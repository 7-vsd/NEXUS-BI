"""Data-quality rules: nulls, duplicates, referential integrity, domain checks.

Every check returns a ``CheckResult`` with a severity. Results are aggregated
into the HTML data-quality report and also asserted by the data-quality tests.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from src.validation.schemas import SCHEMAS

BRAZIL_UF = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB",
    "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}
# Approximate bounding box of Brazil (incl. islands)
BRAZIL_LAT = (-34.0, 5.5)
BRAZIL_LNG = (-74.5, -28.5)


@dataclass
class CheckResult:
    dataset: str
    check: str
    column: str
    failed_rows: int
    total_rows: int
    severity: str          # INFO | WARNING | ERROR
    detail: str = ""

    @property
    def failed_pct(self) -> float:
        return round(100 * self.failed_rows / self.total_rows, 4) if self.total_rows else 0.0

    @property
    def status(self) -> str:
        if self.failed_rows == 0:
            return "PASS"
        return {"ERROR": "FAIL", "WARNING": "WARN"}.get(self.severity, "NOTE")

    def to_dict(self) -> dict:
        d = asdict(self)
        d.update(failed_pct=self.failed_pct, status=self.status)
        return d


# Columns that are optional by design (nulls are expected, not a defect)
OPTIONAL_COLUMNS = {"review_comment_title", "review_comment_message", "order_approved_at",
                    "order_delivered_carrier_date", "order_delivered_customer_date"}


def check_nulls(name: str, df: pd.DataFrame) -> list[CheckResult]:
    schema = SCHEMAS[name]
    out = []
    for col in schema.columns:
        n = int(df[col].isna().sum())
        if col in schema.primary_key or col in schema.foreign_keys:
            sev = "ERROR"
        elif col in OPTIONAL_COLUMNS:
            sev = "INFO"
        else:
            sev = "WARNING"
        out.append(CheckResult(name, "null_check", col, n, len(df), sev))
    return out


def check_duplicates(name: str, df: pd.DataFrame) -> list[CheckResult]:
    schema = SCHEMAS[name]
    out = [CheckResult(name, "duplicate_full_row", "*", int(df.duplicated().sum()), len(df), "WARNING")]
    if schema.primary_key:
        n = int(df.duplicated(list(schema.primary_key)).sum())
        out.append(CheckResult(name, "duplicate_primary_key", ",".join(schema.primary_key), n, len(df), "ERROR"))
    return out


def check_referential_integrity(frames: dict[str, pd.DataFrame]) -> list[CheckResult]:
    out = []
    for name, schema in SCHEMAS.items():
        df = frames[name]
        for col, (parent, pcol) in schema.foreign_keys.items():
            orphans = int((~df[col].isin(frames[parent][pcol])).sum())
            out.append(CheckResult(name, "referential_integrity", col, orphans, len(df), "ERROR",
                                   f"{name}.{col} -> {parent}.{pcol}"))
    # Business-level completeness (not FK violations, but important for analytics)
    orders, items, pays = frames["orders"], frames["order_items"], frames["payments"]
    out.append(CheckResult("orders", "orders_without_items", "order_id",
                           int((~orders.order_id.isin(items.order_id)).sum()), len(orders), "WARNING",
                           "Orders with no order_items rows (mostly canceled/unavailable)."))
    out.append(CheckResult("orders", "orders_without_payments", "order_id",
                           int((~orders.order_id.isin(pays.order_id)).sum()), len(orders), "WARNING"))
    prods = frames["products"]
    trans = frames["category_translation"]
    untranslated = prods.product_category_name.dropna()
    out.append(CheckResult("products", "category_without_translation", "product_category_name",
                           int((~untranslated.isin(trans.product_category_name)).sum()), len(prods), "WARNING",
                           ", ".join(sorted(set(untranslated) - set(trans.product_category_name)))))
    geo_zips = set(frames["geolocation"].geolocation_zip_code_prefix)
    cust = frames["customers"]
    out.append(CheckResult("customers", "zip_not_in_geolocation", "customer_zip_code_prefix",
                           int((~cust.customer_zip_code_prefix.isin(geo_zips)).sum()), len(cust), "INFO"))
    sel = frames["sellers"]
    out.append(CheckResult("sellers", "zip_not_in_geolocation", "seller_zip_code_prefix",
                           int((~sel.seller_zip_code_prefix.isin(geo_zips)).sum()), len(sel), "INFO"))
    return out


def check_domains(frames: dict[str, pd.DataFrame]) -> list[CheckResult]:
    o = frames["orders"]
    oi = frames["order_items"]
    p = frames["payments"]
    r = frames["reviews"]
    g = frames["geolocation"]
    c = frames["customers"]
    s = frames["sellers"]
    pr = frames["products"]
    n = len
    checks = [
        CheckResult("orders", "approved_before_purchase", "order_approved_at",
                    int((o.order_approved_at < o.order_purchase_timestamp).sum()), n(o), "WARNING"),
        CheckResult("orders", "carrier_before_purchase", "order_delivered_carrier_date",
                    int((o.order_delivered_carrier_date < o.order_purchase_timestamp).sum()), n(o), "WARNING"),
        CheckResult("orders", "delivered_before_purchase", "order_delivered_customer_date",
                    int((o.order_delivered_customer_date < o.order_purchase_timestamp).sum()), n(o), "WARNING"),
        CheckResult("orders", "delivered_status_missing_delivery_date", "order_delivered_customer_date",
                    int(((o.order_status == "delivered") & o.order_delivered_customer_date.isna()).sum()), n(o), "WARNING"),
        CheckResult("orders", "delivery_date_on_non_delivered", "order_delivered_customer_date",
                    int(((o.order_status != "delivered") & o.order_delivered_customer_date.notna()).sum()), n(o), "INFO"),
        CheckResult("order_items", "shipping_limit_after_2018", "shipping_limit_date",
                    int((oi.shipping_limit_date > pd.Timestamp("2018-12-31")).sum()), n(oi), "WARNING",
                    "Shipping deadline far beyond the dataset period (likely data-entry error)."),
        CheckResult("order_items", "non_positive_price", "price", int((oi.price <= 0).sum()), n(oi), "ERROR"),
        CheckResult("order_items", "negative_freight", "freight_value", int((oi.freight_value < 0).sum()), n(oi), "ERROR"),
        CheckResult("payments", "zero_payment_value", "payment_value", int((p.payment_value <= 0).sum()), n(p), "WARNING"),
        CheckResult("payments", "zero_installments", "payment_installments", int((p.payment_installments < 1).sum()), n(p), "WARNING"),
        CheckResult("payments", "payment_type_not_defined", "payment_type", int((p.payment_type == "not_defined").sum()), n(p), "WARNING"),
        CheckResult("reviews", "score_out_of_range", "review_score", int((~r.review_score.between(1, 5)).sum()), n(r), "ERROR"),
        CheckResult("reviews", "duplicate_review_id_across_orders", "review_id", int(r.review_id.duplicated().sum()), n(r), "INFO",
                    "Same survey id covers several orders; grain is (review_id, order_id)."),
        CheckResult("reviews", "order_with_multiple_reviews", "order_id", int(r.order_id.duplicated().sum()), n(r), "INFO"),
        CheckResult("customers", "invalid_state", "customer_state", int((~c.customer_state.isin(BRAZIL_UF)).sum()), n(c), "ERROR"),
        CheckResult("sellers", "invalid_state", "seller_state", int((~s.seller_state.isin(BRAZIL_UF)).sum()), n(s), "ERROR"),
        CheckResult("geolocation", "coordinates_outside_brazil", "geolocation_lat/lng",
                    int((~g.geolocation_lat.between(*BRAZIL_LAT) | ~g.geolocation_lng.between(*BRAZIL_LNG)).sum()), n(g), "WARNING"),
        CheckResult("products", "missing_dimensions", "product_weight_g", int(pr.product_weight_g.isna().sum()), n(pr), "WARNING"),
        CheckResult("products", "zero_weight", "product_weight_g", int((pr.product_weight_g == 0).sum()), n(pr), "WARNING"),
        CheckResult("customers", "zip_not_5_digits", "customer_zip_code_prefix",
                    int((~c.customer_zip_code_prefix.str.fullmatch(r"\d{5}")).sum()), n(c), "ERROR"),
    ]
    return checks


def run_all_checks(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    results: list[CheckResult] = []
    for name, df in frames.items():
        results += check_nulls(name, df)
        results += check_duplicates(name, df)
    results += check_referential_integrity(frames)
    results += check_domains(frames)
    return pd.DataFrame([r.to_dict() for r in results])
