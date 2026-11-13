"""Data profiling and data-dictionary generation."""
from __future__ import annotations

import pandas as pd

from src.validation.schemas import SCHEMAS

# Business descriptions for the data dictionary (source: Olist dataset documentation + inspection).
COLUMN_DESCRIPTIONS: dict[str, str] = {
    "customer_id": "Order-scoped customer key (one per order). FK from orders.",
    "customer_unique_id": "Stable identifier of the real customer across orders.",
    "customer_zip_code_prefix": "First 5 digits of the customer zip code (string, zero-padded).",
    "customer_city": "Customer city name (lower-case, Portuguese).",
    "customer_state": "Customer state (2-letter Brazilian UF code).",
    "order_id": "Unique order identifier.",
    "order_status": "Lifecycle status: delivered, shipped, canceled, unavailable, invoiced, processing, created, approved.",
    "order_purchase_timestamp": "Timestamp the order was placed.",
    "order_approved_at": "Timestamp payment was approved.",
    "order_delivered_carrier_date": "Timestamp the order was handed to the logistics partner.",
    "order_delivered_customer_date": "Actual delivery timestamp to the customer.",
    "order_estimated_delivery_date": "Estimated delivery date shown to the customer at purchase.",
    "order_item_id": "Sequential item number within an order (1..n).",
    "product_id": "Unique product identifier.",
    "seller_id": "Unique seller identifier.",
    "shipping_limit_date": "Seller's shipping deadline for handing the item to the carrier.",
    "price": "Item price in BRL.",
    "freight_value": "Freight charged for the item in BRL (split per item when the order has several).",
    "payment_sequential": "Sequence number when an order is paid with several payment methods.",
    "payment_type": "credit_card, boleto, voucher, debit_card, not_defined.",
    "payment_installments": "Number of installments chosen by the customer.",
    "payment_value": "Transaction value in BRL.",
    "review_id": "Survey identifier (NOT unique alone: the same review_id can cover several orders).",
    "review_score": "Satisfaction score 1-5.",
    "review_comment_title": "Optional review title (Portuguese).",
    "review_comment_message": "Optional review comment (Portuguese).",
    "review_creation_date": "Date the satisfaction survey was sent.",
    "review_answer_timestamp": "Timestamp the survey was answered.",
    "product_category_name": "Product category (Portuguese).",
    "product_name_lenght": "Characters in the product name (source spelling 'lenght').",
    "product_description_lenght": "Characters in the product description (source spelling 'lenght').",
    "product_photos_qty": "Number of published product photos.",
    "product_weight_g": "Product weight in grams.",
    "product_length_cm": "Product length in cm.",
    "product_height_cm": "Product height in cm.",
    "product_width_cm": "Product width in cm.",
    "seller_zip_code_prefix": "First 5 digits of the seller zip code.",
    "seller_city": "Seller city name.",
    "seller_state": "Seller state (UF).",
    "geolocation_zip_code_prefix": "5-digit zip-code prefix.",
    "geolocation_lat": "Latitude (decimal degrees).",
    "geolocation_lng": "Longitude (decimal degrees).",
    "geolocation_city": "City name.",
    "geolocation_state": "State (UF).",
    "product_category_name_english": "Category name translated to English.",
}


def profile_column(s: pd.Series) -> dict:
    n = len(s)
    nulls = int(s.isna().sum())
    prof = {
        "column": s.name,
        "dtype": str(s.dtype),
        "non_null": n - nulls,
        "nulls": nulls,
        "null_pct": round(100 * nulls / n, 3) if n else 0.0,
        "distinct": int(s.nunique(dropna=True)),
    }
    if pd.api.types.is_numeric_dtype(s):
        d = s.dropna().astype(float)
        prof.update(min=d.min() if len(d) else None, p25=d.quantile(.25) if len(d) else None,
                    median=d.median() if len(d) else None, mean=d.mean() if len(d) else None,
                    p75=d.quantile(.75) if len(d) else None, max=d.max() if len(d) else None,
                    std=d.std() if len(d) else None)
    elif pd.api.types.is_datetime64_any_dtype(s):
        prof.update(min=s.min(), max=s.max())
    else:
        top = s.value_counts(dropna=True).head(3)
        prof.update(top_values="; ".join(f"{k} ({v})" for k, v in top.items()),
                    min_len=int(s.dropna().str.len().min()) if s.notna().any() else None,
                    max_len=int(s.dropna().str.len().max()) if s.notna().any() else None)
    return prof


def profile_dataset(name: str, df: pd.DataFrame) -> pd.DataFrame:
    rows = [profile_column(df[c]) for c in df.columns]
    out = pd.DataFrame(rows)
    out.insert(0, "dataset", name)
    return out


def build_data_dictionary(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for name, df in frames.items():
        schema = SCHEMAS[name]
        for col, dtype in schema.columns.items():
            s = df[col]
            example = s.dropna().iloc[0] if s.notna().any() else None
            rows.append({
                "dataset": name,
                "column": col,
                "target_type": dtype,
                "is_primary_key": col in schema.primary_key,
                "foreign_key_to": ".".join(schema.foreign_keys[col]) if col in schema.foreign_keys else "",
                "null_pct": round(100 * s.isna().mean(), 3),
                "distinct_values": int(s.nunique()),
                "example": str(example)[:60] if example is not None else "",
                "description": COLUMN_DESCRIPTIONS.get(col, ""),
            })
    return pd.DataFrame(rows)
