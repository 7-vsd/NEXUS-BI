"""Data & model access for the API (loaded once, cached)."""
from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
import pandas as pd

from ml.common import ART, load_model
from src.config.settings import settings
from src.logging.logger import get_logger

log = get_logger("api.services")


# 2016 contains only a few hundred test orders; growth comparisons must not use it as a base.
RELIABLE_START = pd.Timestamp("2017-01-01")


class ResourceUnavailable(RuntimeError):
    """A model or dataset required by an endpoint has not been produced yet."""


def _read(name: str) -> pd.DataFrame:
    path = settings.processed_dir / f"{name}.parquet"
    if not path.exists():
        raise ResourceUnavailable(f"{path.name} not found – run the pipeline (make etl && make train)")
    return pd.read_parquet(path)


@lru_cache(maxsize=None)
def order_mart() -> pd.DataFrame:
    return _read("order_mart")


@lru_cache(maxsize=None)
def metrics(module: str) -> dict:
    p = ART / module / "metrics.json"
    if not p.exists():
        raise ResourceUnavailable(f"metrics for {module} not found – run `python -m ml.train_all`")
    return json.loads(p.read_text())


@lru_cache(maxsize=None)
def model(module: str, name: str):
    try:
        return load_model(module, name)
    except FileNotFoundError as exc:
        raise ResourceUnavailable(f"model {module}/{name} not found – run `python -m ml.train_all`") from exc


@lru_cache(maxsize=None)
def table(name: str) -> pd.DataFrame:
    return _read(name)


def models_status() -> dict[str, bool]:
    files = {"customer_segmentation": "kmeans_rfm", "churn_prediction": "churn_model",
             "revenue_forecasting": "xgboost_revenue", "demand_forecasting": "xgboost_demand",
             "anomaly_detection": "anomaly_model"}
    return {m: (ART / m / f"{f}.joblib").exists() for m, f in files.items()}


def compute_kpis(om: pd.DataFrame) -> dict:
    rev = om[om.is_revenue_order]
    orders = int(rev.order_id.nunique())
    revenue = float(rev.revenue.sum())
    dl = om[om.is_delivered]
    with_items = rev[rev.items_count > 0]
    per_cust = with_items.groupby("customer_unique_id").order_id.nunique()
    return {
        "total_revenue": round(revenue, 2),
        "product_revenue": round(float(rev.items_price.sum()), 2),
        "freight_revenue": round(float(rev.freight_value.sum()), 2),
        "total_orders": orders,
        "unique_customers": int(rev.customer_unique_id.nunique()),
        "average_order_value": round(revenue / orders, 2) if orders else 0.0,
        "cancellation_rate": round(float(om.is_canceled.mean()), 6) if len(om) else 0.0,
        "on_time_delivery_rate": round(float(dl.is_on_time.astype(float).mean()), 6) if len(dl) else None,
        "avg_delivery_days": round(float(dl.delivery_days.mean()), 3) if len(dl) else None,
        "avg_review_score": round(float(om.review_score.mean()), 4) if om.review_score.notna().any() else None,
        "repeat_customer_rate": round(float((per_cust > 1).mean()), 6) if len(per_cust) else 0.0,
    }


def filter_orders(start=None, end=None, state: str | None = None, category: str | None = None) -> pd.DataFrame:
    om = order_mart()
    m = pd.Series(True, index=om.index)
    if start is not None:
        m &= om.order_purchase_timestamp >= pd.Timestamp(start)
    if end is not None:
        m &= om.order_purchase_timestamp < pd.Timestamp(end) + pd.Timedelta(days=1)
    if state:
        m &= om.customer_state == state.upper()
    if category:
        m &= om.main_category == category
    return om[m]


def risk_band(p: float) -> str:
    return "Very High" if p >= 0.97 else "High" if p >= 0.9 else "Medium"


def predict_churn(rows: list[dict]) -> tuple[dict, np.ndarray]:
    b = model("churn_prediction", "churn_model")
    X = pd.DataFrame(rows)[b["features"]]
    for c in b["numeric_features"]:
        X[c] = pd.to_numeric(X[c], errors="coerce")
    return b, b["pipeline"].predict_proba(X)[:, 1]
