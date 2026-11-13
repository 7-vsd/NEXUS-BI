"""Cached data access for chart-level detail (processed parquet marts).

KPIs and predictions come from the API; detailed time series and breakdowns
are read from the same processed marts the API uses (single source of truth).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.settings import settings  # noqa: E402

P = settings.processed_dir


class DataMissing(RuntimeError):
    pass


@st.cache_data(show_spinner="Loading data…")
def load(name: str) -> pd.DataFrame:
    path = P / f"{name}.parquet"
    if not path.exists():
        raise DataMissing(f"`{path.name}` not found. Run `python -m src.pipeline --stage all` first.")
    return pd.read_parquet(path)


@st.cache_data
def load_json(path: str) -> dict:
    p = ROOT / path
    if not p.exists():
        raise DataMissing(f"`{path}` not found.")
    return json.loads(p.read_text())


@st.cache_data
def load_csv(path: str) -> pd.DataFrame:
    p = ROOT / path
    if not p.exists():
        raise DataMissing(f"`{path}` not found.")
    return pd.read_csv(p)


def filters() -> dict:
    return st.session_state.get("filters", {})


def filtered_orders() -> pd.DataFrame:
    om = load("order_mart")
    f = filters()
    m = pd.Series(True, index=om.index)
    if f.get("start"):
        m &= om.order_purchase_timestamp >= pd.Timestamp(f["start"])
    if f.get("end"):
        m &= om.order_purchase_timestamp < pd.Timestamp(f["end"]) + pd.Timedelta(days=1)
    if f.get("regions"):
        m &= om.customer_state.map(REGION_OF).isin(f["regions"])
    if f.get("states"):
        m &= om.customer_state.isin(f["states"])
    if f.get("categories"):
        m &= om.main_category.isin(f["categories"])
    return om[m]


def filtered_items() -> pd.DataFrame:
    it = load("items_enriched")
    ids = set(filtered_orders().order_id)
    return it[it.order_id.isin(ids)]


REGION_OF = {**{s: "Norte" for s in ["AC", "AP", "AM", "PA", "RO", "RR", "TO"]},
             **{s: "Nordeste" for s in ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"]},
             **{s: "Centro-Oeste" for s in ["DF", "GO", "MT", "MS"]},
             **{s: "Sudeste" for s in ["ES", "MG", "RJ", "SP"]}, **{s: "Sul" for s in ["PR", "RS", "SC"]}}


def pretty(cat: str) -> str:
    return str(cat).replace("_", " ").title()
