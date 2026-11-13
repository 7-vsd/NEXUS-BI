"""C. Daily revenue forecasting – 30-day horizon.

Series: daily revenue (BRL, revenue-recognised orders) over the reliable capture
window detected by ``ml.common.reliable_window`` (2017-01-05 .. 2018-08-22).

Models
* Seasonal Naive (weekly): y(t+h) = y(t+h-7k) using the last observed week.
* SARIMA: SARIMAX on log1p(revenue), order (1,1,1) x seasonal (1,0,1,7).
* Ensemble: simple mean of the three models above.
* XGBoost (direct, leakage-free): features are calendar variables and lags
  >= 30 days, so every feature is known at the forecast origin for all
  horizons 1..30 – no recursive error accumulation and no look-ahead.

Validation: rolling-origin backtest with 4 folds, each forecasting the next 30
days from an origin, origins 30 days apart, ending at the last reliable day.
Prediction intervals: SARIMA native 95% interval; Seasonal Naive and XGBoost use
empirical 2.5/97.5% quantiles of their backtest residuals.
"""
from __future__ import annotations

import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX
from xgboost import XGBRegressor

from ml.common import FIG_DIR, REPORT_DIR, SEED, load_processed, metadata, regression_metrics, reliable_window, save_json, save_model
from src.config.settings import settings

MODULE = "revenue_forecasting"
HORIZON = 30
N_FOLDS = 4
SARIMA_ORDER = (1, 1, 1)
SARIMA_SEASONAL = (1, 0, 1, 7)
LAGS = [30, 31, 35, 42, 49, 56, 63, 91]


def load_series() -> pd.Series:
    daily = load_processed("daily_kpis")
    start, end = reliable_window(daily)
    s = daily.set_index("date").revenue.loc[start:end].asfreq("D").fillna(0.0)
    s.name = "revenue"
    return s


# ---------------------------------------------------------------- models
def seasonal_naive(train: pd.Series, horizon: int, season: int = 7) -> np.ndarray:
    last = train.values[-season:]
    return np.array([last[i % season] for i in range(horizon)])


def sarima_fit_predict(train: pd.Series, horizon: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, object]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = SARIMAX(np.log1p(train), order=SARIMA_ORDER, seasonal_order=SARIMA_SEASONAL,
                      enforce_stationarity=False, enforce_invertibility=False).fit(disp=False, maxiter=200)
        fc = res.get_forecast(horizon)
        mean = np.expm1(fc.predicted_mean.values)
        ci = fc.conf_int(alpha=0.05).values
    return np.clip(mean, 0, None), np.clip(np.expm1(ci[:, 0]), 0, None), np.expm1(ci[:, 1]), res


def calendar_features(idx: pd.DatetimeIndex) -> pd.DataFrame:
    f = pd.DataFrame(index=idx)
    f["dow"] = idx.dayofweek
    f["dom"] = idx.day
    f["month"] = idx.month
    f["weekofyear"] = idx.isocalendar().week.astype(int).values
    f["is_weekend"] = (idx.dayofweek >= 5).astype(int)
    bf = pd.to_datetime([f"{y}-11-{d}" for y in idx.year.unique() for d in range(23, 30)])
    bf = bf[bf.dayofweek == 4]
    f["is_black_friday"] = idx.isin(bf).astype(int)
    f["days_to_black_friday"] = [min([abs((d - b).days) for b in bf] or [365]) for d in idx]
    f["is_bf_week"] = (f.days_to_black_friday <= 3).astype(int)
    f["t"] = (idx - pd.Timestamp("2017-01-01")).days
    return f


def xgb_design(series: pd.Series, index: pd.DatetimeIndex) -> pd.DataFrame:
    """Design matrix for the given dates using only values >= 30 days old."""
    full_idx = pd.date_range(series.index.min(), index.max(), freq="D")
    s = series.reindex(full_idx)
    X = calendar_features(full_idx)
    for lag in LAGS:
        X[f"lag_{lag}"] = s.shift(lag)
    X["roll7_lag30"] = s.shift(30).rolling(7).mean()
    X["roll28_lag30"] = s.shift(30).rolling(28).mean()
    X["roll7_dow_lag35"] = s.shift(35)  # same weekday 5 weeks earlier
    return X.loc[index]


