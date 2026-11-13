# NEXUS BI – Testing Report

_Generated 2026-11-12 15:16 UTC from `reports/tests/junit.xml` (pytest) plus the manual/environment checks listed below. Unexecuted tests are reported as NOT RUN – never as passed._

## Automated test summary (pytest)

| suite | PASS | FAIL | NOT RUN |
|---|---|---|---|
| api | 26 | 0 | 0 |
| data_quality | 8 | 0 | 0 |
| integration | 39 | 0 | 1 |
| ml | 14 | 0 | 0 |
| unit | 19 | 0 | 0 |
| TOTAL | 106 | 0 | 1 |

## Automated test detail

| suite | test | status | time_s | note |
|---|---|---|---|---|
| api | test_api::test_health_ok | PASS | 0.13 |  |
| api | test_api::test_openapi_documents_all_required_endpoints | PASS | 0.06 |  |
| api | test_api::test_business_kpis_matches_reconciled_headline | PASS | 0.24 |  |
| api | test_api::test_business_kpis_filters_and_growth | PASS | 0.04 |  |
| api | test_api::test_business_kpis_invalid_range_422 | PASS | 0.0 |  |
| api | test_api::test_business_kpis_no_match_404 | PASS | 0.01 |  |
| api | test_api::test_customer_segments_summary_and_lookup | PASS | 0.03 |  |
| api | test_api::test_customer_segments_unknown_customer_404 | PASS | 0.01 |  |
| api | test_api::test_predict_churn_valid | PASS | 0.25 |  |
| api | test_api::test_predict_churn_invalid_inputs_422[bad0] | PASS | 0.01 |  |
| api | test_api::test_predict_churn_invalid_inputs_422[bad1] | PASS | 0.0 |  |
| api | test_api::test_predict_churn_invalid_inputs_422[bad2] | PASS | 0.0 |  |
| api | test_api::test_predict_churn_invalid_inputs_422[bad3] | PASS | 0.0 |  |
| api | test_api::test_predict_churn_invalid_inputs_422[bad4] | PASS | 0.0 |  |
| api | test_api::test_predict_churn_empty_batch_422 | PASS | 0.0 |  |
| api | test_api::test_forecast_revenue_default_best | PASS | 0.01 |  |
| api | test_api::test_forecast_revenue_specific_model_and_history | PASS | 0.01 |  |
| api | test_api::test_forecast_revenue_invalid_422[payload0] | PASS | 0.0 |  |
| api | test_api::test_forecast_revenue_invalid_422[payload1] | PASS | 0.0 |  |
| api | test_api::test_forecast_revenue_invalid_422[payload2] | PASS | 0.0 |  |
| api | test_api::test_forecast_demand_valid_and_case_insensitive | PASS | 0.01 |  |
| api | test_api::test_forecast_demand_unknown_category_404 | PASS | 0.0 |  |
| api | test_api::test_detect_anomaly_normal_and_extreme | PASS | 0.39 |  |
| api | test_api::test_detect_anomaly_invalid_422 | PASS | 0.01 |  |
| api | test_api::test_model_metrics_unknown_module_404 | PASS | 0.0 |  |
| api | test_api::test_missing_artifact_returns_503 | PASS | 0.0 |  |
| data_quality | test_processed_data::test_primary_keys_unique | PASS | 0.24 |  |
| data_quality | test_processed_data::test_referential_integrity | PASS | 2.52 |  |
| data_quality | test_processed_data::test_raw_rows_preserved | PASS | 0.0 |  |
| data_quality | test_processed_data::test_domain_rules | PASS | 0.1 |  |
| data_quality | test_processed_data::test_order_mart_no_fanout | PASS | 0.16 |  |
| data_quality | test_processed_data::test_one_latest_review_per_order | PASS | 0.03 |  |
| data_quality | test_processed_data::test_synthetic_data_is_labelled | PASS | 0.04 |  |
| data_quality | test_processed_data::test_headline_kpis_consistent | PASS | 0.0 |  |
| integration | test_powerbi_and_app::test_powerbi_static_validation_passes | PASS | 6.13 |  |
| integration | test_powerbi_and_app::test_dax_library_has_required_functions_and_30_plus_measures | PASS | 0.0 |  |
| integration | test_powerbi_and_app::test_rls_roles_defined | PASS | 0.0 |  |
| integration | test_powerbi_and_app::test_dag_task_chain_without_airflow | PASS | 0.0 |  |
| integration | test_powerbi_and_app::test_dag_parses_in_airflow | NOT RUN | 0.0 | Airflow not installed in this environment |
| integration | test_powerbi_and_app::test_streamlit_page_renders_without_exception[1_Executive_Overview.py] | PASS | 2.74 |  |
| integration | test_powerbi_and_app::test_streamlit_page_renders_without_exception[2_Revenue_Intelligence.py] | PASS | 1.55 |  |
| integration | test_powerbi_and_app::test_streamlit_page_renders_without_exception[3_Sales_Analytics.py] | PASS | 2.82 |  |
| integration | test_powerbi_and_app::test_streamlit_page_renders_without_exception[4_Customer_Intelligence.py] | PASS | 2.91 |  |
| integration | test_powerbi_and_app::test_streamlit_page_renders_without_exception[5_Operations_Analytics.py] | PASS | 1.49 |  |
| integration | test_powerbi_and_app::test_streamlit_page_renders_without_exception[6_Predictive_Analytics.py] | PASS | 1.63 |  |
| integration | test_powerbi_and_app::test_streamlit_page_renders_without_exception[7_Anomaly_Monitoring.py] | PASS | 1.29 |  |
| integration | test_powerbi_and_app::test_streamlit_page_renders_without_exception[8_Data_Quality.py] | PASS | 1.38 |  |
| integration | test_powerbi_and_app::test_streamlit_page_renders_without_exception[9_System_Monitoring.py] | PASS | 1.51 |  |
| integration | test_spark_parity::test_geolocation_parity | PASS | 25.7 |  |
| integration | test_spark_parity::test_daily_revenue_parity | PASS | 2.22 |  |
| integration | test_warehouse::test_no_duplicate_keys[fact_orders-order_id] | PASS | 0.03 |  |
| integration | test_warehouse::test_no_duplicate_keys[fact_order_items-order_id, order_item_id] | PASS | 0.22 |  |
| integration | test_warehouse::test_no_duplicate_keys[fact_payments-order_id, payment_sequential] | PASS | 0.43 |  |
| integration | test_warehouse::test_no_duplicate_keys[fact_reviews-review_id, order_id] | PASS | 0.48 |  |
| integration | test_warehouse::test_no_duplicate_keys[dim_customer-customer_key] | PASS | 0.01 |  |
| integration | test_warehouse::test_no_duplicate_keys[dim_product-product_id] | PASS | 0.01 |  |
| integration | test_warehouse::test_no_duplicate_keys[dim_seller-seller_id] | PASS | 0.0 |  |
| integration | test_warehouse::test_no_duplicate_keys[dim_date-date_key] | PASS | 0.0 |  |
| integration | test_warehouse::test_no_duplicate_keys[dim_location-zip_code_prefix] | PASS | 0.0 |  |
| integration | test_warehouse::test_no_orphan_or_unknown_keys[fact_orders-customer_key-dim_customer-customer_key] | PASS | 0.04 |  |
| integration | test_warehouse::test_no_orphan_or_unknown_keys[fact_orders-purchase_date_key-dim_date-date_key] | PASS | 0.01 |  |
| integration | test_warehouse::test_no_orphan_or_unknown_keys[fact_order_items-product_key-dim_product-product_key] | PASS | 0.03 |  |
| integration | test_warehouse::test_no_orphan_or_unknown_keys[fact_order_items-seller_key-dim_seller-seller_key] | PASS | 0.02 |  |
| integration | test_warehouse::test_no_orphan_or_unknown_keys[fact_payments-payment_type_key-dim_payment_type-payment_type_key] | PASS | 0.01 |  |
| integration | test_warehouse::test_surrogate_keys_positive_except_unknown | PASS | 0.0 |  |
| integration | test_warehouse::test_scd2_customer_versions_are_contiguous | PASS | 0.1 |  |
| integration | test_warehouse::test_fact_grain_no_fanout | PASS | 0.14 |  |
| integration | test_warehouse::test_sql_python_reconciliation_all_pass | PASS | 0.54 |  |
| integration | test_warehouse::test_query_library_runs_and_has_40_plus | PASS | 4.38 |  |
| integration | test_warehouse::test_sql_matches_python_for_category_and_state | PASS | 0.25 |  |
| integration | test_warehouse::test_materialized_views_populated | PASS | 0.01 |  |
| integration | test_warehouse::test_ml_tables_published | PASS | 0.03 |  |
| integration | test_warehouse::test_incremental_fact_reload_is_idempotent | PASS | 4.27 |  |
| integration | test_warehouse::test_scd2_merge_adds_version_for_moved_customer | PASS | 0.06 |  |
| ml | test_models::test_churn_features_use_only_history | PASS | 7.55 |  |
| ml | test_models::test_churn_label_windows_do_not_overlap_later_cutoffs | PASS | 0.01 |  |
| ml | test_models::test_churn_label_depends_on_future_only | PASS | 0.01 |  |
| ml | test_models::test_xgb_revenue_features_respect_horizon | PASS | 0.38 |  |
| ml | test_models::test_churn_models_beat_no_skill_baseline_on_ranking | PASS | 0.0 |  |
| ml | test_models::test_revenue_backtest_metrics_and_best_model_selection | PASS | 0.0 |  |
| ml | test_models::test_forecast_intervals_contain_point_forecast | PASS | 0.0 |  |
| ml | test_models::test_demand_backtest_includes_baselines | PASS | 0.0 |  |
| ml | test_models::test_segmentation_quality_and_coverage | PASS | 0.06 |  |
| ml | test_models::test_anomaly_detector_flags_black_friday | PASS | 0.01 |  |
| ml | test_models::test_anomaly_scoring_function | PASS | 0.18 |  |
| ml | test_models::test_regression_metrics | PASS | 0.0 |  |
| ml | test_models::test_reliable_window_excludes_truncated_tail | PASS | 0.01 |  |
| ml | test_models::test_artifacts_and_metadata_exist | PASS | 0.0 |  |
| unit | test_ingestion_validation::test_discovery_matches_all_and_rejects_missing | PASS | 0.0 |  |
| unit | test_ingestion_validation::test_schema_validation_missing_column | PASS | 0.0 |  |
| unit | test_ingestion_validation::test_cast_counts_failures_and_keeps_zip_as_text | PASS | 0.01 |  |
| unit | test_ingestion_validation::test_bom_header_is_handled | PASS | 0.0 |  |
| unit | test_ingestion_validation::test_quality_rules | PASS | 0.0 |  |
| unit | test_ingestion_validation::test_check_result_status_mapping | PASS | 0.0 |  |
| unit | test_transformations::test_strip_accents_and_city_normalisation | PASS | 0.0 |  |
| unit | test_transformations::test_zip_zero_padding | PASS | 0.0 |  |
| unit | test_transformations::test_category_normalisation | PASS | 0.0 |  |
| unit | test_transformations::test_date_key | PASS | 0.0 |  |
| unit | test_transformations::test_orders_delivery_metrics_and_flags | PASS | 0.01 |  |
| unit | test_transformations::test_order_items_invalid_amounts_dropped | PASS | 0.0 |  |
| unit | test_transformations::test_payments_installments_floor | PASS | 0.0 |  |
| unit | test_transformations::test_reviews_latest_flag_and_sentiment | PASS | 0.01 |  |
| unit | test_transformations::test_products_translation_and_unknown | PASS | 0.01 |  |
| unit | test_transformations::test_geolocation_aggregation_and_bounds | PASS | 0.02 |  |
| unit | test_transformations::test_category_translation_appends_manual | PASS | 0.0 |  |
| unit | test_transformations::test_customers_transform_keeps_keys | PASS | 0.0 |  |
| unit | test_transformations::test_headline_kpis_and_daily_gap_fill | PASS | 0.04 |  |

