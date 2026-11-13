"""Shared ML utilities: data access, reliable-window detection, persistence, metrics."""
from __future__ import annotations

import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn

from src.config.settings import settings

ART = settings.ml_artifacts_dir
REPORT_DIR = settings.reports_dir / "ml"
FIG_DIR = settings.reports_dir / "figures" / "ml"
SEED = settings.random_seed


def module_dir(name: str) -> Path:
    p = ART / name
    p.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    return p


def load_processed(name: str) -> pd.DataFrame:
    return pd.read_parquet(settings.processed_dir / f"{name}.parquet")


def reliable_window(daily: pd.DataFrame, min_ratio: float = 0.7) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Return the date range where daily order capture is complete.

    Start: first day in 2017 with orders > 0 (2016 is sparse/test data).
    End:   last day whose orders >= ``min_ratio`` x trailing 28-day median
           (the source extract is truncated in late Aug 2018).
    """
    d = daily.set_index("date").orders
    d = d[d.index >= "2017-01-01"]
    start = d[d > 0].index.min()
    med = d.rolling(28, min_periods=14).median().shift(1)
    floor = 0.25 * d[d > 0].median()          # absolute floor: empty/near-empty days never qualify
    ok = (d >= min_ratio * med) & (d >= floor)
    # walk back from the end until the first "ok" day
    end = d.index.max()
    for ts in reversed(d.index):
        if ok.get(ts, False):
            end = ts
            break
    return pd.Timestamp(start), pd.Timestamp(end)


def save_model(obj: Any, module: str, name: str) -> Path:
    path = module_dir(module) / f"{name}.joblib"
    joblib.dump(obj, path)
    return path


def load_model(module: str, name: str) -> Any:
    return joblib.load(ART / module / f"{name}.joblib")


def save_json(obj: dict, module: str, name: str) -> Path:
    path = module_dir(module) / f"{name}.json"
    path.write_text(json.dumps(obj, indent=2, default=_json_default))
    return path


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (pd.Timestamp, datetime)):
        return o.isoformat()
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def metadata(module: str, **extra) -> dict:
    return {"module": module, "trained_at": datetime.now(timezone.utc).isoformat(),
            "python": platform.python_version(), "sklearn": sklearn.__version__, "random_seed": SEED, **extra}


# ------------------------------------------------------------------ metrics
def regression_metrics(y_true, y_pred) -> dict[str, float]:
    y_true, y_pred = np.asarray(y_true, float), np.asarray(y_pred, float)
    err = y_pred - y_true
    nz = y_true != 0
    return {
        "mae": float(np.mean(np.abs(err))),
        "rmse": float(np.sqrt(np.mean(err ** 2))),
        "mape_pct": float(np.mean(np.abs(err[nz] / y_true[nz])) * 100) if nz.any() else float("nan"),
        "smape_pct": float(np.mean(2 * np.abs(err) / (np.abs(y_true) + np.abs(y_pred) + 1e-9)) * 100),
        "wape_pct": float(np.sum(np.abs(err)) / max(np.sum(np.abs(y_true)), 1e-9) * 100),
        "bias": float(np.mean(err)),
        "n": int(len(y_true)),
    }


def tree_shap_values(model, X) -> "np.ndarray":
    """TreeSHAP values for an XGBoost sklearn model.

    Uses the ``shap`` package when compatible; otherwise falls back to XGBoost's native
    ``pred_contribs`` (the same TreeSHAP algorithm), which avoids known shap<->xgboost
    version incompatibilities (e.g. shap 0.49 with xgboost 3.x base_score parsing).
    """
    try:
        import shap
        return np.asarray(shap.TreeExplainer(model).shap_values(X))
    except Exception:  # noqa: BLE001
        import xgboost as xgb
        dm = xgb.DMatrix(X) if isinstance(X, pd.DataFrame) else xgb.DMatrix(np.asarray(X, dtype=float))
        contrib = model.get_booster().predict(dm, pred_contribs=True)
        return contrib[:, :-1]   # last column = bias term