def make_xgb() -> XGBRegressor:
    return XGBRegressor(n_estimators=500, max_depth=4, learning_rate=0.03, subsample=0.8, colsample_bytree=0.8,
                        min_child_weight=3, objective="reg:squarederror", random_state=SEED, n_jobs=2)


def xgb_fit_predict(train: pd.Series, horizon: int):
    idx_tr = train.index[max(LAGS) + 28:]
    X_tr = xgb_design(train, idx_tr)
    model = make_xgb().fit(X_tr, np.log1p(train.loc[idx_tr]))
    fut = pd.date_range(train.index.max() + pd.Timedelta(days=1), periods=horizon, freq="D")
    X_f = xgb_design(train, fut)
    return np.clip(np.expm1(model.predict(X_f)), 0, None), model, X_f


# ---------------------------------------------------------------- backtest
def backtest(series: pd.Series) -> tuple[pd.DataFrame, dict]:
    end = len(series)
    rows = []
    for k in range(N_FOLDS, 0, -1):
        origin = end - k * HORIZON
        train, test = series.iloc[:origin], series.iloc[origin:origin + HORIZON]
        preds = {
            "seasonal_naive": seasonal_naive(train, len(test)),
            "sarima": sarima_fit_predict(train, len(test))[0],
            "xgboost": xgb_fit_predict(train, len(test))[0],
        }
        preds["ensemble_mean"] = np.mean([preds["seasonal_naive"], preds["sarima"], preds["xgboost"]], axis=0)
        for m, p in preds.items():
            for i, (d, y) in enumerate(test.items()):
                rows.append({"fold": N_FOLDS - k + 1, "origin": train.index.max(), "date": d, "horizon": i + 1,
                             "model": m, "actual": y, "predicted": float(p[i])})
    bt = pd.DataFrame(rows)
    metrics = {}
    for m, g in bt.groupby("model"):
        metrics[m] = {"overall": regression_metrics(g.actual, g.predicted),
                      "by_fold": {int(f): regression_metrics(x.actual, x.predicted) for f, x in g.groupby("fold")}}
    return bt, metrics


