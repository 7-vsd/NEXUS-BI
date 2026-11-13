# Machine Learning Model Documentation – NEXUS BI

All metrics are in the auto-generated **[MODEL_EVALUATION_REPORT.md](../../reports/ml/MODEL_EVALUATION_REPORT.md)**
(built from `ml/artifacts/*/metrics.json`). This document describes design, assumptions and usage.
Train everything: `python -m ml.train_all` (≈ 60 s on 2 cores). Seeds fixed via `NEXUS_RANDOM_SEED`.

| Module | Code | Artifacts | Consumers |
|---|---|---|---|
| A. Customer segmentation | `ml/customer_segmentation/segmentation.py` | `kmeans_rfm.joblib`, metrics, `customer_segments.parquet` | API `/api/customer-segments`, app, PBI, `nexus_ml.customer_segments` |
| B. Churn prediction | `ml/churn_prediction/churn.py` | `churn_model.joblib` (+ each candidate), SHAP csv/png, `churn_scores.parquet` | API `/api/predict-churn`, app, PBI |
| C. Revenue forecasting | `ml/revenue_forecasting/forecast.py` | `xgboost_revenue.joblib`, `sarima_revenue.joblib`, backtest + forecast parquet | API `/api/forecast-revenue`, app, PBI |
| D. Demand forecasting | `ml/demand_forecasting/demand.py` | `xgboost_demand.joblib`, backtest + forecast parquet | API `/api/forecast-demand`, app, PBI |
| E. Anomaly detection | `ml/anomaly_detection/anomaly.py` | `anomaly_model.joblib`, `anomalies.parquet` | API `/api/detect-anomaly`, `/api/anomalies`, app, PBI |

## A. Segmentation
* Unit: `customer_unique_id` with ≥ 1 revenue order with items (94,983 customers). Snapshot = last order date + 1.
* Features: log1p(recency, frequency, monetary), standardised. k = 2..10 evaluated (inertia + silhouette on a seeded
  15k sample); k chosen as max silhouette within 3..8 (actionable range). Selected **k = 3**.
* Naming rule (from centroids): mean frequency ≥ 1.5 → "Loyal Repeat Buyers"; otherwise Recent/Lapsed by median
  recency, with a High/Low-Value qualifier only when median spend differs ≥ 20% from the overall median.
* Rule-based RFM segments (7) are produced as well, using the same rules as SQL Q17 / `mv_customer_rfm`.

## B. Churn (time-aware, leakage-safe)
* Churn = no revenue order in the **180 days** after a cutoff; population = customers active in the previous 365 days.
* Cutoffs: train 2017-05-15 · validation 2017-08-15 · test 2018-02-15. Label windows never overlap a later cutoff;
  the test label window ends before the last reliable capture day. Features use only orders strictly before the cutoff
  (`max_feature_ts < cutoff` asserted in code and tests).
* Candidates: Logistic Regression, Random Forest, XGBoost (class-weighted) + a no-skill prior baseline. Model selected
  on validation ROC-AUC, threshold on validation macro-F1, refit on train+validation, evaluated once on test.
* **Result:** discrimination is modest (test ROC-AUC ≈ 0.58) – the dataset has ~1 order per customer and no behavioural
  data. Because 98.8% of customers churn, F1/PR-AUC of the churn class look high even for the baseline; the
  meaningful metric is the **return-class lift (~2× in the top decile)**. Not production-ready for individual decisions.
* SHAP (XGBoost): recency, average order value, freight ratio, installments, monetary and delivery days dominate.

## C. Revenue forecasting (30 days)
* Daily revenue over the reliable window 2017-01-05 → 2018-08-21.
* Models: seasonal naive (weekly), SARIMA(1,1,1)(1,0,1,7) on log1p, XGBoost **direct** model using only lags ≥ 30
  days + calendar/Black-Friday features (no recursion, no look-ahead), and an equal-weight ensemble.
* Validation: rolling origin, 4 folds × 30 days. Metrics MAE, RMSE, MAPE (valid – no zero days), sMAPE, bias.
* Intervals: SARIMA native 95%; others empirical 2.5/97.5% backtest residual quantiles.
* **Result:** single models within ~5% MAE of each other; the ensemble is best (MAE ≈ R$ 7.8k/day, MAPE ≈ 23%).

## D. Demand forecasting (4 weeks)
* Weekly units per top-10 category (73% of products sell < 3 units, so SKU-level forecasting is not meaningful).
* Models: naive, 4-week moving average, 52-week seasonal naive, global XGBoost (lags ≥ 4 weeks).
* **Result:** naive is best (WAPE ≈ 26%); XGBoost does not beat it with ~85 weeks of history. Naive is the recommended default.

## E. Anomaly detection
* Daily KPIs (revenue & orders as log-deviation from the trailing 28-day median, AOV, late rate, review, cancel rate).
  Trend-relative inputs prevent growth from being flagged; first 28 days are warm-up.
* Detectors: Isolation Forest (2% contamination), rolling 28-day z-score on revenue (|z| > 3), detrended weekday-adjusted
  global z-score (|z| > 3). Anomaly = ≥ 2 votes; severity by votes. SHAP identifies the top driver per day.
* Unsupervised – no labelled incidents exist, so precision/recall cannot be measured; validated qualitatively
  (Black Friday 2017 = High severity).

## Retraining & monitoring
* Retrain via the pipeline (`predict` stage / Airflow task `generate_predictions`). Metadata (`trained_at`, library
  versions, seed, chosen model) in `ml/artifacts/<module>/metadata.json`; the app's System Monitoring page shows model age.
* Recommended production monitoring: forecast error vs actuals (Power BI measure `[Forecast MAPE]`), churn lift on a
  randomised holdout, anomaly alert volume.
