# Interview Preparation – NEXUS BI

## 60-second pitch
"I built NEXUS BI, an end-to-end analytics platform on the Olist e-commerce dataset – about 100k orders and 1.5M source
rows. A Python ETL validates the data with 100 automated checks and loads a PostgreSQL star schema with an SCD Type 2
customer dimension. 47 SQL queries cover growth, cohorts, CLV and logistics, and every headline KPI is reconciled between
SQL, Python and DAX – 20 out of 20 checks match to the cent. On top I trained five models – segmentation, churn,
revenue and demand forecasting, anomaly detection – served them through FastAPI, built a 9-page Streamlit app and a
Power BI project with 80 measures and row-level security, and orchestrated it with an Airflow DAG I tested end-to-end.
The headline finding: the business is acquisition-only – 3% of customers ever reorder – and late deliveries cut ratings
from 4.3 to 1.7 stars, so logistics reliability and a second-purchase programme are the two biggest levers."

## Numbers to remember (all computed)
| Fact | Value |
|---|---|
| Revenue (price + freight, excl. canceled/unavailable) | R$ 15.74 M |
| Orders / customers / AOV | 98,207 / 94,990 / R$ 160.23 |
| On-time delivery / avg delivery | 93.2% / 12.6 days (median 10.2) |
| Repeat-customer rate / month-1 retention | 3.04% / 0.48% |
| Review on-time vs > 15 days late | 4.29 vs 1.73 |
| Top 5% sellers' GMV share | 53% |
| SP share of revenue | 37% |
| Jan–Aug 2018 vs 2017 | +140% (but flat during 2018) |
| Churn model | ROC-AUC ≈ 0.58, ~2× top-decile lift |
| Revenue forecast (ensemble) | MAE ≈ R$ 7.8k/day, MAPE ≈ 23% |

## Likely questions & strong answers

**Why is `customer_unique_id` important?** Olist creates a new `customer_id` for every order; counting it would report
~99k "customers" and a 0% repeat rate. I model the person (`customer_unique_id`) and keep the order-scoped id in a bridge
table mapped to the SCD2 version valid at order time.

**How did you avoid double counting?** Explicit fact grains: order-level money only in `fact_orders`, item-level only in
`fact_order_items`, payments in their own fact. Views aggregate each fact at its own grain before joining. A test asserts
`fact_orders.items_price` equals the sum of its items for every order.

**How do you know the numbers are right?** Two independent implementations (SQL procedures vs pandas marts) plus DAX
logic re-computed on the Power BI extracts; 13 KPIs and 7 raw→staging→warehouse row counts reconcile exactly.

**What data quality issues did you find?** No PK/FK violations, but: 775 orders without items, 166 carrier dates before
purchase, shipping limits in 2020, 262k duplicate geolocation rows, 610 products without category, two untranslated
categories, review ids reused across orders, and capture truncation after 2018-08-22. Each is handled explicitly and logged.

**Explain your churn design.** Cutoff-based: features strictly before the cutoff, label = no purchase in the next 180 days.
Train/validation/test cutoffs are spaced so no label window overlaps a later cutoff. I selected on validation and
evaluated once on test. Results are modest; with 98.8% churn the right metric is lift on the minority "returns" class,
not accuracy or churn-class F1 – the no-skill baseline actually has the best churn F1.

**Why did simple forecasts win?** ~600 days of a fast-growing series with one Black Friday; a weekly seasonal-naive
captures most signal. I used rolling-origin backtesting, direct (lag ≥ 30) features to avoid leakage, and an ensemble
that beat every single model. Reporting that honestly is more useful than overfitting.

**SCD Type 2 implementation?** Full loads rebuild versions with window functions (LAG to detect address change, running
SUM to number versions, LEAD for `valid_to`). Incremental loads use a merge procedure that closes the current version and
opens a new one; tested by inserting a moved customer inside a rolled-back transaction.

**SQL optimisation example?** A correlated subquery (category average per product) took 266 s; rewriting with
`avg() OVER (PARTITION BY category)` gave identical results in 0.18 s. Plus partial/BRIN indexes and materialized views.

**DAX you can explain?** `[Revenue Running Total]` (CALCULATE + FILTER + ALL over dates), `[Repeat Customers]` (FILTER over
customers with CALCULATE(COUNTROWS) > 1), `[Share of Region Revenue]` (ALLEXCEPT), `[Deliveries by Delivery Date]`
(USERELATIONSHIP on an inactive relationship), dynamic RLS with USERPRINCIPALNAME and a mapping table, a field parameter.

**What would you do next?** Add marketing/web data to improve churn, carrier data for root-causing late deliveries,
A/B test the second-purchase programme, publish to Power BI Service with incremental refresh, deploy to Azure Container Apps.

**What are the limitations?** Power BI PBIP generated and statically validated but not opened in Desktop; Docker build and
cloud deploy not executed; synthetic cost/inventory are demonstrations only; correlations are not causal.

## Correlation vs causation statements to use
* "Late orders are associated with 2-point lower reviews (Mann-Whitney, r = 0.64). It is plausible lateness causes it,
  but a randomised delivery-promise test would be needed to quantify the causal effect."
* "Installments correlate with higher order values – likely selection (expensive items → installments), not causation."
