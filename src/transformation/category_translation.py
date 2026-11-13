"""Category translation transform: normalise keys and append documented manual translations."""
from __future__ import annotations

import pandas as pd

from src.transformation.common import CleaningLog, normalize_category
from src.transformation.products import MANUAL_TRANSLATIONS, UNKNOWN

DATASET = "category_translation"


def transform(df: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    out = df.copy()
    out["product_category_name"] = normalize_category(out.product_category_name)
    extra = pd.DataFrame({"product_category_name": list(MANUAL_TRANSLATIONS) + [UNKNOWN],
                          "product_category_name_english": list(MANUAL_TRANSLATIONS.values()) + [UNKNOWN]})
    extra = extra[~extra.product_category_name.isin(out.product_category_name)]
    log.add(DATASET, "append_manual_translations", len(extra))
    out = pd.concat([out, extra], ignore_index=True).astype("string")
    out["category_display_name"] = out.product_category_name_english.str.replace("_", " ").str.title()
    return out