## Compatibility run: Python 3.10 + pandas 2.3 (target workstation's interpreter)

| Tests | PASS | FAIL | NOT RUN |
|---|---|---|---|
| unit, api, ml, data_quality, Power BI/DAG/Streamlit | 79 | 0 | 2 |

Full no-DB pipeline (`--skip-db`) also completed on 3.10 with identical KPIs (R$ 15,735,527.03) and model results (churn ROC-AUC 0.5824, k = 3, 7 anomalies). Source: `reports/tests/junit_py310.xml`.

## Defects found by testing and fixed

| # | Found by | Defect | Fix |
|---|---|---|---|
| 1 | Warehouse FK constraint | `shipping_limit_date` values in 2020 outside `dim_date` | dim_date range derived from data; DQ check added |
| 2 | Reconciliation (rows) | Surrogate key 0 issued after the −1 Unknown row | `GREATEST(max(key), 0)`; DB rebuilt |
| 3 | Query timing | Q27 correlated subquery took 266 s | Window-function rewrite (0.18 s) |
| 4 | Data review | Data capture truncated after 2018-08-22 distorted forecasts | `reliable_window()` with absolute floor |
| 5 | Result review | Anomaly detector flagged business growth (Jan-2017) | Trend-relative features + warm-up |
| 6 | Screenshot review | Growth +30,263% vs sparse 2016 base; % and BRL formats | Growth only vs fully-captured periods; formats fixed |
| 7 | Airflow `dags test` | pandas 3.1 object dtype broke demand plot | Explicit float casting |
| 8 | pytest (API) | Models pickled in Airflow venv not loadable elsewhere (`dill`) | Retrain in serving env; documented |
| 9 | Spark parity test | Accent stripping differed from pandas for 1 zip | Reuse pandas function via broadcast map |
| 10 | Python 3.10 run | shap 0.49 ↔ xgboost 3.x incompatibility | Native XGBoost TreeSHAP fallback |
| 11 | Python 3.10 run | nullable boolean aggregation under pandas 2.x | Explicit integer flags |

