# NEXUS BI – Final Delivery Report

**Delivered to:** `C:\Users\91705\Nexus_bi\NEXUS-BI` · **Build date:** 2026-11-12
**Status legend:** PASS = executed and verified · NOT RUN = not executed (reason given) · never "passed" without execution.

## 1. Implemented modules

| # | Module | Status | Evidence |
|---|---|---|---|
| 1 | Project structure, config, logging | Done | `src/config`, `src/logging`, `logs/pipeline_runs.jsonl` |
| 2 | Ingestion, schema validation, profiling, data dictionary | Done · PASS | `reports/data_quality/*.csv`, `docs/database/DATA_DICTIONARY.md` |
| 3 | Data quality (100 checks), cleaning, HTML DQ report | Done · PASS | `reports/data_quality/data_quality_report.html` |
| 4 | PostgreSQL warehouse (raw/staging/dw/ml, star schema, SCD1/SCD2, procedures, views, MVs, RLS, incremental) | Done · PASS | `sql/`, 20 warehouse integration tests |
| 5 | 47 SQL queries + SQL↔Python reconciliation | Done · PASS (47/47, 20/20) | `reports/sql_results/` |
| 6 | 5 executed notebooks, EDA report, hypothesis tests | Done · PASS | `notebooks/`, `reports/eda/EDA_REPORT.md` |
| 7 | Power BI PBIP (TMDL + PBIR), 80 DAX measures, M scripts, theme, RLS, incremental-refresh parameters | Generated · static validation PASS · **Desktop NOT RUN** | `powerbi/`, `reports/powerbi_validation.json` |
| 8 | ML: segmentation, churn, revenue & demand forecasting, anomaly detection, SHAP | Done · PASS | `ml/`, `reports/ml/MODEL_EVALUATION_REPORT.md` |
| 9 | FastAPI (7 required endpoints + 2 helpers) | Done · PASS | 26 API tests, live `/health` |
| 10 | Streamlit (9 pages, dark/light) | Done · PASS | 9 page tests, screenshots |
| 11 | Airflow DAG | Done · PASS (`airflow dags test` → success) | `orchestration/` |
| 12 | Optional PySpark jobs | Done · PASS (parity with pandas) | `src/transformation/spark_jobs.py` |
| 7a | Power BI accessibility: English alt text + reading-order tab order on all 58 visuals | Done · re-scan 0 issues | `docs/user_manual/POWERBI_USER_GUIDE.md` §Accessibility |
| 13 | Business insights report | Done | `docs/business_requirements/BUSINESS_INSIGHTS_REPORT.md` |
| 14 | Documentation (15 required docs + guides) | Done | `docs/`, `README.md` |
| 15 | Docker / compose / Makefile / PowerShell runner | Done · compose PASS · image build NOT RUN | root files, `scripts/nexus.ps1` |

## 2. Files created
≈ 420 project files excluding data (≈ 8,000 lines of Python, 1,600 lines of SQL), plus generated data:
`data/staging` (typed + clean parquet), `data/processed` (marts, forecasts, 18 Power BI CSV extracts), `data/synthetic`,
`data/sample` (2,000-order sample), `ml/artifacts` (11 model files), `reports/` (DQ, EDA, ML, SQL results, tests, 22 figures).

## 3. Dataset records processed

| Dataset | Source rows | After cleaning / in warehouse |
|---|---|---|
| customers | 99,441 | 99,441 customer_ids → 96,355 customer versions (96,096 people) |
| orders | 99,441 | 99,441 (`fact_orders`) |
| order_items | 112,650 | 112,650 (`fact_order_items`) |
| payments | 103,886 | 103,886 (`fact_payments`) |
| reviews | 99,224 | 99,224 (`fact_reviews`) |
| products | 32,951 | 32,951 (`dim_product`) |
| sellers | 3,095 | 3,095 (`dim_seller`) |
| geolocation | 1,000,163 | 19,011 zip prefixes (after removing 279,694 duplicates, 27 out-of-Brazil points) |
| category_translation | 71 | 74 (+ 2 manual translations + `unknown`) |
| **Total** | **1,550,922** | |

## 4. Actual model metrics (held-out / backtest)

