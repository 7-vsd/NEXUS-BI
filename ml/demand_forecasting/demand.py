"""D. Product demand forecasting – weekly units for the top product categories.

Aggregation: category x ISO week (Mon-start), units = order lines of
revenue-recognised orders. Category level is used because 73% of products sell
fewer than 3 units in the whole dataset – product-level series are too sparse
to forecast meaningfully.

Horizon 4 weeks; rolling-origin backtest with 4 origins (4 weeks apart).
Models: Naive (last week), Moving Average (4w), Seasonal Naive (52w, available
for 2018 target weeks), XGBoost global model (all categories, lags >= horizon,
week-of-year seasonality, category code). Metric: WAPE (robust to low volumes),
plus MAE/RMSE. Intervals: empirical residual quantiles from the backtest.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from ml.common import FIG_DIR, REPORT_DIR, SEED, load_processed, metadata, regression_metrics, reliable_window, save_json, save_model
from src.config.settings import settings

MODULE = "demand_forecasting"
TOP_N = 10
HORIZON = 4
N_FOLDS = 4
LAGS = [4, 5, 6, 8, 12, 52]


def load_panel() -> pd.DataFrame:
    cw = load_processed("category_weekly")
    start, end = reliable_window(load_processed("daily_kpis"))
    first_week = (start + pd.offsets.Week(weekday=0)).normalize()          # first full Monday-week
    last_week = (end - pd.Timedelta(days=6) - pd.offsets.Week(weekday=0)).normalize() if end.dayofweek != 6 else (end - pd.Timedelta(days=6)).normalize()
    top = cw[(cw.week >= first_week) & (cw.week <= last_week)].groupby("category").units.sum().nlargest(TOP_N).index
    weeks = pd.date_range(first_week, last_week, freq="W-MON")
    grid = pd.MultiIndex.from_product([top, weeks], names=["category", "week"]).to_frame(index=False)
    panel = grid.merge(cw[["category", "week", "units"]], on=["category", "week"], how="left").fillna({"units": 0})
    return panel.sort_values(["category", "week"]).reset_index(drop=True)


def _features(panel: pd.DataFrame, cats: list[str]) -> pd.DataFrame:
    p = panel.copy()
    g = p.groupby("category").units
    for lag in LAGS:
        p[f"lag_{lag}"] = g.shift(lag)
    p["roll4_lag4"] = g.shift(HORIZON).rolling(4).mean().reset_index(level=0, drop=True)
    p["weekofyear"] = p.week.dt.isocalendar().week.astype(int).values
    p["month"] = p.week.dt.month
    p["cat_code"] = p.category.map({c: i for i, c in enumerate(cats)})
    p["is_bf_week"] = ((p.week.dt.month == 11) & (p.week.dt.day.between(20, 29))).astype(int)
    return p


FEATS = [f"lag_{l}" for l in LAGS] + ["roll4_lag4", "weekofyear", "month", "cat_code", "is_bf_week"]


def make_xgb() -> XGBRegressor:
    return XGBRegressor(n_estimators=400, max_depth=4, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8,
                        objective="reg:squarederror", random_state=SEED, n_jobs=2)


def forecast_from_origin(panel: pd.DataFrame, origin: pd.Timestamp, cats: list[str]) -> pd.DataFrame:
    """Forecast weeks origin+1..origin+HORIZON using data up to and including origin."""
    hist = panel[panel.week <= origin]
    fut_weeks = pd.date_range(origin + pd.Timedelta(weeks=1), periods=HORIZON, freq="W-MON")
    fut = pd.MultiIndex.from_product([cats, fut_weeks], names=["category", "week"]).to_frame(index=False)
    fut["units"] = np.nan
    full = pd.concat([hist, fut], ignore_index=True).sort_values(["category", "week"])
    feats = _features(full, cats)
    train = feats[(feats.week <= origin)].dropna(subset=["lag_4", "lag_8", "roll4_lag4"])
    model = make_xgb().fit(train[FEATS], np.log1p(train.units))
    test = feats[feats.week.isin(fut_weeks)].copy()
    test["xgboost"] = np.clip(np.expm1(model.predict(test[FEATS])), 0, None)
    last = hist.groupby("category").units.last()
    ma4 = hist.groupby("category").units.apply(lambda s: s.tail(4).mean())
    test["naive"] = test.category.map(last)
    test["moving_avg_4w"] = test.category.map(ma4)
    s52 = panel.set_index(["category", "week"]).units
    test["seasonal_naive_52w"] = pd.to_numeric(pd.Series([s52.get((c, w - pd.Timedelta(weeks=52)), np.nan)
                                                          for c, w in zip(test.category, test.week)], index=test.index),
                                               errors="coerce").astype(float)
    test["horizon"] = ((test.week - origin).dt.days // 7).astype(int)
    test["origin"] = origin
    return test, model


def train() -> dict:
    panel = load_panel()
    cats = list(panel.category.unique())
    weeks = sorted(panel.week.unique())
    rows, model = [], None
    for k in range(N_FOLDS, 0, -1):
        origin = pd.Timestamp(weeks[len(weeks) - 1 - k * HORIZON])
        test, model = forecast_from_origin(panel, origin, cats)
        actual = panel.set_index(["category", "week"]).units
        test["actual"] = [actual.get((c, w)) for c, w in zip(test.category, test.week)]
        test["fold"] = N_FOLDS - k + 1
        rows.append(test)
    bt = pd.concat(rows, ignore_index=True)
    models = ["naive", "moving_avg_4w", "seasonal_naive_52w", "xgboost"]
    long = bt.melt(id_vars=["category", "week", "fold", "origin", "horizon", "actual"], value_vars=models,
                   var_name="model", value_name="predicted")
    long[["predicted", "actual"]] = long[["predicted", "actual"]].apply(pd.to_numeric, errors="coerce").astype(float)
    long = long.dropna(subset=["predicted", "actual"])
    metrics = {m: regression_metrics(g.actual, g.predicted) for m, g in long.groupby("model")}
    by_cat = (long.groupby(["model", "category"])
                  .apply(lambda g: pd.Series({"wape_pct": regression_metrics(g.actual, g.predicted)["wape_pct"],
                                              "mae": regression_metrics(g.actual, g.predicted)["mae"]}), include_groups=False)
                  .reset_index())
    best = min(metrics, key=lambda m: metrics[m]["wape_pct"])

    # future forecast from the last observed week
    last_origin = pd.Timestamp(weeks[-1])
    fut, final_model = forecast_from_origin(panel, last_origin, cats)
    resid = (long[long.model == best].actual - long[long.model == best].predicted)
    lo_q, hi_q = resid.quantile(0.025), resid.quantile(0.975)
    fut_long = fut.melt(id_vars=["category", "week", "horizon"], value_vars=models, var_name="model",
                        value_name="predicted")
    fut_long["predicted"] = pd.to_numeric(fut_long.predicted, errors="coerce").astype(float)
    fut_long = fut_long.dropna(subset=["predicted"])
    fut_long["lower_95"] = np.clip(fut_long.predicted + lo_q, 0, None)
    fut_long["upper_95"] = fut_long.predicted + hi_q
    fut_long["is_best_model"] = fut_long.model == best

    save_model({"model": final_model, "features": FEATS, "categories": cats, "lags": LAGS,
                "trained_until": last_origin}, MODULE, "xgboost_demand")
    panel.to_parquet(settings.processed_dir / "demand_panel.parquet", index=False)
    long.to_parquet(settings.processed_dir / "demand_backtest.parquet", index=False)
    fut_long.to_parquet(settings.processed_dir / "demand_forecast.parquet", index=False)
    by_cat.to_csv(REPORT_DIR / "demand_backtest_by_category.csv", index=False)
    _plot(panel, fut_long, best, cats[:4])

    out = {"categories": cats, "horizon_weeks": HORIZON, "folds": N_FOLDS, "best_model_by_wape": best,
           "backtest_overall": metrics, "first_week": str(pd.Timestamp(weeks[0]).date()),
           "last_week": str(last_origin.date()),
           "seasonality_note": "Seasonal naive (52w) only covers 2018 target weeks; one seasonal cycle available."}
    save_json(metadata(MODULE, best_model=best, categories=cats, features=FEATS), MODULE, "metadata")
    save_json(out, MODULE, "metrics")
    return out


def _plot(panel, fut, best, cats) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(11, 6), sharex=True)
    for ax, c in zip(axes.ravel(), cats):
        h = panel[panel.category == c]
        f = fut[(fut.category == c) & (fut.model == best)]
        ax.plot(h.week.to_numpy(), h.units.to_numpy(float), color="#13294b", lw=1)
        ax.plot(f.week.to_numpy(), f.predicted.to_numpy(float), color="#ef4444", marker="o", ms=3)
        ax.fill_between(f.week.to_numpy(), f.lower_95.to_numpy(float), f.upper_95.to_numpy(float), color="#ef4444", alpha=0.15)
        ax.set_title(c.replace("_", " ").title(), fontsize=9); ax.set_ylabel("Units / week")
    fig.suptitle(f"Weekly category demand and 4-week forecast ({best}, 95% interval)")
    fig.tight_layout(); fig.savefig(FIG_DIR / "demand_forecast_top_categories.png", dpi=130); plt.close(fig)


if __name__ == "__main__":
    m = train()
    print("best:", m["best_model_by_wape"], m["first_week"], "->", m["last_week"])
    for k, v in m["backtest_overall"].items():
        print(f"{k:20} WAPE={v['wape_pct']:.1f}% MAE={v['mae']:.1f} RMSE={v['rmse']:.1f} n={v['n']}")