## Environment / end-to-end checks

| check | status | evidence |
|---|---|---|
| Airflow DagBag parse (Airflow 3.1.8 venv) | PASS | reports/tests/junit_airflow.xml – 0 import errors, 9 tasks |
| airflow dags test nexus_bi_pipeline (end-to-end) | PASS | DagRun state=success; 8 tasks success, send_failure_status skipped (2nd run). 1st run exposed a pandas-3.1 dtype bug in demand forecasting, fixed. |
| Airflow scheduler with live schedule | NOT RUN | Only `dags test` executed; no scheduler/worker deployment |
| Full pipeline CLI (python -m src.pipeline --stage all stages) | PASS | logs/pipeline_runs.jsonl |
| Python 3.10 + pandas 2.3 compatibility (no-DB pipeline + 79 tests) | PASS | reports/tests/junit_py310.xml |
| SQL ↔ Python reconciliation | PASS | 20/20 – reports/sql_results/_reconciliation.csv |
| SQL library execution (47 queries) | PASS | reports/sql_results/_query_catalog.csv |
| Notebooks executed (nbconvert, 5) | PASS | 0 error outputs |
| FastAPI live server (uvicorn) /health | PASS | status=ok, 5/5 models loaded |
| Streamlit live server + headless Chrome screenshots | PASS | docs/user_manual/screenshots/*.png |
| Power BI static validation + DAX logic recomputation | PASS | reports/powerbi_validation.json |
| Power BI Desktop open/refresh/render | NOT RUN | Power BI Desktop unavailable in build environment (Linux) |
| docker compose config | PASS | compose file valid; services db, api, app, pipeline |
| Docker image build | NOT RUN | Docker Hub blocked by network policy (403 on registry-1.docker.io) |
| Azure deployment | NOT RUN | No subscription/credentials; design + commands documented |
| Windows execution of scripts/nexus.ps1 | NOT RUN | Build ran on Linux; see FINAL_DELIVERY_REPORT for Windows checks |
| PySpark 4.3 jobs ↔ pandas parity | PASS | tests/integration/test_spark_parity.py (in main suite) |
