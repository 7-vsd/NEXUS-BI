"""Customers transform: standardise geography fields, keep both customer keys."""
from __future__ import annotations

import pandas as pd

from src.transformation.common import CleaningLog, drop_exact_duplicates, normalize_city, normalize_state, normalize_zip

DATASET = "customers"


def transform(df: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    out = df.copy()
    out["customer_zip_code_prefix"] = normalize_zip(out.customer_zip_code_prefix)
    before = out.customer_city.copy()
    out["customer_city"] = normalize_city(out.customer_city)
    log.add(DATASET, "normalize_city", int((before != out.customer_city).sum()), "lower-case, accents removed")
    out["customer_state"] = normalize_state(out.customer_state)
    out = drop_exact_duplicates(out, DATASET, log, ["customer_id"])
    return out.reset_index(drop=True)
