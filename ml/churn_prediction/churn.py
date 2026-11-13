"""B. Customer churn prediction (time-aware, leakage-safe).

Definitions
-----------
* Observation window: all revenue orders strictly BEFORE the cutoff date.
* Population at a cutoff: customers with >= 1 order in the 365 days before it.
* Label (churn = 1): NO revenue order in the 180 days starting at the cutoff.

Splits (label windows never overlap a later cutoff -> no temporal leakage)
* train      cutoff 2017-05-15 (labels to 2017-11-11)
* validation cutoff 2017-08-15 (labels to 2018-02-11) - model/threshold selection
* test       cutoff 2018-02-15 (labels to 2018-08-14) - final, untouched
The final model is refit on train+validation and evaluated once on test.
All three label windows end before 2018-08-22, the last reliable capture day.

Because ~97% of Olist customers buy only once, churn is the MAJORITY class.
We therefore also report the metrics of the minority "will return" class and
the lift over the base rate – the business-relevant view.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, confusion_matrix, f1_score, precision_score, recall_score,
                             roc_auc_score)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

from ml.common import FIG_DIR, REPORT_DIR, SEED, load_processed, metadata, save_json, save_model
from src.config.settings import settings

MODULE = "churn_prediction"
HORIZON_DAYS = 180
LOOKBACK_DAYS = 365
CUTOFFS = {"train": "2017-05-15", "validation": "2017-08-15", "test": "2018-02-15"}

NUMERIC_FEATURES = ["recency_days", "frequency", "monetary", "avg_order_value", "tenure_days", "avg_items",
                    "avg_review", "last_review", "pct_late", "avg_delivery_days", "avg_freight_ratio",
                    "max_installments", "n_categories", "days_since_first"]
CATEGORICAL_FEATURES = ["customer_region", "last_payment_type"]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

REGION = {**{s: "Norte" for s in ["AC", "AP", "AM", "PA", "RO", "RR", "TO"]},
          **{s: "Nordeste" for s in ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"]},
          **{s: "Centro-Oeste" for s in ["DF", "GO", "MT", "MS"]},
          **{s: "Sudeste" for s in ["ES", "MG", "RJ", "SP"]}, **{s: "Sul" for s in ["PR", "RS", "SC"]}}


def order_history() -> pd.DataFrame:
    om = load_processed("order_mart")
    om = om[om.is_revenue_order & (om.items_count > 0)].copy()
    om["freight_ratio"] = om.freight_value / om.items_price.replace(0, np.nan)
    return om[["customer_unique_id", "order_id", "order_purchase_timestamp", "revenue", "items_count", "review_score",
               "is_late", "delivery_days", "freight_ratio", "max_installments", "main_category", "customer_state",
               "main_payment_type"]]


def build_features(hist: pd.DataFrame, cutoff: str | pd.Timestamp, with_label: bool = True) -> pd.DataFrame:
    """Features use ONLY orders with purchase_timestamp < cutoff."""
    cutoff = pd.Timestamp(cutoff)
    past = hist[hist.order_purchase_timestamp < cutoff]
    active = past.groupby("customer_unique_id").order_purchase_timestamp.max()
    active = active[active >= cutoff - pd.Timedelta(days=LOOKBACK_DAYS)].index
    past = past[past.customer_unique_id.isin(active)].sort_values("order_purchase_timestamp")
    g = past.groupby("customer_unique_id")
    f = pd.DataFrame({
        "last_ts": g.order_purchase_timestamp.max(),
        "first_ts": g.order_purchase_timestamp.min(),
        "frequency": g.order_id.nunique(),
        "monetary": g.revenue.sum(),
        "avg_items": g.items_count.mean(),
        "avg_review": g.review_score.mean(),
        "last_review": g.review_score.last(),
        "pct_late": g.is_late.apply(lambda s: s.astype(float).mean()),
        "avg_delivery_days": g.delivery_days.mean(),
        "avg_freight_ratio": g.freight_ratio.mean(),
        "max_installments": g.max_installments.max(),
        "n_categories": g.main_category.nunique(),
        "customer_state": g.customer_state.last(),
        "last_payment_type": g.main_payment_type.last(),
    })
    f["recency_days"] = (cutoff - f.last_ts).dt.days
    f["days_since_first"] = (cutoff - f.first_ts).dt.days
    f["tenure_days"] = (f.last_ts - f.first_ts).dt.days
    f["avg_order_value"] = f.monetary / f.frequency
    f["customer_region"] = f.customer_state.map(REGION).fillna("Unknown")
    f["last_payment_type"] = f.last_payment_type.fillna("unknown")
    f["cutoff_date"] = cutoff
    f["max_feature_ts"] = f.last_ts  # kept for the leakage test
    if with_label:
        future = hist[(hist.order_purchase_timestamp >= cutoff) &
                      (hist.order_purchase_timestamp < cutoff + pd.Timedelta(days=HORIZON_DAYS))]
        returned = set(future.customer_unique_id)
        f["churn"] = (~f.index.isin(returned)).astype(int)
    return f.reset_index()


def make_pipeline(model) -> Pipeline:
    pre = ColumnTransformer([
        ("num", Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), NUMERIC_FEATURES),
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
    ])
    return Pipeline([("pre", pre), ("model", model)])


def candidate_models(pos_weight: float) -> dict:
    return {
        "logistic_regression": LogisticRegression(max_iter=2000, class_weight="balanced", C=0.5),
        "random_forest": RandomForestClassifier(n_estimators=300, min_samples_leaf=20, class_weight="balanced_subsample",
                                                n_jobs=-1, random_state=SEED),
        "xgboost": XGBClassifier(n_estimators=400, max_depth=4, learning_rate=0.05, subsample=0.8,
                                 colsample_bytree=0.8, min_child_weight=5, reg_lambda=1.0,
                                 scale_pos_weight=pos_weight, eval_metric="aucpr", random_state=SEED, n_jobs=2),
    }


def evaluate(y, p, threshold: float) -> dict:
    pred = (p >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    ret_y, ret_p = 1 - y, 1 - p   # minority class: customer returns
    base = ret_y.mean()
    top_decile = ret_p >= np.quantile(ret_p, 0.9)
    return {
        "threshold": float(threshold),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y, p)),
        "pr_auc_churn": float(average_precision_score(y, p)),
        "pr_auc_return_class": float(average_precision_score(ret_y, ret_p)),
        "return_base_rate": float(base),
        "return_lift_top_decile": float(ret_y[top_decile].mean() / base) if base > 0 else float("nan"),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "n": int(len(y)), "churn_rate": float(y.mean()),
    }


def best_threshold(y, p) -> float:
    """Threshold maximising macro-F1 (balances both classes) on validation data."""
    grid = np.linspace(0.05, 0.95, 91)
    scores = [f1_score(y, (p >= t).astype(int), average="macro", zero_division=0) for t in grid]
    return float(grid[int(np.argmax(scores))])


def train() -> dict:
    hist = order_history()
    sets = {k: build_features(hist, c) for k, c in CUTOFFS.items()}
    # leakage guard (also unit-tested)
    for k, df in sets.items():
        assert (df.max_feature_ts < pd.Timestamp(CUTOFFS[k])).all(), f"feature leakage in {k}"
    assert pd.Timestamp(CUTOFFS["validation"]) + pd.Timedelta(days=HORIZON_DAYS) <= pd.Timestamp(CUTOFFS["test"])

    tr, va, te = sets["train"], sets["validation"], sets["test"]
    pos_w = float((1 - tr.churn).sum() / max(tr.churn.sum(), 1))
    results, fitted = {}, {}
    for name, model in candidate_models(pos_w).items():
        pipe = make_pipeline(model).fit(tr[FEATURES], tr.churn)
        p_va = pipe.predict_proba(va[FEATURES])[:, 1]
        thr = best_threshold(va.churn.values, p_va)
        results[name] = {"validation": evaluate(va.churn.values, p_va, thr)}
        fitted[name] = (pipe, thr)
    # baseline: churn probability = training base rate (no skill)
    base_rate = float(tr.churn.mean())
    results["baseline_prior"] = {"validation": evaluate(va.churn.values, np.full(len(va), base_rate), 0.5)}

    best = max((n for n in fitted), key=lambda n: results[n]["validation"]["roc_auc"])
    trva = pd.concat([tr, va], ignore_index=True)
    pos_w2 = float((1 - trva.churn).sum() / max(trva.churn.sum(), 1))
    for name, model in candidate_models(pos_w2).items():
        pipe = make_pipeline(model).fit(trva[FEATURES], trva.churn)
        p_te = pipe.predict_proba(te[FEATURES])[:, 1]
        results[name]["test"] = evaluate(te.churn.values, p_te, fitted[name][1])
        fitted[name] = (pipe, fitted[name][1])
    results["baseline_prior"]["test"] = evaluate(te.churn.values, np.full(len(te), float(trva.churn.mean())), 0.5)

    final_pipe, final_thr = fitted[best]
    save_model({"pipeline": final_pipe, "threshold": final_thr, "features": FEATURES,
                "numeric_features": NUMERIC_FEATURES, "categorical_features": CATEGORICAL_FEATURES,
                "model_name": best, "horizon_days": HORIZON_DAYS}, MODULE, "churn_model")
    for name, (pipe, thr) in fitted.items():
        save_model({"pipeline": pipe, "threshold": thr, "features": FEATURES, "model_name": name}, MODULE, f"churn_{name}")

    # ---- SHAP for the XGBoost model
    shap_summary = _shap(fitted["xgboost"][0], te)

    # ---- score customers as of the last reliable day (label unknown)
    score_cutoff = pd.Timestamp("2018-08-23")
    cur = build_features(hist, score_cutoff, with_label=False)
    cur["churn_probability"] = final_pipe.predict_proba(cur[FEATURES])[:, 1]
    cur["risk_band"] = pd.cut(cur.churn_probability, [0, 0.9, 0.97, 1.0001], labels=["Medium", "High", "Very High"],
                              include_lowest=True).astype(str)
    cur["model_name"] = best
    cur[["customer_unique_id", "cutoff_date", "churn_probability", "risk_band", "model_name"] + FEATURES].to_parquet(
        settings.processed_dir / "churn_scores.parquet", index=False)
    te_out = te[["customer_unique_id", "cutoff_date", "churn"]].copy()
    te_out["churn_probability"] = final_pipe.predict_proba(te[FEATURES])[:, 1]
    te_out.to_parquet(settings.processed_dir / "churn_test_predictions.parquet", index=False)

    _plots(results, te, fitted)
    metrics = {"best_model": best, "selection_metric": "validation ROC-AUC", "cutoffs": CUTOFFS,
               "horizon_days": HORIZON_DAYS, "lookback_days": LOOKBACK_DAYS,
               "population": {k: {"customers": int(len(v)), "churn_rate": float(v.churn.mean())} for k, v in sets.items()},
               "results": results, "shap_mean_abs_top": shap_summary, "scored_customers": int(len(cur)),
               "scoring_cutoff": str(score_cutoff.date())}
    save_json(metadata(MODULE, best_model=best, features=FEATURES, cutoffs=CUTOFFS, horizon_days=HORIZON_DAYS,
                       threshold=final_thr), MODULE, "metadata")
    save_json(metrics, MODULE, "metrics")
    return metrics


def _shap(pipe: Pipeline, te: pd.DataFrame, n: int = 3000) -> list[dict]:
    try:
        import shap
    except ImportError:  # pragma: no cover
        return []
    sample = te.sample(min(n, len(te)), random_state=SEED)
    Xt = pipe.named_steps["pre"].transform(sample[FEATURES])
    names = list(pipe.named_steps["pre"].get_feature_names_out())
    from ml.common import tree_shap_values
    Xt = Xt.toarray() if hasattr(Xt, "toarray") else Xt
    sv = tree_shap_values(pipe.named_steps["model"], Xt)
    imp = pd.DataFrame({"feature": names, "mean_abs_shap": np.abs(sv).mean(axis=0)}).sort_values("mean_abs_shap", ascending=False)
    imp.to_csv(REPORT_DIR / "churn_shap_importance.csv", index=False)
    plt.figure()
    shap.summary_plot(sv, Xt, feature_names=names, show=False, max_display=15)
    plt.title("Churn model (XGBoost) – SHAP feature impact on churn probability")
    plt.tight_layout(); plt.savefig(FIG_DIR / "churn_shap_summary.png", dpi=130); plt.close()
    return imp.head(10).to_dict(orient="records")


def _plots(results: dict, te: pd.DataFrame, fitted: dict) -> None:
    from sklearn.metrics import roc_curve

    fig, ax = plt.subplots(figsize=(6.5, 5))
    for name, (pipe, _) in fitted.items():
        p = pipe.predict_proba(te[FEATURES])[:, 1]
        fpr, tpr, _ = roc_curve(te.churn, p)
        ax.plot(fpr, tpr, label=f"{name} (AUC {results[name]['test']['roc_auc']:.3f})")
    ax.plot([0, 1], [0, 1], "k--", lw=0.8, label="No skill")
    ax.set_xlabel("False positive rate"); ax.set_ylabel("True positive rate")
    ax.set_title("Churn models – ROC curves on the held-out test cutoff (2018-02-15)")
    ax.legend(fontsize=8); fig.tight_layout(); fig.savefig(FIG_DIR / "churn_roc_test.png", dpi=130); plt.close(fig)


if __name__ == "__main__":
    m = train()
    print("best:", m["best_model"])
    for k, v in m["results"].items():
        t = v["test"]
        print(f"{k:20} test ROC-AUC={t['roc_auc']:.4f} PR-AUC(churn)={t['pr_auc_churn']:.4f} "
              f"PR-AUC(return)={t['pr_auc_return_class']:.4f} lift@10%={t['return_lift_top_decile']:.2f} F1={t['f1']:.4f}")
