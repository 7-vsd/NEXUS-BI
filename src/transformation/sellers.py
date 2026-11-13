"""Sellers transform: standardise geography fields."""
from __future__ import annotations

import pandas as pd

from src.transformation.common import CleaningLog, drop_exact_duplicates, normalize_city, normalize_state, normalize_zip

DATASET = "sellers"


def transform(df: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    out = df.copy()
    out["seller_zip_code_prefix"] = normalize_zip(out.seller_zip_code_prefix)
    before = out.seller_city.copy()
    out["seller_city"] = normalize_city(out.seller_city)
    log.add(DATASET, "normalize_city", int((before != out.seller_city).sum()), "lower-case, accents removed")
    out["seller_state"] = normalize_state(out.seller_state)
    out = drop_exact_duplicates(out, DATASET, log, ["seller_id"])
    return out.reset_index(drop=True)
