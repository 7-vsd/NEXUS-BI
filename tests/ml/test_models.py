"""ML tests: leakage checks, baseline comparisons, evaluation sanity and artifact contracts."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from ml.common import ART, regression_metrics, reliable_window
from src.config.settings import settings

trained = (ART / "churn_prediction" / "metrics.json").exists()
pytestmark = pytest.mark.skipif(not trained, reason="run `python -m ml.train_all` first")


def metrics(m):
    return json.loads((ART / m / "metrics.json").read_text())


# ------------------------------------------------------------------ leakage
def test_churn_features_use_only_history():
    from ml.churn_prediction.churn import CUTOFFS, build_features, order_history
    hist = order_history()
    for cutoff in CUTOFFS.values():
        f = build_features(hist, cutoff)
        assert (f.max_feature_ts < pd.Timestamp(cutoff)).all()
        assert (f.recency_days >= 0).all()


def test_churn_label_windows_do_not_overlap_later_cutoffs():
    from ml.churn_prediction.churn import CUTOFFS, HORIZON_DAYS
    c = {k: pd.Timestamp(v) for k, v in CUTOFFS.items()}
    assert c["train"] + pd.Timedelta(days=HORIZON_DAYS) <= c["validation"] + pd.Timedelta(days=HORIZON_DAYS)
    assert c["validation"] + pd.Timedelta(days=HORIZON_DAYS) <= c["test"]
    end = reliable_window(pd.read_parquet(settings.processed_dir / "daily_kpis.parquet"))[1]
    assert c["test"] + pd.Timedelta(days=HORIZON_DAYS) <= end       # test labels fully observed


def test_churn_label_depends_on_future_only():
    from ml.churn_prediction.churn import build_features
    hist = pd.DataFrame({"customer_unique_id": ["a", "a", "b"], "order_id": ["1", "2", "3"],
                         "order_purchase_timestamp": pd.to_datetime(["2018-01-01", "2018-03-01", "2018-01-05"]),
                         "revenue": [10.0, 20.0, 5.0], "items_count": [1, 1, 1], "review_score": [5, 4, 1],
                         "is_late": [False, False, True], "delivery_days": [5.0, 6.0, 20.0], "freight_ratio": [.1, .1, .5],
                         "max_installments": [1, 2, 1], "main_category": ["x", "y", "x"], "customer_state": ["SP", "SP", "BA"],
                         "main_payment_type": ["boleto", "credit_card", "boleto"]})
    f = build_features(hist, "2018-02-01").set_index("customer_unique_id")
    assert f.loc["a", "frequency"] == 1 and f.loc["a", "monetary"] == 10.0     # March order NOT in features
    assert f.loc["a", "churn"] == 0 and f.loc["b", "churn"] == 1                # but it IS in the label


def test_xgb_revenue_features_respect_horizon():
    from ml.revenue_forecasting.forecast import LAGS, xgb_design
    assert min(LAGS) >= 30
    s = pd.Series(np.arange(200, dtype=float), index=pd.date_range("2018-01-01", periods=200))
    train = s.iloc[:170]
    X = xgb_design(train, pd.date_range(train.index.max() + pd.Timedelta(days=1), periods=30))
    assert X.notna().all().all()          # all 30 horizons computable from data <= origin -> no look-ahead


# ------------------------------------------------------------------ baselines & evaluation
def test_churn_models_beat_no_skill_baseline_on_ranking():
    r = metrics("churn_prediction")["results"]
    base = r["baseline_prior"]["test"]
    best = r[metrics("churn_prediction")["best_model"]]["test"]
    assert best["roc_auc"] > base["roc_auc"] + 0.03
    assert best["return_lift_top_decile"] > 1.2


def test_revenue_backtest_metrics_and_best_model_selection():
    m = metrics("revenue_forecasting")
    maes = {k: v["overall"]["mae"] for k, v in m["backtest"].items()}
    assert m["best_model_by_backtest_mae"] == min(maes, key=maes.get)
    assert {"seasonal_naive", "sarima", "xgboost"} <= set(maes)
    for v in m["backtest"].values():
        assert v["overall"]["n"] == m["folds"] * m["horizon_days"]


def test_forecast_intervals_contain_point_forecast():
    f = pd.read_parquet(settings.processed_dir / "revenue_forecast.parquet")
    assert len(f.date.unique()) == 30
    assert (f.lower_95 <= f.predicted + 1e-6).all() and (f.predicted <= f.upper_95 + 1e-6).all()
    assert (f.lower_95 >= 0).all()


def test_demand_backtest_includes_baselines():
    m = metrics("demand_forecasting")
    assert {"naive", "moving_avg_4w", "xgboost"} <= set(m["backtest_overall"])
    assert len(m["categories"]) == 10


def test_segmentation_quality_and_coverage():
    m = metrics("customer_segmentation")
    assert 3 <= m["selected_k"] <= 8 and m["silhouette_selected"] > 0.2
    seg = pd.read_parquet(settings.processed_dir / "customer_segments.parquet")
    cm = pd.read_parquet(settings.processed_dir / "customer_mart.parquet")
    assert len(seg) == len(cm) and seg.customer_unique_id.is_unique
    assert seg.cluster_name.notna().all() and seg.recommended_strategy.str.len().gt(0).all()


def test_anomaly_detector_flags_black_friday():
    a = pd.read_parquet(settings.processed_dir / "anomalies.parquet")
    bf = a[a.date == "2017-11-24"]
    assert len(bf) == 1 and bool(bf.is_anomaly.iloc[0]) and bf.direction.iloc[0] == "spike"
    assert a.is_anomaly.mean() < 0.05


def test_anomaly_scoring_function():
    from ml.anomaly_detection.anomaly import score_observation
    normal = score_observation({"date": "2018-08-20", "revenue": 40000, "orders": 260, "late_rate": .06,
                                "avg_review": 4.1, "cancel_rate": .003})
    spike = score_observation({"date": "2018-08-20", "revenue": 400000, "orders": 2600, "late_rate": .06,
                               "avg_review": 4.1, "cancel_rate": .003})
    assert not normal["is_anomaly"] and spike["is_anomaly"]


def test_regression_metrics():
    m = regression_metrics([100, 200, 0], [110, 180, 10])
    assert m["mae"] == pytest.approx(40 / 3) and m["mape_pct"] == pytest.approx(10.0)   # zero actual excluded from MAPE


def test_reliable_window_excludes_truncated_tail():
    d = pd.read_parquet(settings.processed_dir / "daily_kpis.parquet")
    start, end = reliable_window(d)
    assert start >= pd.Timestamp("2017-01-01") and end <= pd.Timestamp("2018-08-31")


def test_artifacts_and_metadata_exist():
    for mod in ("customer_segmentation", "churn_prediction", "revenue_forecasting", "demand_forecasting", "anomaly_detection"):
        meta = json.loads((ART / mod / "metadata.json").read_text())
        assert meta["module"] == mod and "trained_at" in meta
        assert list((ART / mod).glob("*.joblib"))
