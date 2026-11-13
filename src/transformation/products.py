"""Products transform: fix misspelt source columns, translate categories, derive volume."""
from __future__ import annotations

import pandas as pd

from src.transformation.common import CleaningLog, drop_exact_duplicates, normalize_category

DATASET = "products"

# Two Portuguese categories present in products but absent from the translation file.
# Translations added manually and documented in docs/database/DATA_DICTIONARY.md.
MANUAL_TRANSLATIONS = {
    "pc_gamer": "pc_gamer",
    "portateis_cozinha_e_preparadores_de_alimentos": "portable_kitchen_food_preparers",
}
UNKNOWN = "unknown"


def transform(df: pd.DataFrame, translation: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    out = df.rename(columns={"product_name_lenght": "product_name_length",
                             "product_description_lenght": "product_description_length"}).copy()
    out["product_category_name"] = normalize_category(out.product_category_name)
    missing_cat = out.product_category_name.isna()
    log.add(DATASET, "fill_missing_category", int(missing_cat.sum()), f"set to '{UNKNOWN}'")
    out["product_category_name"] = out.product_category_name.fillna(UNKNOWN)

    trans = translation.copy()
    trans["product_category_name"] = normalize_category(trans.product_category_name)
    mapping = dict(zip(trans.product_category_name, trans.product_category_name_english))
    mapping.update(MANUAL_TRANSLATIONS)
    mapping[UNKNOWN] = UNKNOWN
    out["product_category_name_english"] = out.product_category_name.map(mapping).astype("string")
    log.add(DATASET, "manual_category_translation",
            int(out.product_category_name.isin(MANUAL_TRANSLATIONS).sum()), ", ".join(MANUAL_TRANSLATIONS))

    for c in ("product_name_length", "product_description_length", "product_photos_qty"):
        out[c] = out[c].astype("Int64")
    zero_w = out.product_weight_g == 0
    log.add(DATASET, "zero_weight_to_null", int(zero_w.sum()), "weight 0 g treated as unknown")
    out.loc[zero_w, "product_weight_g"] = pd.NA
    out["product_volume_cm3"] = out.product_length_cm * out.product_height_cm * out.product_width_cm
    out = drop_exact_duplicates(out, DATASET, log, ["product_id"])
    return out.reset_index(drop=True)
