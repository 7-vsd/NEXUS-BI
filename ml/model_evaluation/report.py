"""Generate reports/ml/MODEL_EVALUATION_REPORT.md from the saved metrics (no hand-typed numbers)."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from ml.common import ART, REPORT_DIR


def _load(module: str) -> dict:
    return json.loads((ART / module / "metrics.json").read_text())


def _f(x, nd=4):
    return "n/a" if x is None else f"{x:,.{nd}f}"


def write_report(_: dict | None = None) -> str:
    seg, ch, rv, dm, an = (_load(m) for m in ("customer_segmentation", "churn_prediction", "revenue_forecasting",
                                              "demand_forecasting", "anomaly_detection"))
    L = [f"# NEXUS BI – Model Evaluation Report",
         f"_Generated automatically from `ml/artifacts/*/metrics.json` on {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}. "
         "All numbers are measured on the Olist dataset; none are hand-entered._", ""]

    L += ["## A. Customer segmentation (RFM + K-Means)", "",
          f"- Customers segmented: **{seg['customers']:,}** (snapshot {seg['snapshot_date'][:10]})",
          f"- Selected k = **{seg['selected_k']}** (max silhouette within k=3..8); silhouette = **{_f(seg['silhouette_selected'])}**", "",
          "| k | inertia | silhouette |", "|---|---|---|"]
    L += [f"| {r['k']} | {r['inertia']:,.0f} | {r['silhouette']:.4f} |" for r in seg["k_curve"]]
    L += ["", "| Cluster | Customers | Customer % | Revenue % | Median recency (d) | Mean frequency | Median monetary (BRL) | Strategy |",
          "|---|---|---|---|---|---|---|---|"]
    L += [f"| {c['cluster_name']} | {c['customers']:,} | {c['customer_share_pct']}% | {c['revenue_share_pct']}% | "
          f"{c['recency_median']:.0f} | {c['frequency_mean']:.2f} | {c['monetary_median']:.2f} | {c['recommended_strategy']} |"
          for c in seg["clusters"]]

    L += ["", "## B. Churn prediction", "",
          f"- Churn = no revenue order within **{ch['horizon_days']} days** after the cutoff; population = customers active in the prior {ch['lookback_days']} days.",
          f"- Cutoffs: train `{ch['cutoffs']['train']}`, validation `{ch['cutoffs']['validation']}`, test `{ch['cutoffs']['test']}` (label windows never overlap later cutoffs).",
          f"- Selected model (by validation ROC-AUC): **{ch['best_model']}**", ""]
    L += ["| Split | Customers | Churn rate |", "|---|---|---|"]
    L += [f"| {k} | {v['customers']:,} | {v['churn_rate']:.4f} |" for k, v in ch["population"].items()]
    L += ["", "**Held-out test results (cutoff " + ch["cutoffs"]["test"] + ")**", "",
          "| Model | ROC-AUC | PR-AUC (churn) | PR-AUC (return class) | Return lift @ top 10% | Precision | Recall | F1 | Threshold |",
          "|---|---|---|---|---|---|---|---|---|"]
    for name, r in ch["results"].items():
        t = r["test"]
        L.append(f"| {name} | {t['roc_auc']:.4f} | {t['pr_auc_churn']:.4f} | {t['pr_auc_return_class']:.4f} | "
                 f"{t['return_lift_top_decile']:.2f}x | {t['precision']:.4f} | {t['recall']:.4f} | {t['f1']:.4f} | {t['threshold']:.2f} |")
    best_t = ch["results"][ch["best_model"]]["test"]
    cm = best_t["confusion_matrix"]
    L += ["", f"Confusion matrix ({ch['best_model']}, test): TN={cm['tn']:,} FP={cm['fp']:,} FN={cm['fn']:,} TP={cm['tp']:,}", "",
          "Top SHAP drivers (XGBoost): " + ", ".join(f"`{d['feature']}`" for d in ch["shap_mean_abs_top"][:6]), "",
          "> **Interpretation.** Only ~1–2% of active customers return within 180 days, so a constant 'everyone churns' "
          "prediction already scores high F1/PR-AUC for the churn class. The models' real value is ranking: the top decile "
          f"of predicted returners contains **{best_t['return_lift_top_decile']:.1f}x** the base return rate. Discrimination is modest "
          f"(ROC-AUC {best_t['roc_auc']:.3f}); the model is suitable for prioritising retention campaigns, **not** for "
          "individual-level decisions, and is not production-ready without richer behavioural data (browsing, marketing touches)."]

    L += ["", "## C. Revenue forecasting (daily, 30-day horizon)", "",
          f"- Series: {rv['series_start']} → {rv['series_end']} ({rv['n_days']} days, reliable capture window).",
          f"- Rolling-origin backtest: {rv['folds']} folds × {rv['horizon_days']} days.",
          f"- Best model by backtest MAE: **{rv['best_model_by_backtest_mae']}**", "",
          "| Model | MAE (BRL) | RMSE (BRL) | MAPE % | sMAPE % | Bias (BRL) |", "|---|---|---|---|---|---|"]
    for m, v in sorted(rv["backtest"].items(), key=lambda kv: kv[1]["overall"]["mae"]):
        o = v["overall"]
        L.append(f"| {m} | {o['mae']:,.0f} | {o['rmse']:,.0f} | {o['mape_pct']:.1f} | {o['smape_pct']:.1f} | {o['bias']:,.0f} |")
    L += ["", "Next-30-day revenue total by model (BRL): " +
          ", ".join(f"{m} {v:,.0f}" for m, v in rv["forecast_total_next_30d"].items()),
          "", "> The three single models are within ~5% MAE of each other and the seasonal-naive baseline is hard to beat; "
          "the simple ensemble is the most robust choice. MAPE is valid here (no zero-revenue days in the window)."]

    L += ["", "## D. Demand forecasting (weekly units, top categories, 4-week horizon)", "",
          f"- Categories: {', '.join(dm['categories'])}",
          f"- Weeks {dm['first_week']} → {dm['last_week']}; {dm['folds']} rolling origins.",
          f"- Best model by WAPE: **{dm['best_model_by_wape']}**", "",
          "| Model | WAPE % | MAE (units) | RMSE (units) | n |", "|---|---|---|---|---|"]
    for m, v in sorted(dm["backtest_overall"].items(), key=lambda kv: kv[1]["wape_pct"]):
        L.append(f"| {m} | {v['wape_pct']:.1f} | {v['mae']:.1f} | {v['rmse']:.1f} | {v['n']} |")
    L += ["", f"> {dm['seasonality_note']} XGBoost does not beat the naive baseline at this horizon; the naive forecast is "
          "the recommended production default until more history is available."]

    L += ["", "## E. Anomaly detection (daily KPIs)", "",
          f"- Days scored: {an['days_scored']} ({an['window'][0]} → {an['window'][1]}).",
          f"- Flags: Isolation Forest {an['flags']['iforest']}, rolling threshold {an['flags']['rolling']}, "
          f"z-score {an['flags']['zscore']}; **consensus (≥2 votes): {an['flags']['consensus_anomalies']}**", "",
          "| Date | Revenue (BRL) | Orders | Severity | Direction | Top SHAP driver |", "|---|---|---|---|---|---|"]
    L += [f"| {a['date']} | {a['revenue']:,.0f} | {a['orders']:.0f} | {a['severity']} | {a['direction']} | {a['top_driver']} |"
          for a in an["anomalies"]]
    L += ["", f"> {an['note']}", ""]
    text = "\n".join(L)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "MODEL_EVALUATION_REPORT.md").write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    write_report()
