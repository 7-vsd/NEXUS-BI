"""Expected source schemas for the Olist datasets.

Each entry defines the logical dataset name, a filename pattern used for
automatic discovery, the expected columns with their target pandas dtypes,
the primary key and the foreign keys used for referential-integrity checks.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DatasetSchema:
    name: str
    pattern: str                       # regex matched against the file name
    columns: dict[str, str]            # column -> dtype ("string", "float", "int", "datetime")
    primary_key: tuple[str, ...]
    foreign_keys: dict[str, tuple[str, str]] = field(default_factory=dict)  # col -> (dataset, col)
    description: str = ""


SCHEMAS: dict[str, DatasetSchema] = {
    "customers": DatasetSchema(
        name="customers",
        pattern=r"customers?_dataset\.csv$",
        columns={
            "customer_id": "string",
            "customer_unique_id": "string",
            "customer_zip_code_prefix": "string",
            "customer_city": "string",
            "customer_state": "string",
        },
        primary_key=("customer_id",),
        description="One row per customer_id. customer_id is order-specific; customer_unique_id identifies the person.",
    ),
    "orders": DatasetSchema(
        name="orders",
        pattern=r"orders?_dataset\.csv$",
        columns={
            "order_id": "string",
            "customer_id": "string",
            "order_status": "string",
            "order_purchase_timestamp": "datetime",
            "order_approved_at": "datetime",
            "order_delivered_carrier_date": "datetime",
            "order_delivered_customer_date": "datetime",
            "order_estimated_delivery_date": "datetime",
        },
        primary_key=("order_id",),
        foreign_keys={"customer_id": ("customers", "customer_id")},
        description="Order header with lifecycle timestamps.",
    ),
    "order_items": DatasetSchema(
        name="order_items",
        pattern=r"order_items?_dataset\.csv$",
        columns={
            "order_id": "string",
            "order_item_id": "int",
            "product_id": "string",
            "seller_id": "string",
            "shipping_limit_date": "datetime",
            "price": "float",
            "freight_value": "float",
        },
        primary_key=("order_id", "order_item_id"),
        foreign_keys={
            "order_id": ("orders", "order_id"),
            "product_id": ("products", "product_id"),
            "seller_id": ("sellers", "seller_id"),
        },
        description="One row per item within an order (item sequence number order_item_id).",
    ),
    "payments": DatasetSchema(
        name="payments",
        pattern=r"order_payments?_dataset\.csv$",
        columns={
            "order_id": "string",
            "payment_sequential": "int",
            "payment_type": "string",
            "payment_installments": "int",
            "payment_value": "float",
        },
        primary_key=("order_id", "payment_sequential"),
        foreign_keys={"order_id": ("orders", "order_id")},
        description="One row per payment transaction of an order.",
    ),
    "reviews": DatasetSchema(
        name="reviews",
        pattern=r"order_reviews?_dataset\.csv$",
        columns={
            "review_id": "string",
            "order_id": "string",
            "review_score": "int",
            "review_comment_title": "string",
            "review_comment_message": "string",
            "review_creation_date": "datetime",
            "review_answer_timestamp": "datetime",
        },
        primary_key=("review_id", "order_id"),
        foreign_keys={"order_id": ("orders", "order_id")},
        description="Customer satisfaction survey responses.",
    ),
    "products": DatasetSchema(
        name="products",
        pattern=r"products?_dataset\.csv$",
        columns={
            "product_id": "string",
            "product_category_name": "string",
            "product_name_lenght": "float",
            "product_description_lenght": "float",
            "product_photos_qty": "float",
            "product_weight_g": "float",
            "product_length_cm": "float",
            "product_height_cm": "float",
            "product_width_cm": "float",
        },
        primary_key=("product_id",),
        description="Product catalogue (category in Portuguese, physical attributes).",
    ),
    "sellers": DatasetSchema(
        name="sellers",
        pattern=r"sellers?_dataset\.csv$",
        columns={
            "seller_id": "string",
            "seller_zip_code_prefix": "string",
            "seller_city": "string",
            "seller_state": "string",
        },
        primary_key=("seller_id",),
        description="Marketplace sellers.",
    ),
    "geolocation": DatasetSchema(
        name="geolocation",
        pattern=r"geolocation_dataset\.csv$",
        columns={
            "geolocation_zip_code_prefix": "string",
            "geolocation_lat": "float",
            "geolocation_lng": "float",
            "geolocation_city": "string",
            "geolocation_state": "string",
        },
        primary_key=(),  # no natural key: many points per zip prefix
        description="Lat/lng samples per 5-digit zip-code prefix (many rows per prefix).",
    ),
    "category_translation": DatasetSchema(
        name="category_translation",
        pattern=r"product_category_name_translation\.csv$",
        columns={
            "product_category_name": "string",
            "product_category_name_english": "string",
        },
        primary_key=("product_category_name",),
        description="Portuguese -> English category names.",
    ),
}

DATETIME_COLUMNS: dict[str, list[str]] = {
    n: [c for c, t in s.columns.items() if t == "datetime"] for n, s in SCHEMAS.items()
}
