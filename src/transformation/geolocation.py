"""Geolocation transform.

The raw file holds ~1M lat/lng samples with many points per zip prefix and
exact duplicates. We (1) drop exact duplicates, (2) drop coordinates outside
Brazil's bounding box, then (3) collapse to one row per zip prefix using the
median coordinate and the most frequent city/state. The result is the
``dim_location`` geography source.
"""
from __future__ import annotations

import pandas as pd

from src.transformation.common import CleaningLog, drop_exact_duplicates, normalize_city, normalize_state, normalize_zip
from src.validation.quality import BRAZIL_LAT, BRAZIL_LNG

DATASET = "geolocation"


def transform(df: pd.DataFrame, log: CleaningLog) -> pd.DataFrame:
    out = df.copy()
    out["geolocation_zip_code_prefix"] = normalize_zip(out.geolocation_zip_code_prefix)
    out["geolocation_city"] = normalize_city(out.geolocation_city)
    out["geolocation_state"] = normalize_state(out.geolocation_state)
    out = drop_exact_duplicates(out, DATASET, log)
    in_box = out.geolocation_lat.between(*BRAZIL_LAT) & out.geolocation_lng.between(*BRAZIL_LNG)
    log.add(DATASET, "drop_coordinates_outside_brazil", int((~in_box).sum()))
    out = out[in_box]
    agg = (out.groupby("geolocation_zip_code_prefix", observed=True)
              .agg(latitude=("geolocation_lat", "median"),
                   longitude=("geolocation_lng", "median"),
                   sample_points=("geolocation_lat", "size"))
              .reset_index())
    mode_city = (out.groupby(["geolocation_zip_code_prefix", "geolocation_city", "geolocation_state"], observed=True)
                    .size().reset_index(name="n")
                    .sort_values(["geolocation_zip_code_prefix", "n"], ascending=[True, False])
                    .drop_duplicates("geolocation_zip_code_prefix"))
    agg = agg.merge(mode_city.drop(columns="n"), on="geolocation_zip_code_prefix", how="left")
    log.add(DATASET, "aggregate_to_zip_prefix", len(agg), "median lat/lng, modal city/state per prefix")
    return agg.rename(columns={"geolocation_zip_code_prefix": "zip_code_prefix",
                               "geolocation_city": "city", "geolocation_state": "state"})
