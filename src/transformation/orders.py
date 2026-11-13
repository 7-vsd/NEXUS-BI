"""Orders transform: lifecycle validation, delivery metrics and status flags."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.transformation.common import CleaningLog, drop_exact_duplicates

DATASET = "orders"
# Statuses that never generate recognised revenue
NON_REVENUE_STATUSES = ("canceled", "unavailable")


def transform(df: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    out = df.copy()
    out["order_status"] = out.order_status.str.strip().str.lower()
    out = drop_exact_duplicates(out, DATASET, log, ["order_id"])

    # Timestamps that precede the purchase are physically impossible -> flag & null them
    for col in ("order_approved_at", "order_delivered_carrier_date", "order_delivered_customer_date"):
        bad = out[col] < out.order_purchase_timestamp
        if bad.any():
            log.add(DATASET, f"null_{col}_before_purchase", int(bad.sum()))
            out.loc[bad, col] = pd.NaT

    out["order_purchase_date"] = out.order_purchase_timestamp.dt.normalize()
    out["is_revenue_order"] = ~out.order_status.isin(NON_REVENUE_STATUSES)
    out["is_canceled"] = out.order_status.eq("canceled")
    out["is_delivered"] = out.order_status.eq("delivered") & out.order_delivered_customer_date.notna()

    sec_per_day = 86400.0
    out["approval_hours"] = ((out.order_approved_at - out.order_purchase_timestamp).dt.total_seconds() / 3600).round(2)
    out["delivery_days"] = ((out.order_delivered_customer_date - out.order_purchase_timestamp).dt.total_seconds() / sec_per_day).round(2)
    out["estimated_delivery_days"] = ((out.order_estimated_delivery_date - out.order_purchase_timestamp).dt.total_seconds() / sec_per_day).round(2)
    # Positive = late. Compared at date granularity (estimate is a date at 00:00)
    out["delivery_delay_days"] = (out.order_delivered_customer_date.dt.normalize() - out.order_estimated_delivery_date.dt.normalize()).dt.days.astype("Int64")
    out["is_on_time"] = pd.array(np.where(out.is_delivered, out.delivery_delay_days.fillna(0) <= 0, pd.NA), dtype="boolean")
    out["is_late"] = pd.array(np.where(out.is_delivered, out.delivery_delay_days.fillna(0) > 0, pd.NA), dtype="boolean")
    log.add(DATASET, "derive_delivery_metrics", int(out.is_delivered.sum()), "delivery_days, delay, on-time flags")
    return out.reset_index(drop=True)
