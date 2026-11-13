# NEXUS BI – Model Evaluation Report
_Generated automatically from `ml/artifacts/*/metrics.json` on 2026-11-13 05:34 UTC. All numbers are measured on the Olist dataset; none are hand-entered._

## A. Customer segmentation (RFM + K-Means)

- Customers segmented: **94,983** (snapshot 2018-09-04)
- Selected k = **3** (max silhouette within k=3..8); silhouette = **0.3966**

| k | inertia | silhouette |
|---|---|---|
| 2 | 193,512 | 0.7157 |
| 3 | 130,815 | 0.3966 |
| 4 | 84,572 | 0.3920 |
| 5 | 69,847 | 0.3519 |
| 6 | 59,676 | 0.3512 |
| 7 | 52,084 | 0.3474 |
| 8 | 46,235 | 0.3432 |
| 9 | 41,388 | 0.3444 |
| 10 | 37,074 | 0.3394 |

| Cluster | Customers | Customer % | Revenue % | Median recency (d) | Mean frequency | Median monetary (BRL) | Strategy |
|---|---|---|---|---|---|---|---|
| Recent One-Time Buyers | 24,029 | 25.3% | 26.01% | 65 | 1.00 | 111.17 | Drive the 2nd order: post-delivery cross-sell within 30-60 days, review request, free-shipping threshold. |
| Lapsed One-Time Buyers | 68,067 | 71.66% | 68.33% | 284 | 1.00 | 103.86 | Low-cost automated win-back (email/push) on the category bought; exclude from paid retargeting. |
| Loyal Repeat Buyers | 2,887 | 3.04% | 5.66% | 207 | 2.11 | 225.55 | Protect: VIP perks, early access, referral programme; monitor for lapses. |

## B. Churn prediction

- Churn = no revenue order within **180 days** after the cutoff; population = customers active in the prior 365 days.
- Cutoffs: train `2017-05-15`, validation `2017-08-15`, test `2018-02-15` (label windows never overlap later cutoffs).
- Selected model (by validation ROC-AUC): **random_forest**

| Split | Customers | Churn rate |
|---|---|---|
| train | 9,145 | 0.9852 |
| validation | 19,941 | 0.9837 |
| test | 51,262 | 0.9881 |

**Held-out test results (cutoff 2018-02-15)**

| Model | ROC-AUC | PR-AUC (churn) | PR-AUC (return class) | Return lift @ top 10% | Precision | Recall | F1 | Threshold |
|---|---|---|---|---|---|---|---|---|
| logistic_regression | 0.5805 | 0.9908 | 0.0243 | 2.01x | 0.9888 | 0.9816 | 0.9852 | 0.36 |
| random_forest | 0.5824 | 0.9905 | 0.0220 | 1.85x | 0.9886 | 0.9867 | 0.9876 | 0.56 |
| xgboost | 0.5742 | 0.9902 | 0.0197 | 1.86x | 0.9886 | 0.9755 | 0.9820 | 0.32 |
| baseline_prior | 0.5000 | 0.9881 | 0.0119 | 1.00x | 0.9881 | 1.0000 | 0.9940 | 0.50 |

Confusion matrix (random_forest, test): TN=35 FP=577 FN=675 TP=49,975

Top SHAP drivers (XGBoost): `num__recency_days`, `num__days_since_first`, `num__avg_freight_ratio`, `num__avg_order_value`, `num__monetary`, `num__max_installments`

> **Interpretation.** Only ~1–2% of active customers return within 180 days, so a constant 'everyone churns' prediction already scores high F1/PR-AUC for the churn class. The models' real value is ranking: the top decile of predicted returners contains **1.8x** the base return rate. Discrimination is modest (ROC-AUC 0.582); the model is suitable for prioritising retention campaigns, **not** for individual-level decisions, and is not production-ready without richer behavioural data (browsing, marketing touches).

## C. Revenue forecasting (daily, 30-day horizon)

- Series: 2017-01-05 → 2018-08-21 (594 days, reliable capture window).
- Rolling-origin backtest: 4 folds × 30 days.
- Best model by backtest MAE: **ensemble_mean**

| Model | MAE (BRL) | RMSE (BRL) | MAPE % | sMAPE % | Bias (BRL) |
|---|---|---|---|---|---|
| ensemble_mean | 7,823 | 9,855 | 23.2 | 22.5 | -3,040 |
| seasonal_naive | 8,089 | 10,133 | 24.8 | 23.8 | -2,115 |
| xgboost | 8,325 | 10,553 | 24.5 | 24.6 | -3,284 |
| sarima | 8,499 | 10,725 | 24.6 | 24.2 | -3,722 |

Next-30-day revenue total by model (BRL): ensemble_mean 1,103,114, sarima 1,047,946, seasonal_naive 1,136,857, xgboost 1,124,539

> The three single models are within ~5% MAE of each other and the seasonal-naive baseline is hard to beat; the simple ensemble is the most robust choice. MAPE is valid here (no zero-revenue days in the window).

## D. Demand forecasting (weekly units, top categories, 4-week horizon)

- Categories: auto, bed_bath_table, computers_accessories, furniture_decor, garden_tools, health_beauty, housewares, sports_leisure, telephony, watches_gifts
- Weeks 2017-01-09 → 2018-08-13; 4 rolling origins.
- Best model by WAPE: **naive**

| Model | WAPE % | MAE (units) | RMSE (units) | n |
|---|---|---|---|---|
| naive | 25.7 | 29.6 | 39.1 | 160 |
| moving_avg_4w | 26.8 | 30.9 | 39.4 | 160 |
| xgboost | 29.2 | 33.6 | 44.8 | 160 |
| seasonal_naive_52w | 51.2 | 59.0 | 73.7 | 160 |

> Seasonal naive (52w) only covers 2018 target weeks; one seasonal cycle available. XGBoost does not beat the naive baseline at this horizon; the naive forecast is the recommended production default until more history is available.

## E. Anomaly detection (daily KPIs)

- Days scored: 566 (2017-02-02 → 2018-08-21).
- Flags: Isolation Forest 12, rolling threshold 6, z-score 8; **consensus (≥2 votes): 7**

| Date | Revenue (BRL) | Orders | Severity | Direction | Top SHAP driver |
|---|---|---|---|---|---|
| 2017-02-03 | 11,400 | 56 | Medium | spike | cancel_rate |
| 2017-02-04 | 15,717 | 66 | Medium | spike | revenue_vs_trend |
| 2017-06-21 | 7,272 | 35 | Medium | drop | orders_vs_trend |
| 2017-11-24 | 178,378 | 1166 | High | spike | revenue_vs_trend |
| 2017-11-25 | 71,858 | 499 | Medium | spike | orders_vs_trend |
| 2017-12-24 | 6,709 | 58 | Medium | drop | orders_vs_trend |
| 2018-02-26 | 49,962 | 293 | Medium | spike | late_rate |

> Unsupervised: there are no labelled incidents, so precision/recall cannot be measured. Flags are validated qualitatively (e.g. Black Friday 2017).
