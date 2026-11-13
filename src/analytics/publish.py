"""Publish stage: ML outputs -> nexus_ml tables, warehouse -> Power BI CSV extracts, status file."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd

from src.config.settings import settings
from src.logging.logger import get_logger

log = get_logger("publish")
PBI_DIR = settings.processed_dir / "powerbi"
PBI_TABLES = [
    "nexus_dw.dim_date", "nexus_dw.dim_customer", "nexus_dw.dim_product", "nexus_dw.dim_seller",
    "nexus_dw.dim_location", "nexus_dw.dim_payment_type", "nexus_dw.fact_orders", "nexus_dw.fact_order_items",
    "nexus_dw.fact_payments", "nexus_dw.fact_reviews", "nexus_ml.customer_segments", "nexus_ml.churn_scores",
    "nexus_ml.revenue_forecast", "nexus_ml.demand_forecast", "nexus_ml.anomalies",
    "nexus_dw.syn_inventory_weekly", "nexus_dw.vw_syn_category_margin",
]


def ml_frames() -> dict[str, pd.DataFrame]:
    P = settings.processed_dir
    seg = pd.read_parquet(P / "customer_segments.parquet")
    churn = pd.read_parquet(P / "churn_scores.parquet")
    rv_bt = pd.read_parquet(P / "revenue_backtest.parquet")
    rv_f = pd.read_parquet(P / "revenue_forecast.parquet")
    dm_bt = pd.read_parquet(P / "demand_backtest.parquet")
    dm_f = pd.read_parquet(P / "demand_forecast.parquet")
    an = pd.read_parquet(P / "anomalies.parquet")
    an["orders"] = an.orders.round().astype("Int64")

    # last fold covering each date wins for backtest (dates are unique per fold anyway)
    rev = pd.concat([
        rv_bt.assign(kind="backtest", lower_95=None, upper_95=None)[["date", "model", "kind", "actual", "predicted", "lower_95", "upper_95"]],
        rv_f.assign(kind="future", actual=None)[["date", "model", "kind", "actual", "predicted", "lower_95", "upper_95"]],
    ]).drop_duplicates(["date", "model", "kind"], keep="last").rename(columns={"date": "forecast_date", "model": "model_name"})
    dem = pd.concat([
        dm_bt.assign(kind="backtest", lower_95=None, upper_95=None)[["category", "week", "model", "kind", "actual", "predicted", "lower_95", "upper_95"]],
        dm_f.assign(kind="future", actual=None)[["category", "week", "model", "kind", "actual", "predicted", "lower_95", "upper_95"]],
    ]).drop_duplicates(["category", "week", "model", "kind"], keep="last").rename(columns={"week": "week_start", "model": "model_name"})
    return {
        "nexus_ml.customer_segments": seg[["customer_unique_id", "recency_days", "frequency", "monetary", "r_score", "f_score",
                                           "m_score", "rfm_segment", "cluster", "cluster_name", "recommended_strategy"]],
        "nexus_ml.churn_scores": churn[["customer_unique_id", "cutoff_date", "churn_probability", "risk_band", "model_name"]]
                                 .assign(actual_churn=None),
        "nexus_ml.revenue_forecast": rev,
        "nexus_ml.demand_forecast": dem,
        "nexus_ml.anomalies": an.rename(columns={"date": "metric_date"})[
            ["metric_date", "revenue", "orders", "aov", "late_rate", "avg_review", "iforest_score", "iforest_flag",
             "rolling_z", "rolling_flag", "global_z", "zscore_flag", "votes", "is_anomaly", "severity", "direction"]],
    }


def publish_outputs(skip_db: bool = False) -> dict:
    out: dict = {"published_at": datetime.now(timezone.utc).isoformat()}
    if not skip_db:
        from src.database.loader import export_tables_csv, load_frame

        for table, df in ml_frames().items():
            out[table] = load_frame(df, table, list(df.columns))
        out["powerbi_extracts"] = export_tables_csv(PBI_TABLES, PBI_DIR)
    (settings.reports_dir / "publish_status.json").write_text(json.dumps(out, indent=2, default=str))
    log.info("Published outputs (skip_db=%s)", skip_db)
    return {"tables": len(out) - 1}