def train() -> dict:
    series = load_series()
    bt, bt_metrics = backtest(series)
    best = min(bt_metrics, key=lambda m: bt_metrics[m]["overall"]["mae"])

    # empirical residual quantiles from backtest (for SN & XGB intervals)
    bt["residual"] = bt.actual - bt.predicted
    q = bt.groupby("model").residual.quantile([0.025, 0.975]).unstack()

    fut_idx = pd.date_range(series.index.max() + pd.Timedelta(days=1), periods=HORIZON, freq="D")
    sn = seasonal_naive(series, HORIZON)
    sa_mean, sa_lo, sa_hi, sa_res = sarima_fit_predict(series, HORIZON)
    xg, xgb_model, X_future = xgb_fit_predict(series, HORIZON)
    en = np.mean([sn, sa_mean, xg], axis=0)
    fut = []
    for m, p, lo, hi in [("seasonal_naive", sn, sn + q.loc["seasonal_naive", 0.025], sn + q.loc["seasonal_naive", 0.975]),
                         ("sarima", sa_mean, sa_lo, sa_hi),
                         ("xgboost", xg, xg + q.loc["xgboost", 0.025], xg + q.loc["xgboost", 0.975]),
                         ("ensemble_mean", en, en + q.loc["ensemble_mean", 0.025], en + q.loc["ensemble_mean", 0.975])]:
        for d, a, b, c in zip(fut_idx, p, np.clip(lo, 0, None), hi):
            fut.append({"date": d, "model": m, "predicted": float(a), "lower_95": float(b), "upper_95": float(c),
                        "is_best_model": m == best})
    fut = pd.DataFrame(fut)

    # persist
    save_model({"model": xgb_model, "lags": LAGS, "trained_until": series.index.max()}, MODULE, "xgboost_revenue")
    save_model({"result": sa_res, "order": SARIMA_ORDER, "seasonal_order": SARIMA_SEASONAL,
                "trained_until": series.index.max()}, MODULE, "sarima_revenue")
    series.to_frame().to_parquet(settings.processed_dir / "revenue_series.parquet")
    bt.to_parquet(settings.processed_dir / "revenue_backtest.parquet", index=False)
    fut.to_parquet(settings.processed_dir / "revenue_forecast.parquet", index=False)
    _shap(xgb_model, X_future)
    _plot(series, bt, fut, best)

    metrics = {"series_start": str(series.index.min().date()), "series_end": str(series.index.max().date()),
               "n_days": int(len(series)), "horizon_days": HORIZON, "folds": N_FOLDS,
               "best_model_by_backtest_mae": best, "backtest": bt_metrics,
               "interval_method": {"sarima": "model 95% CI", "seasonal_naive": "empirical backtest residual quantiles",
                                   "xgboost": "empirical backtest residual quantiles",
                                   "ensemble_mean": "empirical backtest residual quantiles"},
               "forecast_total_next_30d": {m: float(g.predicted.sum()) for m, g in fut.groupby("model")}}
    save_json(metadata(MODULE, best_model=best, sarima_order=SARIMA_ORDER, sarima_seasonal=SARIMA_SEASONAL,
                       xgb_lags=LAGS, series_end=metrics["series_end"]), MODULE, "metadata")
    save_json(metrics, MODULE, "metrics")
    return metrics


def _shap(model, X: pd.DataFrame) -> None:
    from ml.common import tree_shap_values
    sv = tree_shap_values(model, X)
    pd.DataFrame({"feature": X.columns, "mean_abs_shap": np.abs(sv).mean(axis=0)}).sort_values(
        "mean_abs_shap", ascending=False).to_csv(REPORT_DIR / "revenue_xgb_shap_importance.csv", index=False)


def _plot(series, bt, fut, best) -> None:
    fig, ax = plt.subplots(figsize=(11, 4.8))
    hist = series.loc[series.index.max() - pd.Timedelta(days=180):]
    ax.plot(hist.index, hist.values / 1e3, color="#13294b", lw=1.2, label="Actual daily revenue")
    colors = {"seasonal_naive": "#94a3b8", "sarima": "#14b8a6", "xgboost": "#f59e0b", "ensemble_mean": "#8b5cf6"}
    for m, g in bt.groupby("model"):
        ax.plot(g.date, g.predicted / 1e3, color=colors[m], lw=0.9, alpha=0.8, label=f"Backtest – {m}")
    fb = fut[fut.model == best]
    ax.plot(fb.date, fb.predicted / 1e3, color="#ef4444", lw=1.8, label=f"30-day forecast – {best}")
    ax.fill_between(fb.date.to_numpy(), fb.lower_95.to_numpy(float) / 1e3, fb.upper_95.to_numpy(float) / 1e3, color="#ef4444", alpha=0.15, label="95% interval")
    ax.set_title("Daily revenue: rolling-origin backtest (4 x 30 days) and 30-day forecast")
    ax.set_ylabel("Revenue (thousand BRL)"); ax.set_xlabel("Date"); ax.legend(fontsize=7, ncol=2)
    fig.tight_layout(); fig.savefig(FIG_DIR / "revenue_forecast_backtest.png", dpi=130); plt.close(fig)


if __name__ == "__main__":
    m = train()
    print(m["series_start"], "->", m["series_end"], "best:", m["best_model_by_backtest_mae"])
    for k, v in m["backtest"].items():
        o = v["overall"]
        print(f"{k:16} MAE={o['mae']:.0f} RMSE={o['rmse']:.0f} MAPE={o['mape_pct']:.1f}% bias={o['bias']:.0f}")
