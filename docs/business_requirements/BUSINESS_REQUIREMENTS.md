# Business Requirements Document – NEXUS BI

| Item | Detail |
|---|---|
| Product | NEXUS BI – Enterprise Intelligence, Predictive Analytics & Decision Support System |
| Business | Olist marketplace (Brazilian e-commerce), public dataset, values in BRL |
| Version | 1.0 |
| Status | Implemented (see FINAL_DELIVERY_REPORT.md for verification status) |

## 1. Business context
Olist connects small Brazilian merchants to large marketplaces. Management lacks a single trusted view of revenue,
customers and logistics, and has no forward-looking signals (forecasts, churn risk, anomaly alerts).

## 2. Objectives
1. One reconciled, governed source of KPIs (SQL = Python = DAX).
2. Self-service dashboards for each leadership role.
3. Predictive signals: revenue and demand forecasts, churn risk, anomaly alerts.
4. Actionable, evidence-based recommendations with clear distinction between correlation and causation.

## 3. Stakeholders and their questions

| Stakeholder | Key questions | Delivered in |
|---|---|---|
| CEO | How fast are we growing? Where does revenue come from? What are the top risks? | Executive Overview (app), Executive Command Center (PBI), Insights report |
| CFO | Revenue, AOV, payment mix, installments, YoY/YTD, forecast for next 30 days | Revenue Intelligence, Predictive, SQL Q01–Q10, Q37–Q38 |
| Sales Manager | Which categories/sellers/regions perform? Concentration risk? | Sales Analytics, SQL Q19–Q30 |
| Marketing Manager | Who are our customers? Segments, retention, CLV, who to target? | Customer Intelligence, segmentation + churn models |
| Operations Manager | Delivery speed/reliability, late deliveries by state, cancellations, seller quality | Operations Analytics, SQL Q31–Q36, anomaly alerts |
| Customer Experience | What drives bad reviews? | Review vs delay analysis (Q40, H1), worst categories (Q41) |
| Data Analytics Team | Trustworthy data, lineage, DQ, reproducible pipeline | Data Quality page, DQ report, tests, Airflow DAG |

## 4. Functional requirements

| ID | Requirement | Implementation |
|---|---|---|
| FR-01 | Automatically discover and ingest the 9 source files | `src/ingestion/discovery.py`, `reader.py` |
| FR-02 | Validate schemas, profile data, detect nulls/duplicates/invalid values, check referential integrity | `src/validation/*`, 100 checks |
| FR-03 | Produce data dictionary and HTML DQ report | `reports/data_quality/` |
| FR-04 | Preserve raw data; repeatable, idempotent pipeline | raw files read-only; stages overwrite own outputs |
| FR-05 | Raw, staging and dimensional warehouse in PostgreSQL | `nexus_raw`, `nexus_staging`, `nexus_dw`, `nexus_ml` schemas |
| FR-06 | Star schema with explicit fact grains, SCD where appropriate | 6 dims + 4 facts; SCD2 customer, SCD1 product/seller |
| FR-07 | ≥ 40 analytical SQL queries reconciled with Python | 47 queries; 20/20 reconciliation checks |
| FR-08 | EDA notebooks with business interpretations | 5 notebooks, EDA report |
| FR-09 | Four Power BI dashboards, ≥ 30 DAX measures, RLS, incremental refresh config | PBIP: 6 pages, 80 measures, 7 roles, RangeStart/RangeEnd |
| FR-10 | Five ML modules with honest evaluation | `ml/`, MODEL_EVALUATION_REPORT.md |
| FR-11 | REST API for KPIs and predictions | FastAPI, 7 required endpoints |
| FR-12 | Interactive web application | Streamlit, 9 pages |
| FR-13 | Orchestration with retries and failure handling | Airflow DAG |
| FR-14 | Decision-support insights | BUSINESS_INSIGHTS_REPORT.md |

## 5. Non-functional requirements
* **Security:** credentials only via environment variables; RLS in Power BI and PostgreSQL; non-root container.
* **Data integrity:** primary/foreign keys and CHECK constraints in staging and warehouse; Unknown (-1) members.
* **Performance:** full pipeline ≈ 2 minutes on a 2-core machine; all SQL queries < 0.4 s after optimisation.
* **Reproducibility:** fixed random seeds; generated docs/reports; requirements + lock file.
* **Transparency:** synthetic data segregated and labelled; limitations documented.

## 6. Out of scope / assumptions
* No real cost, inventory or marketing data exists – profitability/stock-out analytics are **simulated** demonstrations.
* Currency conversion not required (all BRL).
* Cloud deployment is prepared (Docker, compose, Azure notes) but not executed.