| Model | Metric(s) |
|---|---|
| Segmentation (K-Means, k = 3) | silhouette 0.3966 · Lapsed One-Time Buyers 68,067 · Recent One-Time Buyers 24,029 · Loyal Repeat Buyers 2,887 |
| Churn – Random Forest (selected) | test ROC-AUC 0.5824 · PR-AUC(churn) 0.9906 · PR-AUC(return) 0.0213 · return lift @10% 2.01× · P 0.9887 · R 0.9771 · F1 0.9829 |
| Churn – Logistic Regression | ROC-AUC 0.5805 · lift 2.01× · F1 0.9852 |
| Churn – XGBoost | ROC-AUC 0.5721 · lift 1.80× · F1 0.9732 |
| Churn – no-skill baseline | ROC-AUC 0.5000 · F1 0.9940 (majority class) |
| Revenue – ensemble (selected) | MAE R$ 7,820 · RMSE R$ 9,795 · MAPE 23.2% |
| Revenue – seasonal naive / SARIMA / XGBoost | MAE 8,089 / 8,499 / 8,416 · MAPE 24.8 / 24.6 / 24.9% |
| Demand – naive (selected) | WAPE 25.7% (MA-4w 26.8%, XGBoost 28.6%, seasonal-52w 51.2%) |
| Anomaly detection | 7 consensus anomalies (Black Friday 2017-11-24 = High); IF 12, rolling 6, z-score 8 flags |

**Production readiness:** churn – **not** production-ready for individual decisions (prioritisation only); forecasts –
usable as planning baselines with stated error; anomaly detection – unsupervised, no labelled incidents for precision/recall.

## 5. Tests

| Run | PASS | FAIL | NOT RUN |
|---|---|---|---|
| Main suite, Python 3.13 + PostgreSQL (unit 19, data-quality 8, integration 40, API 26, ML 14) | 106 | 0 | 1 (Airflow parse – run separately below) |
| Airflow DagBag parse (Airflow 3.1.8 venv) | 1 | 0 | 0 |
| Compatibility: Python 3.10 + pandas 2.3 (no DB) | 79 | 0 | 2 (DB-only Power BI check, Airflow) |
| End-to-end `airflow dags test` | PASS | | |
| Power BI static validation (9 checks) | 9 | 0 | 0 |

**Not run:** Power BI Desktop open/refresh/render · Docker image build (registry blocked) · Azure deployment · live Airflow
scheduler · execution of `scripts/nexus.ps1` on Windows (build ran on Linux) · PostgreSQL on your PC (not installed).
Full detail and the 11 defects found-and-fixed by testing: `docs/TESTING_REPORT.md`.

## 6. Known limitations
1. Power BI PBIP not opened in Desktop; PBIR schema versions may need Desktop to upgrade/repair (fallback documented). No PBIX shipped.
2. Churn signal is weak (ROC-AUC 0.58) because ~97% of customers buy once and no behavioural data exists.
3. Advanced forecasters barely beat seasonal-naive; ensemble/naive recommended.
4. Source capture truncated after 2018-08-22; 2016 contains only test-like volume.
5. Profitability and inventory analytics use **synthetic** data (labelled) – not business findings.
6. ML artifacts are environment-specific pickles; retrain after changing library versions (`nexus.ps1 train`).
7. Airflow is Linux-only (WSL2/Docker on Windows).
8. API has no authentication (add Azure AD / API gateway before exposing publicly).

## 7. Remaining manual steps (your PC)
1. Install **PostgreSQL 16** (or Docker Desktop) and **Power BI Desktop** – neither is currently installed.
2. `.\scripts\nexus.ps1 setup` → edit `.env` (DB password) → create role/database → `init-db` → `pipeline`.
3. Open `powerbi\NexusBI.pbip`, refresh, validate against the expected values in the Power BI User Guide, do the 4
   manual finishing steps (drill-through field, tooltip page, anomaly filter, incremental-refresh policy), save as PBIX.
4. Optional: push to GitHub (`.gitignore` already excludes secrets, raw data and generated artifacts).

## 8. Exact commands (Windows PowerShell, from `C:\Users\91705\Nexus_bi\NEXUS-BI`)

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\nexus.ps1 setup            # 1. install dependencies (creates .venv with Python 3.10+)
.\scripts\nexus.ps1 init-db          # 2. initialise the database (after creating role/db, editing .env)
.\scripts\nexus.ps1 pipeline         # 3. run ETL + warehouse + SQL + ML + publish  (no DB: pipeline-no-db)
.\scripts\nexus.ps1 api              # 4. API  → http://localhost:8000/docs
.\scripts\nexus.ps1 app              # 5. app  → http://localhost:8501
.\scripts\nexus.ps1 powerbi          # 6. regenerate PBIP for this path, then: start .\powerbi\NexusBI.pbip
.\scripts\nexus.ps1 test             #    run the test suite
```
The delivered copy already contains processed data, trained models and Power BI extracts, so `api`/`app` work right after
`setup` – but because model files are environment-specific, run `.\scripts\nexus.ps1 train` once first (≈ 1 min, no DB needed).
