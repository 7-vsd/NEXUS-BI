"""Order items transform: monetary validation and line totals."""
from __future__ import annotations

import pandas as pd

from src.transformation.common import CleaningLog, drop_exact_duplicates

DATASET = "order_items"


def transform(df: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    out = drop_exact_duplicates(df.copy(), DATASET, log, ["order_id", "order_item_id"])
    bad = (out.price <= 0) | (out.freight_value < 0)
    if bad.any():
        log.add(DATASET, "drop_invalid_amounts", int(bad.sum()), "price<=0 or freight<0")
        out = out[~bad]
    out["price"] = out.price.round(2)
    out["freight_value"] = out.freight_value.round(2)
    out["line_total"] = (out.price + out.freight_value).round(2)
    return out.reset_index(drop=True)
