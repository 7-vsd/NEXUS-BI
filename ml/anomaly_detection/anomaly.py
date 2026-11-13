"""E. Business anomaly detection on daily KPIs.

Three independent detectors vote; a day is an anomaly when >= 2 agree:
1. Isolation Forest on standardised daily features
   [revenue & orders as log-deviation from trailing 28-day median, AOV,
   late-delivery rate, avg review, cancel rate], contamination = 2%.
2. Rolling statistical threshold: revenue vs the trailing 28-day mean/std
   (excluding the current day); |z| > 3.
3. Global z-score of the detrended, weekday-adjusted log revenue; |z| > 3.
The first 28 days are a warm-up period (no trailing history) and are not scored.

SHAP (TreeExplainer on the Isolation Forest) explains which KPI drove each
flagged day. The fitted scaler/forest and the rolling statistics are saved so
the API can score new observations.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from ml.common import FIG_DIR, REPORT_DIR, SEED, load_processed, metadata, reliable_window, save_json, save_model
from src.config.settings import settings

MODULE = "anomaly_detection"
# Revenue/orders enter as log-deviation from their trailing 28-day median so that
# business GROWTH is not mistaken for anomalies (the platform scaled ~10x in 2017).
FEATURES = ["revenue_vs_trend", "orders_vs_trend", "aov", "late_rate", "avg_review", "cancel_rate"]
CONTAMINATION = 0.02
ROLL_WINDOW = 28
Z_THRESHOLD = 3.0


def daily_frame() -> pd.DataFrame:
    d = load_processed("daily_kpis")
    start, end = reliable_window(d)
    d = d[(d.date >= start) & (d.date <= end)].copy()
    d["log_revenue"] = np.log1p(d.revenue)
    d["log_orders"] = np.log1p(d.orders)
    d["trend_log_revenue"] = d.log_revenue.shift(1).rolling(ROLL_WINDOW, min_periods=ROLL_WINDOW).median()
    d["trend_log_orders"] = d.log_orders.shift(1).rolling(ROLL_WINDOW, min_periods=ROLL_WINDOW).median()
    d["revenue_vs_trend"] = d.log_revenue - d.trend_log_revenue
    d["orders_vs_trend"] = d.log_orders - d.trend_log_orders
    for c in ("aov", "late_rate", "avg_review", "cancel_rate"):
        d[c] = d[c].fillna(d[c].median())
    return d.iloc[ROLL_WINDOW:].reset_index(drop=True)   # warm-up excluded


def add_statistical_flags(d: pd.DataFrame) -> pd.DataFrame:
    roll = d.revenue.shift(1).rolling(ROLL_WINDOW, min_periods=14)
    d["rolling_mean"] = roll.mean()
    d["rolling_std"] = roll.std()
    d["rolling_z"] = (d.revenue - d.rolling_mean) / d.rolling_std
    d["rolling_flag"] = d.rolling_z.abs() > Z_THRESHOLD
    dow_mean = d.groupby(d.date.dt.dayofweek).revenue_vs_trend.transform("mean")
    resid = d.revenue_vs_trend - dow_mean
    d["global_z"] = (resid - resid.mean()) / resid.std()
    d["zscore_flag"] = d.global_z.abs() > Z_THRESHOLD
    return d


def train() -> dict:
    d = add_statistical_flags(daily_frame())
    scaler = StandardScaler().fit(d[FEATURES])
    X = scaler.transform(d[FEATURES])
    forest = IsolationForest(n_estimators=300, contamination=CONTAMINATION, random_state=SEED).fit(X)
    d["iforest_score"] = -forest.score_samples(X)          # higher = more anomalous
    d["iforest_flag"] = forest.predict(X) == -1
    d["votes"] = d[["iforest_flag", "rolling_flag", "zscore_flag"]].sum(axis=1).astype(int)
    d["is_anomaly"] = d.votes >= 2
    d["severity"] = np.select([d.votes == 3, d.votes == 2, d.votes == 1], ["High", "Medium", "Low"], "None")
    d["direction"] = np.where(d.rolling_z.fillna(d.global_z) >= 0, "spike", "drop")

    drivers = _shap_drivers(forest, X, d)
    d = d.merge(drivers, on="date", how="left")

    save_model({"scaler": scaler, "forest": forest, "features": FEATURES,
                "revenue_rolling_tail": d.revenue.tail(ROLL_WINDOW).tolist(),
                "orders_rolling_tail": d.orders.tail(ROLL_WINDOW).tolist(),
                "dow_resid_mean": d.groupby(d.date.dt.dayofweek).revenue_vs_trend.mean().to_dict(),
                "global_resid_mean": float((d.revenue_vs_trend - d.groupby(d.date.dt.dayofweek).revenue_vs_trend.transform("mean")).mean()),
                "global_resid_std": float((d.revenue_vs_trend - d.groupby(d.date.dt.dayofweek).revenue_vs_trend.transform("mean")).std()),
                "iforest_threshold": float(np.quantile(d.iforest_score, 1 - CONTAMINATION)),
                "z_threshold": Z_THRESHOLD}, MODULE, "anomaly_model")
    cols = ["date", "revenue", "orders", "aov", "late_rate", "avg_review", "cancel_rate", "iforest_score", "iforest_flag",
            "rolling_z", "rolling_flag", "global_z", "zscore_flag", "votes", "is_anomaly", "severity", "direction",
            "top_driver"]
    d[cols].to_parquet(settings.processed_dir / "anomalies.parquet", index=False)
    flagged = d[d.is_anomaly][cols].sort_values("date")
    flagged.to_csv(REPORT_DIR / "anomalies_flagged.csv", index=False)
    _plot(d)
    out = {"days_scored": int(len(d)), "window": [str(d.date.min().date()), str(d.date.max().date())],
           "flags": {"iforest": int(d.iforest_flag.sum()), "rolling": int(d.rolling_flag.sum()),
                     "zscore": int(d.zscore_flag.sum()), "consensus_anomalies": int(d.is_anomaly.sum())},
           "anomalies": flagged.assign(date=flagged.date.dt.date.astype(str)).to_dict(orient="records"),
           "note": "Unsupervised: there are no labelled incidents, so precision/recall cannot be measured. "
                   "Flags are validated qualitatively (e.g. Black Friday 2017)."}
    save_json(metadata(MODULE, features=FEATURES, contamination=CONTAMINATION, rolling_window=ROLL_WINDOW,
                       z_threshold=Z_THRESHOLD), MODULE, "metadata")
    save_json(out, MODULE, "metrics")
    return out


def _shap_drivers(forest, X, d) -> pd.DataFrame:
    try:
        import shap
        sv = shap.TreeExplainer(forest).shap_values(X)
        # negative SHAP lowers the (normality) score -> pushes towards anomaly
        top = [FEATURES[i] for i in np.argmin(sv, axis=1)]
    except Exception:  # noqa: BLE001 - explanation is optional
        top = [None] * len(d)
    return pd.DataFrame({"date": d.date, "top_driver": top})


def score_observation(obs: dict, bundle: dict | None = None) -> dict:
    """Score one new daily observation with the saved detectors (used by the API)."""
    from ml.common import load_model

    b = bundle or load_model(MODULE, "anomaly_model")
    tail = np.array(obs.get("recent_revenue") or b["revenue_rolling_tail"], dtype=float)
    otail = np.array(obs.get("recent_orders") or b["orders_rolling_tail"], dtype=float)
    rev_vs_trend = float(np.log1p(obs["revenue"]) - np.median(np.log1p(tail)))
    row = pd.DataFrame([{
        "revenue_vs_trend": rev_vs_trend,
        "orders_vs_trend": float(np.log1p(obs["orders"]) - np.median(np.log1p(otail))),
        "aov": obs["revenue"] / obs["orders"] if obs["orders"] else 0.0,
        "late_rate": obs.get("late_rate", 0.0), "avg_review": obs.get("avg_review", 4.1),
        "cancel_rate": obs.get("cancel_rate", 0.0),
    }])[b["features"]]
    score = float(-b["forest"].score_samples(b["scaler"].transform(row))[0])
    rz = float((obs["revenue"] - tail.mean()) / tail.std()) if tail.std() > 0 else 0.0
    dow = pd.Timestamp(obs["date"]).dayofweek
    gz = float((rev_vs_trend - b["dow_resid_mean"][dow] - b["global_resid_mean"]) / b["global_resid_std"])
    flags = {"iforest": score > b["iforest_threshold"], "rolling": abs(rz) > b["z_threshold"],
             "zscore": abs(gz) > b["z_threshold"]}
    votes = int(sum(flags.values()))
    return {"iforest_score": round(score, 5), "rolling_z": round(rz, 3), "global_z": round(gz, 3), "flags": flags,
            "votes": votes, "is_anomaly": votes >= 2,
            "severity": {3: "High", 2: "Medium", 1: "Low"}.get(votes, "None"),
            "direction": "spike" if rz >= 0 else "drop"}


def _plot(d: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.plot(d.date, d.revenue / 1e3, color="#13294b", lw=0.9, label="Daily revenue")
    ax.plot(d.date, d.rolling_mean / 1e3, color="#94a3b8", lw=1, ls="--", label="Trailing 28-day mean")
    a = d[d.is_anomaly]
    ax.scatter(a.date, a.revenue / 1e3, color="#ef4444", s=40, zorder=5, label="Consensus anomaly (>=2 detectors)")
    ax.set_title("Daily revenue anomalies – Isolation Forest + rolling threshold + z-score (vote >= 2)")
    ax.set_ylabel("Revenue (thousand BRL)"); ax.set_xlabel("Date"); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(FIG_DIR / "anomaly_detection_revenue.png", dpi=130); plt.close(fig)


if __name__ == "__main__":
    m = train()
    print(m["flags"])
    for a in m["anomalies"]:
        print(a["date"], round(a["revenue"]), a["severity"], a["direction"], a["top_driver"])
