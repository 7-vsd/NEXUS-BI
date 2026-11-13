# NEXUS BI – SQL Query Documentation

_Generated 2026-11-12 15:16 UTC. Runtime/rows were measured on the loaded warehouse (PostgreSQL 16, 99,441 orders)._

Run all: `python -m src.analytics.sql_runner` → results in `reports/sql_results/<query_id>.csv`.

## Techniques covered

CTEs, window functions (LAG, RANK, DENSE_RANK, NTILE, PERCENT_RANK, running SUM, ROWS/RANGE frames), correlated & scalar subqueries, percentile_cont, FILTER clauses, self-joins (YoY), generate_series gap filling, cohort analysis, materialized views, EXPLAIN ANALYZE.

## Optimisation case study (Q27)

The first version of Q27 used a correlated subquery (category average recomputed per product in both SELECT and HAVING). Measured runtime: **266 s**. Rewriting it with a single window function (`avg(price) OVER (PARTITION BY category)`) computed once in a CTE returned identical rows in **0.25 s**.

Other optimisations: partial index `ix_fo_revenue_only` (most queries filter `is_revenue_order`), BRIN index on `purchase_timestamp`, materialized views for daily KPIs / monthly category sales / RFM (Q46, Q47 show the plans).

## SQL ↔ Python reconciliation

| check | sql_value | python_value | abs_diff | tolerance | status | detail |
|---|---|---|---|---|---|---|
| kpi:total_revenue | 15735527.03 | 15735527.03 | 0.0 | 15.735527029999998 | PASS |  |
| kpi:product_revenue | 13494400.74 | 13494400.74 | 0.0 | 13.49440074 | PASS |  |
| kpi:freight_revenue | 2241126.29 | 2241126.29 | 0.0 | 2.24112629 | PASS |  |
| kpi:total_orders | 98207.0 | 98207.0 | 0.0 | 0.0 | PASS |  |
| kpi:all_orders | 99441.0 | 99441.0 | 0.0 | 0.0 | PASS |  |
| kpi:unique_customers | 94990.0 | 94990.0 | 0.0 | 0.0 | PASS |  |
| kpi:average_order_value | 160.23 | 160.23 | 0.0 | 0.011 | PASS |  |
| kpi:total_payment_value | 16008872.12 | 16008872.12 | 0.0 | 16.00887212 | PASS |  |
| kpi:cancellation_rate | 0.006285 | 0.006285 | 0.0 | 0.011 | PASS |  |
| kpi:on_time_delivery_rate | 0.932269 | 0.932269 | 0.0 | 0.011 | PASS |  |
| kpi:avg_delivery_days | 12.5582 | 12.5582 | 0.0 | 0.011 | PASS |  |
| kpi:avg_review_score | 4.0864 | 4.0864 | 0.0 | 0.011 | PASS |  |
| kpi:items_sold | 112101.0 | 112101.0 | 0.0 | 0.0 | PASS |  |
| rows:orders | 99441.0 | 99441.0 | 0.0 | 0.0 | PASS | raw=99441 staging=99441 warehouse=99441 |
| rows:order_items | 112650.0 | 112650.0 | 0.0 | 0.0 | PASS | raw=112650 staging=112650 warehouse=112650 |
| rows:payments | 103886.0 | 103886.0 | 0.0 | 0.0 | PASS | raw=103886 staging=103886 warehouse=103886 |
| rows:reviews | 99224.0 | 99224.0 | 0.0 | 0.0 | PASS | raw=99224 staging=99224 warehouse=99224 |
| rows:products | 32951.0 | 32951.0 | 0.0 | 0.0 | PASS | raw=32951 staging=32951 warehouse=32951 |
| rows:sellers | 3095.0 | 3095.0 | 0.0 | 0.0 | PASS | raw=3095 staging=3095 warehouse=3095 |
| rows:customer_ids | 99441.0 | 99441.0 | 0.0 | 0.0 | PASS | raw=99441 staging=99441 warehouse=99441 |

## Query catalogue

### Q01_headline_kpis

- **Category:** Revenue
- **Purpose:** Headline KPIs: revenue, orders, customers, AOV for revenue-recognised orders (status not canceled/unavailable).
- **Output schema:** `total_revenue numeric, product_revenue numeric, freight_revenue numeric, total_orders bigint, unique_customers bigint, avg_order_value numeric`
- **Measured:** rows = 1, runtime = 183.3 ms, status = OK
- **Source:** `sql/*/01_revenue.sql`

```sql
SELECT round(sum(f.revenue), 2)                                         AS total_revenue,
       round(sum(f.items_price) FILTER (WHERE f.is_revenue_order), 2)   AS product_revenue,
       round(sum(f.freight_value) FILTER (WHERE f.is_revenue_order), 2) AS freight_revenue,
       count(*) FILTER (WHERE f.is_revenue_order)                       AS total_orders,
       count(DISTINCT c.customer_unique_id) FILTER (WHERE f.is_revenue_order) AS unique_customers,
       round(sum(f.revenue) / NULLIF(count(*) FILTER (WHERE f.is_revenue_order), 0), 2) AS avg_order_value
FROM nexus_dw.fact_orders f
JOIN nexus_dw.dim_customer c ON c.customer_key = f.customer_key
```

### Q02_monthly_revenue_mom_growth

- **Category:** Revenue
- **Purpose:** Monthly revenue with month-over-month growth (LAG window function).
- **Output schema:** `month_start date, revenue numeric, orders bigint, prev_revenue numeric, mom_growth_pct numeric`
- **Measured:** rows = 25, runtime = 38.6 ms, status = OK
- **Source:** `sql/*/01_revenue.sql`

```sql
WITH m AS (
    SELECT d.month_start, sum(f.revenue) AS revenue, count(*) FILTER (WHERE f.is_revenue_order) AS orders
    FROM nexus_dw.fact_orders f JOIN nexus_dw.dim_date d ON d.date_key = f.purchase_date_key
    GROUP BY d.month_start
)
SELECT month_start, round(revenue, 2) AS revenue, orders,
       round(LAG(revenue) OVER (ORDER BY month_start), 2) AS prev_revenue,
       round(100 * (revenue / NULLIF(LAG(revenue) OVER (ORDER BY month_start), 0) - 1), 2) AS mom_growth_pct
FROM m ORDER BY month_start
```

### Q03_quarterly_revenue_qoq

- **Category:** Revenue
- **Purpose:** Quarterly revenue and quarter-over-quarter growth.
- **Output schema:** `quarter_label text, revenue numeric, orders bigint, qoq_growth_pct numeric`
- **Measured:** rows = 10, runtime = 30.2 ms, status = OK
- **Source:** `sql/*/01_revenue.sql`

```sql
WITH q AS (
    SELECT d.year, d.quarter, d.quarter_label, sum(f.revenue) AS revenue,
           count(*) FILTER (WHERE f.is_revenue_order) AS orders
    FROM nexus_dw.fact_orders f JOIN nexus_dw.dim_date d ON d.date_key = f.purchase_date_key
    GROUP BY d.year, d.quarter, d.quarter_label
)
SELECT quarter_label, round(revenue, 2) AS revenue, orders,
       round(100 * (revenue / NULLIF(LAG(revenue) OVER (ORDER BY year, quarter), 0) - 1), 2) AS qoq_growth_pct
FROM q ORDER BY year, quarter
```

### Q04_yoy_monthly_comparison

- **Category:** Revenue
- **Purpose:** Year-over-year comparison by calendar month (2018 vs 2017) – self-join on month number.
- **Output schema:** `month smallint, month_name text, revenue_2017 numeric, revenue_2018 numeric, yoy_growth_pct numeric`
- **Measured:** rows = 12, runtime = 43.2 ms, status = OK
- **Source:** `sql/*/01_revenue.sql`

```sql
WITH m AS (
    SELECT d.year, d.month, d.month_name, sum(f.revenue) AS revenue
    FROM nexus_dw.fact_orders f JOIN nexus_dw.dim_date d ON d.date_key = f.purchase_date_key
    WHERE d.year IN (2017, 2018)
    GROUP BY d.year, d.month, d.month_name
)
SELECT a.month, a.month_name, round(a.revenue, 2) AS revenue_2017, round(b.revenue, 2) AS revenue_2018,
       round(100 * (b.revenue / NULLIF(a.revenue, 0) - 1), 2) AS yoy_growth_pct
FROM m a LEFT JOIN m b ON b.month = a.month AND b.year = 2018
WHERE a.year = 2017
ORDER BY a.month
```

### Q05_ytd_revenue_comparison

- **Category:** Revenue
- **Purpose:** Year-to-date revenue Jan–Aug, 2017 vs 2018 (same period comparison, data ends Aug-2018).
- **Output schema:** `year smallint, ytd_revenue numeric, ytd_orders bigint, yoy_growth_pct numeric`
- **Measured:** rows = 2, runtime = 30.7 ms, status = OK
- **Source:** `sql/*/01_revenue.sql`

```sql
WITH y AS (
    SELECT d.year, sum(f.revenue) AS ytd_revenue, count(*) FILTER (WHERE f.is_revenue_order) AS ytd_orders
    FROM nexus_dw.fact_orders f JOIN nexus_dw.dim_date d ON d.date_key = f.purchase_date_key
    WHERE d.month BETWEEN 1 AND 8 AND d.year IN (2017, 2018)
    GROUP BY d.year
)
SELECT year, round(ytd_revenue, 2) AS ytd_revenue, ytd_orders,
       round(100 * (ytd_revenue / NULLIF(LAG(ytd_revenue) OVER (ORDER BY year), 0) - 1), 2) AS yoy_growth_pct
FROM y ORDER BY year
```

### Q06_running_total_revenue

- **Category:** Revenue
- **Purpose:** Cumulative (running total) revenue by month, and share of all-time revenue reached.
- **Output schema:** `month_start date, revenue numeric, running_revenue numeric, pct_of_total numeric`
- **Measured:** rows = 25, runtime = 36.9 ms, status = OK
- **Source:** `sql/*/01_revenue.sql`

```sql
WITH m AS (
    SELECT d.month_start, sum(f.revenue) AS revenue
    FROM nexus_dw.fact_orders f JOIN nexus_dw.dim_date d ON d.date_key = f.purchase_date_key
    GROUP BY d.month_start
)
SELECT month_start, round(revenue, 2) AS revenue,
       round(sum(revenue) OVER (ORDER BY month_start ROWS UNBOUNDED PRECEDING), 2) AS running_revenue,
       round(100 * sum(revenue) OVER (ORDER BY month_start ROWS UNBOUNDED PRECEDING) / sum(revenue) OVER (), 2) AS pct_of_total
FROM m ORDER BY month_start
```

### Q07_rolling_7_30_day_revenue

- **Category:** Revenue
- **Purpose:** Daily revenue with 7-day and 30-day rolling averages (RANGE frame on dates, gaps filled by dim_date).
- **Output schema:** `full_date date, revenue numeric, rolling_7d_avg numeric, rolling_30d_avg numeric`
- **Measured:** rows = 608, runtime = 40.4 ms, status = OK
- **Source:** `sql/*/01_revenue.sql`

```sql
WITH daily AS (
    SELECT d.full_date, COALESCE(sum(f.revenue), 0) AS revenue
    FROM nexus_dw.dim_date d
    LEFT JOIN nexus_dw.fact_orders f ON f.purchase_date_key = d.date_key
    WHERE d.full_date BETWEEN '2017-01-01' AND '2018-08-31'
    GROUP BY d.full_date
)
SELECT full_date, round(revenue, 2) AS revenue,
       round(avg(revenue) OVER (ORDER BY full_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 2) AS rolling_7d_avg,
       round(avg(revenue) OVER (ORDER BY full_date ROWS BETWEEN 29 PRECEDING AND CURRENT ROW), 2) AS rolling_30d_avg
FROM daily ORDER BY full_date
```

### Q08_revenue_by_weekday

- **Category:** Revenue
- **Purpose:** Revenue and order volume by day of week (average per calendar day to normalise).
- **Output schema:** `day_of_week smallint, day_name text, total_revenue numeric, avg_daily_revenue numeric, avg_daily_orders numeric`
- **Measured:** rows = 7, runtime = 55.3 ms, status = OK
- **Source:** `sql/*/01_revenue.sql`

```sql
WITH daily AS (
    SELECT d.full_date, d.day_of_week, d.day_name, COALESCE(sum(f.revenue), 0) AS revenue,
           count(f.order_id) FILTER (WHERE f.is_revenue_order) AS orders
    FROM nexus_dw.dim_date d
    LEFT JOIN nexus_dw.fact_orders f ON f.purchase_date_key = d.date_key
    WHERE d.full_date BETWEEN '2017-01-01' AND '2018-08-31'
    GROUP BY d.full_date, d.day_of_week, d.day_name
)
SELECT day_of_week, day_name, round(sum(revenue), 2) AS total_revenue,
       round(avg(revenue), 2) AS avg_daily_revenue, round(avg(orders), 1) AS avg_daily_orders
FROM daily GROUP BY day_of_week, day_name ORDER BY day_of_week
```

### Q09_revenue_by_hour

- **Category:** Revenue
- **Purpose:** Revenue and orders by hour of purchase (local timestamp).
- **Output schema:** `purchase_hour int, orders bigint, revenue numeric, pct_orders numeric`
- **Measured:** rows = 24, runtime = 57.6 ms, status = OK
- **Source:** `sql/*/01_revenue.sql`

```sql
SELECT EXTRACT(HOUR FROM purchase_timestamp)::INT AS purchase_hour,
       count(*) AS orders, round(sum(revenue), 2) AS revenue,
       round(100.0 * count(*) / sum(count(*)) OVER (), 2) AS pct_orders
FROM nexus_dw.fact_orders WHERE is_revenue_order
GROUP BY 1 ORDER BY 1
```

### Q10_black_friday_impact

- **Category:** Revenue
- **Purpose:** Black Friday 2017 vs average of the 4 preceding same weekdays (dim_date flag).
- **Output schema:** `full_date date, revenue numeric, orders bigint, baseline_revenue numeric, uplift_x numeric`
- **Measured:** rows = 1, runtime = 40.7 ms, status = OK
- **Source:** `sql/*/01_revenue.sql`

```sql
WITH bf AS (SELECT full_date FROM nexus_dw.dim_date WHERE is_black_friday AND year = 2017),
daily AS (
    SELECT d.full_date, sum(f.revenue) AS revenue, count(*) FILTER (WHERE f.is_revenue_order) AS orders
    FROM nexus_dw.fact_orders f JOIN nexus_dw.dim_date d ON d.date_key = f.purchase_date_key GROUP BY d.full_date
)
SELECT dl.full_date, round(dl.revenue, 2) AS revenue, dl.orders,
       round((SELECT avg(revenue) FROM daily x WHERE x.full_date IN
              (SELECT bf.full_date - 7 * k FROM generate_series(1, 4) k)), 2) AS baseline_revenue,
       round(dl.revenue / (SELECT avg(revenue) FROM daily x WHERE x.full_date IN
              (SELECT bf.full_date - 7 * k FROM generate_series(1, 4) k)), 2) AS uplift_x
FROM daily dl JOIN bf ON bf.full_date = dl.full_date
```

### Q11_repeat_customer_rate

- **Category:** Customers
- **Purpose:** Share of customers (customer_unique_id) with more than one revenue order.
- **Output schema:** `customers bigint, repeat_customers bigint, repeat_rate_pct numeric, repeat_revenue_share_pct numeric`
- **Measured:** rows = 1, runtime = 215.4 ms, status = OK
- **Source:** `sql/*/02_customers.sql`

```sql
WITH c AS (
    SELECT dc.customer_unique_id, count(*) AS orders, sum(f.revenue) AS revenue
    FROM nexus_dw.fact_orders f JOIN nexus_dw.dim_customer dc ON dc.customer_key = f.customer_key
    WHERE f.is_revenue_order AND f.items_count > 0
    GROUP BY dc.customer_unique_id
)
SELECT count(*) AS customers, count(*) FILTER (WHERE orders > 1) AS repeat_customers,
       round(100.0 * count(*) FILTER (WHERE orders > 1) / count(*), 3) AS repeat_rate_pct,
       round(100.0 * sum(revenue) FILTER (WHERE orders > 1) / sum(revenue), 3) AS repeat_revenue_share_pct
FROM c
```

### Q12_order_frequency_distribution

- **Category:** Customers
- **Purpose:** Distribution of customers by number of orders.
- **Output schema:** `orders_per_customer bigint, customers bigint, pct_customers numeric`
- **Measured:** rows = 5, runtime = 151.5 ms, status = OK
- **Source:** `sql/*/02_customers.sql`

```sql
WITH c AS (
    SELECT dc.customer_unique_id, count(*) AS n
    FROM nexus_dw.fact_orders f JOIN nexus_dw.dim_customer dc ON dc.customer_key = f.customer_key
    WHERE f.is_revenue_order AND f.items_count > 0 GROUP BY 1
)
SELECT LEAST(n, 5) AS orders_per_customer, count(*) AS customers,
       round(100.0 * count(*) / sum(count(*)) OVER (), 3) AS pct_customers
FROM c GROUP BY 1 ORDER BY 1
```

### Q13_customer_lifetime_value_estimate

- **Category:** Customers
- **Purpose:** Historical CLV estimate = AOV x purchase frequency x observed lifespan factor; plus revenue deciles (NTILE).
- **Output schema:** `decile int, customers bigint, avg_revenue numeric, min_revenue numeric, max_revenue numeric, revenue_share_pct numeric`
- **Measured:** rows = 10, runtime = 214.1 ms, status = OK
- **Source:** `sql/*/02_customers.sql`

```sql
WITH c AS (
    SELECT dc.customer_unique_id, sum(f.revenue) AS revenue
    FROM nexus_dw.fact_orders f JOIN nexus_dw.dim_customer dc ON dc.customer_key = f.customer_key
    WHERE f.is_revenue_order AND f.items_count > 0 GROUP BY 1
), d AS (SELECT *, ntile(10) OVER (ORDER BY revenue DESC) AS decile FROM c)
SELECT decile, count(*) AS customers, round(avg(revenue), 2) AS avg_revenue,
       round(min(revenue), 2) AS min_revenue, round(max(revenue), 2) AS max_revenue,
       round(100 * sum(revenue) / sum(sum(revenue)) OVER (), 2) AS revenue_share_pct
FROM d GROUP BY decile ORDER BY decile
```

### Q14_clv_formula_by_state

- **Category:** Customers
- **Purpose:** Simple CLV estimate per customer state: AOV x avg orders per customer (historical, BRL).
- **Output schema:** `state text, customers bigint, aov numeric, orders_per_customer numeric, est_clv numeric`
- **Measured:** rows = 24, runtime = 159.3 ms, status = OK
- **Source:** `sql/*/02_customers.sql`

```sql
WITH c AS (
    SELECT dc.customer_unique_id, max(dc.state) AS state, count(*) AS orders, sum(f.revenue) AS revenue
    FROM nexus_dw.fact_orders f JOIN nexus_dw.dim_customer dc ON dc.customer_key = f.customer_key
    WHERE f.is_revenue_order AND f.items_count > 0 GROUP BY 1
)
SELECT state, count(*) AS customers, round(sum(revenue) / sum(orders), 2) AS aov,
       round(avg(orders), 4) AS orders_per_customer,
       round(sum(revenue) / sum(orders) * avg(orders), 2) AS est_clv
FROM c GROUP BY state HAVING count(*) >= 100 ORDER BY est_clv DESC
```

### Q15_top_customers_ranking

- **Category:** Customers
- **Purpose:** Top 20 customers by lifetime revenue with RANK and DENSE_RANK.
- **Output schema:** `customer_unique_id text, orders bigint, lifetime_revenue numeric, revenue_rank bigint, dense_rank bigint`
- **Measured:** rows = 20, runtime = 365.7 ms, status = OK
- **Source:** `sql/*/02_customers.sql`

```sql
SELECT customer_unique_id, orders, round(lifetime_revenue, 2) AS lifetime_revenue,
       RANK() OVER (ORDER BY lifetime_revenue DESC) AS revenue_rank,
       DENSE_RANK() OVER (ORDER BY orders DESC) AS dense_rank
FROM nexus_dw.vw_customer_360
ORDER BY lifetime_revenue DESC LIMIT 20
```

### Q16_days_between_purchases

- **Category:** Customers
- **Purpose:** For repeat customers: days between consecutive orders (LAG) – median and percentiles.
- **Output schema:** `repeat_gaps bigint, p25_days numeric, median_days numeric, p75_days numeric, mean_days numeric`
- **Measured:** rows = 1, runtime = 200.6 ms, status = OK
- **Source:** `sql/*/02_customers.sql`

```sql
WITH o AS (
    SELECT dc.customer_unique_id, f.purchase_timestamp,
           LAG(f.purchase_timestamp) OVER (PARTITION BY dc.customer_unique_id ORDER BY f.purchase_timestamp) AS prev_ts
    FROM nexus_dw.fact_orders f JOIN nexus_dw.dim_customer dc ON dc.customer_key = f.customer_key
    WHERE f.is_revenue_order AND f.items_count > 0
), g AS (SELECT EXTRACT(EPOCH FROM purchase_timestamp - prev_ts) / 86400 AS gap FROM o WHERE prev_ts IS NOT NULL)
SELECT count(*) AS repeat_gaps,
       round(percentile_cont(0.25) WITHIN GROUP (ORDER BY gap)::NUMERIC, 1) AS p25_days,
       round(percentile_cont(0.50) WITHIN GROUP (ORDER BY gap)::NUMERIC, 1) AS median_days,
       round(percentile_cont(0.75) WITHIN GROUP (ORDER BY gap)::NUMERIC, 1) AS p75_days,
       round(avg(gap)::NUMERIC, 1) AS mean_days
FROM g
```

### Q17_rfm_segment_summary

- **Category:** Customers
- **Purpose:** RFM segments from the materialized view mv_customer_rfm (rule-based labelling).
- **Output schema:** `rfm_segment text, customers bigint, avg_recency numeric, avg_frequency numeric, avg_monetary numeric, revenue_share_pct numeric`
- **Measured:** rows = 7, runtime = 33.2 ms, status = OK
- **Source:** `sql/*/02_customers.sql`

```sql
WITH s AS (
    SELECT *, CASE
        WHEN f_score >= 4 AND r_score >= 4 THEN 'Champions'
        WHEN f_score >= 4 THEN 'Loyal - Lapsing'
        WHEN r_score >= 4 AND m_score >= 4 THEN 'New High-Value'
        WHEN r_score >= 4 THEN 'New Low-Value'
        WHEN r_score = 3 THEN 'Needs Attention'
        WHEN m_score >= 4 THEN 'At Risk - High Value'
        ELSE 'Hibernating' END AS rfm_segment
    FROM nexus_dw.mv_customer_rfm
)
SELECT rfm_segment, count(*) AS customers, round(avg(recency_days), 1) AS avg_recency,
       round(avg(frequency), 3) AS avg_frequency, round(avg(monetary), 2) AS avg_monetary,
       round(100 * sum(monetary) / sum(sum(monetary)) OVER (), 2) AS revenue_share_pct
FROM s GROUP BY rfm_segment ORDER BY customers DESC
```

### Q18_customers_with_address_changes

- **Category:** Customers
- **Purpose:** SCD Type 2 insight: customers whose address changed between orders.
- **Output schema:** `customers_with_changes bigint, total_versions bigint, max_versions int`
- **Measured:** rows = 1, runtime = 179.4 ms, status = OK
- **Source:** `sql/*/02_customers.sql`

```sql
SELECT count(*) FILTER (WHERE address_versions > 1) AS customers_with_changes,
       sum(address_versions) AS total_versions, max(address_versions) AS max_versions
FROM nexus_dw.vw_customer_360
```

### Q19_top_categories_revenue

- **Category:** Products
- **Purpose:** Top 15 categories by item revenue (item grain – no fan-out), with share and cumulative share (Pareto).
- **Output schema:** `category text, units bigint, revenue numeric, revenue_share_pct numeric, cumulative_share_pct numeric`
- **Measured:** rows = 15, runtime = 55.4 ms, status = OK
- **Source:** `sql/*/03_products_sellers.sql`

```sql
WITH c AS (
    SELECT p.category_display_name AS category, count(*) AS units, sum(i.price) AS revenue
    FROM nexus_dw.fact_order_items i JOIN nexus_dw.dim_product p ON p.product_key = i.product_key
    WHERE i.is_revenue_order GROUP BY 1
)
SELECT category, units, round(revenue, 2) AS revenue,
       round(100 * revenue / sum(revenue) OVER (), 2) AS revenue_share_pct,
       round(100 * sum(revenue) OVER (ORDER BY revenue DESC) / sum(revenue) OVER (), 2) AS cumulative_share_pct
FROM c ORDER BY revenue DESC LIMIT 15
```

### Q20_category_growth_2018_vs_2017

- **Category:** Products
- **Purpose:** Category revenue Jan–Aug 2018 vs Jan–Aug 2017 (from mv_monthly_category_sales).
- **Output schema:** `category_name_en text, revenue_2017 numeric, revenue_2018 numeric, growth_pct numeric`
- **Measured:** rows = 18, runtime = 2.9 ms, status = OK
- **Source:** `sql/*/03_products_sellers.sql`

```sql
SELECT category_name_en,
       round(sum(product_revenue) FILTER (WHERE month_start BETWEEN '2017-01-01' AND '2017-08-01'), 2) AS revenue_2017,
       round(sum(product_revenue) FILTER (WHERE month_start BETWEEN '2018-01-01' AND '2018-08-01'), 2) AS revenue_2018,
       round(100 * (sum(product_revenue) FILTER (WHERE month_start BETWEEN '2018-01-01' AND '2018-08-01')
             / NULLIF(sum(product_revenue) FILTER (WHERE month_start BETWEEN '2017-01-01' AND '2017-08-01'), 0) - 1), 1) AS growth_pct
FROM nexus_dw.mv_monthly_category_sales
GROUP BY category_name_en
HAVING sum(product_revenue) FILTER (WHERE month_start BETWEEN '2017-01-01' AND '2017-08-01') > 50000
ORDER BY growth_pct DESC
```

### Q21_category_rank_by_month

- **Category:** Products
- **Purpose:** Category rank per month (RANK partitioned by month) – top 3 categories for every month.
- **Output schema:** `month_start date, category_name_en text, revenue numeric, month_rank bigint`
- **Measured:** rows = 60, runtime = 2.9 ms, status = OK
- **Source:** `sql/*/03_products_sellers.sql`

```sql
SELECT * FROM (
    SELECT month_start, category_name_en, round(product_revenue, 2) AS revenue,
           RANK() OVER (PARTITION BY month_start ORDER BY product_revenue DESC) AS month_rank
    FROM nexus_dw.mv_monthly_category_sales
    WHERE month_start BETWEEN '2017-01-01' AND '2018-08-01'
) r WHERE month_rank <= 3 ORDER BY month_start, month_rank
```

### Q22_price_percentiles_by_category

- **Category:** Products
- **Purpose:** Price distribution (P10/P50/P90) per top category – percentile_cont.
- **Output schema:** `category text, items bigint, p10 numeric, p50 numeric, p90 numeric, avg_price numeric`
- **Measured:** rows = 17, runtime = 107.3 ms, status = OK
- **Source:** `sql/*/03_products_sellers.sql`

```sql
SELECT p.category_display_name AS category, count(*) AS items,
       round(percentile_cont(0.1) WITHIN GROUP (ORDER BY i.price)::NUMERIC, 2) AS p10,
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY i.price)::NUMERIC, 2) AS p50,
       round(percentile_cont(0.9) WITHIN GROUP (ORDER BY i.price)::NUMERIC, 2) AS p90,
       round(avg(i.price), 2) AS avg_price
FROM nexus_dw.fact_order_items i JOIN nexus_dw.dim_product p ON p.product_key = i.product_key
WHERE i.is_revenue_order
GROUP BY 1 HAVING count(*) >= 2000 ORDER BY p50 DESC
```

### Q23_freight_ratio_by_category

- **Category:** Products
- **Purpose:** Freight as % of item price per category – identifies categories where shipping cost erodes value.
- **Output schema:** `category text, items bigint, avg_price numeric, avg_freight numeric, freight_ratio_pct numeric`
- **Measured:** rows = 22, runtime = 71.5 ms, status = OK
- **Source:** `sql/*/03_products_sellers.sql`

```sql
SELECT p.category_display_name AS category, count(*) AS items, round(avg(i.price), 2) AS avg_price,
       round(avg(i.freight_value), 2) AS avg_freight,
       round(100 * sum(i.freight_value) / sum(i.price), 2) AS freight_ratio_pct
FROM nexus_dw.fact_order_items i JOIN nexus_dw.dim_product p ON p.product_key = i.product_key
WHERE i.is_revenue_order
GROUP BY 1 HAVING count(*) >= 1000 ORDER BY freight_ratio_pct DESC
```

### Q24_top_sellers_scorecard

- **Category:** Sellers
- **Purpose:** Top 20 sellers by GMV with operational KPIs (fan-out-safe view vw_seller_scorecard).
- **Output schema:** `seller_id text, state text, orders bigint, gmv numeric, avg_review numeric, late_rate_pct numeric, gmv_rank bigint`
- **Measured:** rows = 20, runtime = 279.4 ms, status = OK
- **Source:** `sql/*/03_products_sellers.sql`

```sql
SELECT seller_id, state, orders, round(gmv, 2) AS gmv, round(avg_review, 2) AS avg_review,
       round(100 * late_rate, 2) AS late_rate_pct, RANK() OVER (ORDER BY gmv DESC) AS gmv_rank
FROM nexus_dw.vw_seller_scorecard ORDER BY gmv DESC LIMIT 20
```

### Q25_seller_concentration

- **Category:** Sellers
- **Purpose:** Seller revenue concentration: share of GMV from top 1%, 5%, 10%, 20% of sellers.
- **Output schema:** `top_pct_sellers int, sellers bigint, gmv_share_pct numeric`
- **Measured:** rows = 4, runtime = 61.5 ms, status = OK
- **Source:** `sql/*/03_products_sellers.sql`

```sql
WITH s AS (SELECT seller_id, gmv, PERCENT_RANK() OVER (ORDER BY gmv DESC) AS pr FROM nexus_dw.vw_seller_scorecard),
t AS (SELECT unnest(ARRAY[1, 5, 10, 20]) AS top_pct)
SELECT t.top_pct AS top_pct_sellers, count(s.seller_id) AS sellers,
       round(100 * sum(s.gmv) / (SELECT sum(gmv) FROM nexus_dw.vw_seller_scorecard), 2) AS gmv_share_pct
FROM t JOIN s ON s.pr < t.top_pct / 100.0
GROUP BY t.top_pct ORDER BY t.top_pct
```

### Q26_seller_quality_quadrant

- **Category:** Sellers
- **Purpose:** Sellers (>=30 orders) classified into volume x review-quality quadrants relative to medians.
- **Output schema:** `quadrant text, sellers bigint, gmv numeric, avg_review numeric`
- **Measured:** rows = 4, runtime = 294.8 ms, status = OK
- **Source:** `sql/*/03_products_sellers.sql`

```sql
WITH s AS (SELECT * FROM nexus_dw.vw_seller_scorecard WHERE orders >= 30),
m AS (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY orders) AS mo,
             percentile_cont(0.5) WITHIN GROUP (ORDER BY avg_review) AS mr FROM s)
SELECT CASE WHEN s.orders >= m.mo AND s.avg_review >= m.mr THEN 'Stars (high volume, high quality)'
            WHEN s.orders >= m.mo THEN 'Volume at risk (high volume, low quality)'
            WHEN s.avg_review >= m.mr THEN 'Growth candidates (low volume, high quality)'
            ELSE 'Watch list (low volume, low quality)' END AS quadrant,
       count(*) AS sellers, round(sum(s.gmv), 2) AS gmv, round(avg(s.avg_review), 2) AS avg_review
FROM s CROSS JOIN m GROUP BY 1 ORDER BY gmv DESC
```

### Q27_products_above_category_average

- **Category:** Products
- **Purpose:** Products whose avg price exceeds 2x their category average (top 20 by units). OPTIMISED: category averages computed once in a CTE + window function instead of a correlated subquery (measured 266 s -> well under 1 s on this dataset; see docs/database/SQL_QUERY_DOCUMENTATION.md).
- **Output schema:** `product_id text, category text, units bigint, avg_price numeric, category_avg_price numeric`
- **Measured:** rows = 20, runtime = 254.8 ms, status = OK
- **Source:** `sql/*/03_products_sellers.sql`

```sql
WITH lines AS (
    SELECT p.product_id, p.category_display_name AS category, i.price,
           avg(i.price) OVER (PARTITION BY p.category_name_en) AS category_avg_price
    FROM nexus_dw.fact_order_items i JOIN nexus_dw.dim_product p ON p.product_key = i.product_key
)
SELECT product_id, category, count(*) AS units, round(avg(price), 2) AS avg_price,
       round(max(category_avg_price), 2) AS category_avg_price
FROM lines
GROUP BY product_id, category
HAVING avg(price) > 2 * max(category_avg_price)
ORDER BY units DESC LIMIT 20
```

### Q28_revenue_by_state

- **Category:** Geography
- **Purpose:** Revenue, orders, AOV and share by customer state.
- **Output schema:** `state text, region text, orders bigint, revenue numeric, aov numeric, revenue_share_pct numeric`
- **Measured:** rows = 27, runtime = 96.3 ms, status = OK
- **Source:** `sql/*/04_geo_operations.sql`

```sql
SELECT c.state, c.region, count(*) AS orders, round(sum(f.revenue), 2) AS revenue,
       round(sum(f.revenue) / count(*), 2) AS aov,
       round(100 * sum(f.revenue) / sum(sum(f.revenue)) OVER (), 2) AS revenue_share_pct
FROM nexus_dw.fact_orders f JOIN nexus_dw.dim_customer c ON c.customer_key = f.customer_key
WHERE f.is_revenue_order GROUP BY c.state, c.region ORDER BY revenue DESC
```

### Q29_region_performance

- **Category:** Geography
- **Purpose:** Macro-region scorecard: revenue, delivery time, on-time rate and review score.
- **Output schema:** `region text, orders bigint, revenue numeric, avg_delivery_days numeric, on_time_pct numeric, avg_review numeric`
- **Measured:** rows = 5, runtime = 74.8 ms, status = OK
- **Source:** `sql/*/04_geo_operations.sql`

```sql
SELECT c.region, count(*) AS orders, round(sum(f.revenue), 2) AS revenue,
       round(avg(f.delivery_days), 2) AS avg_delivery_days,
       round(100 * avg(CASE WHEN f.is_on_time THEN 1.0 WHEN f.is_late THEN 0.0 END), 2) AS on_time_pct,
       round(avg(f.review_score), 3) AS avg_review
FROM nexus_dw.fact_orders f JOIN nexus_dw.dim_customer c ON c.customer_key = f.customer_key
WHERE f.is_revenue_order GROUP BY c.region ORDER BY revenue DESC
```

### Q30_top_cities

- **Category:** Geography
- **Purpose:** Top 15 customer cities by revenue.
- **Output schema:** `city text, state text, customers bigint, revenue numeric`
- **Measured:** rows = 15, runtime = 235.4 ms, status = OK
- **Source:** `sql/*/04_geo_operations.sql`

```sql
SELECT c.city, c.state, count(DISTINCT c.customer_unique_id) AS customers, round(sum(f.revenue), 2) AS revenue
FROM nexus_dw.fact_orders f JOIN nexus_dw.dim_customer c ON c.customer_key = f.customer_key
WHERE f.is_revenue_order GROUP BY c.city, c.state ORDER BY revenue DESC LIMIT 15
```

### Q31_intra_vs_inter_state_shipping

- **Category:** Operations
- **Purpose:** Same-state vs cross-state seller->customer shipments: delivery time, freight and late rate (item grain, delivered orders).
- **Output schema:** `route_type text, items bigint, avg_freight numeric, avg_delivery_days numeric, late_rate_pct numeric`
- **Measured:** rows = 2, runtime = 160.1 ms, status = OK
- **Source:** `sql/*/04_geo_operations.sql`

```sql
SELECT CASE WHEN s.state = c.state THEN 'Same state' ELSE 'Cross state' END AS route_type,
       count(*) AS items, round(avg(i.freight_value), 2) AS avg_freight,
       round(avg(f.delivery_days), 2) AS avg_delivery_days,
       round(100 * avg(CASE WHEN f.is_late THEN 1.0 ELSE 0.0 END), 2) AS late_rate_pct
FROM nexus_dw.fact_order_items i
JOIN nexus_dw.fact_orders f ON f.order_id = i.order_id
JOIN nexus_dw.dim_seller s ON s.seller_key = i.seller_key
JOIN nexus_dw.dim_customer c ON c.customer_key = i.customer_key
WHERE f.is_delivered GROUP BY 1
```

### Q32_delivery_performance_monthly

- **Category:** Operations
- **Purpose:** Monthly delivery KPIs for delivered orders: avg/median days, on-time %, avg delay of late orders.
- **Output schema:** `month_start date, delivered bigint, avg_days numeric, median_days numeric, on_time_pct numeric, avg_late_delay numeric`
- **Measured:** rows = 23, runtime = 84.2 ms, status = OK
- **Source:** `sql/*/04_geo_operations.sql`

```sql
SELECT d.month_start, count(*) AS delivered, round(avg(f.delivery_days), 2) AS avg_days,
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY f.delivery_days)::NUMERIC, 2) AS median_days,
       round(100 * avg(CASE WHEN f.is_on_time THEN 1.0 ELSE 0.0 END), 2) AS on_time_pct,
       round(avg(f.delivery_delay_days) FILTER (WHERE f.is_late), 2) AS avg_late_delay
FROM nexus_dw.fact_orders f JOIN nexus_dw.dim_date d ON d.date_key = f.purchase_date_key
WHERE f.is_delivered GROUP BY d.month_start ORDER BY d.month_start
```

### Q33_late_delivery_by_state

- **Category:** Operations
- **Purpose:** Late-delivery rate and estimated-vs-actual gap per customer state (states with >=500 deliveries).
- **Output schema:** `state text, delivered bigint, late_rate_pct numeric, avg_actual_days numeric, avg_estimated_days numeric, avg_buffer_days numeric`
- **Measured:** rows = 17, runtime = 72.8 ms, status = OK
- **Source:** `sql/*/04_geo_operations.sql`

```sql
SELECT c.state, count(*) AS delivered,
       round(100 * avg(CASE WHEN f.is_late THEN 1.0 ELSE 0.0 END), 2) AS late_rate_pct,
       round(avg(f.delivery_days), 2) AS avg_actual_days, round(avg(f.estimated_delivery_days), 2) AS avg_estimated_days,
       round(avg(f.estimated_delivery_days - f.delivery_days), 2) AS avg_buffer_days
FROM nexus_dw.fact_orders f JOIN nexus_dw.dim_customer c ON c.customer_key = f.customer_key
WHERE f.is_delivered GROUP BY c.state HAVING count(*) >= 500 ORDER BY late_rate_pct DESC
```

### Q34_delivery_time_percentiles

- **Category:** Operations
- **Purpose:** Delivery-time percentiles (P50/P75/P90/P95/P99) – service-level view.
- **Output schema:** `p50 numeric, p75 numeric, p90 numeric, p95 numeric, p99 numeric`
- **Measured:** rows = 1, runtime = 46.9 ms, status = OK
- **Source:** `sql/*/04_geo_operations.sql`

```sql
SELECT round(percentile_cont(0.50) WITHIN GROUP (ORDER BY delivery_days)::NUMERIC, 1) AS p50,
       round(percentile_cont(0.75) WITHIN GROUP (ORDER BY delivery_days)::NUMERIC, 1) AS p75,
       round(percentile_cont(0.90) WITHIN GROUP (ORDER BY delivery_days)::NUMERIC, 1) AS p90,
       round(percentile_cont(0.95) WITHIN GROUP (ORDER BY delivery_days)::NUMERIC, 1) AS p95,
       round(percentile_cont(0.99) WITHIN GROUP (ORDER BY delivery_days)::NUMERIC, 1) AS p99
FROM nexus_dw.fact_orders WHERE is_delivered
```

### Q35_cancellation_analysis

- **Category:** Operations
- **Purpose:** Order status mix and cancellation/unavailability rate by month.
- **Output schema:** `month_start date, all_orders bigint, canceled bigint, unavailable bigint, cancel_rate_pct numeric`
- **Measured:** rows = 25, runtime = 30.0 ms, status = OK
- **Source:** `sql/*/04_geo_operations.sql`

```sql
SELECT d.month_start, count(*) AS all_orders,
       count(*) FILTER (WHERE f.order_status = 'canceled') AS canceled,
       count(*) FILTER (WHERE f.order_status = 'unavailable') AS unavailable,
       round(100.0 * count(*) FILTER (WHERE f.order_status IN ('canceled', 'unavailable')) / count(*), 3) AS cancel_rate_pct
FROM nexus_dw.fact_orders f JOIN nexus_dw.dim_date d ON d.date_key = f.purchase_date_key
GROUP BY d.month_start ORDER BY d.month_start
```

### Q36_order_status_distribution

- **Category:** Operations
- **Purpose:** Order status distribution with value at stake.
- **Output schema:** `order_status text, orders bigint, pct_orders numeric, order_value numeric`
- **Measured:** rows = 8, runtime = 28.8 ms, status = OK
- **Source:** `sql/*/04_geo_operations.sql`

```sql
SELECT order_status, count(*) AS orders, round(100.0 * count(*) / sum(count(*)) OVER (), 3) AS pct_orders,
       round(sum(order_value), 2) AS order_value
FROM nexus_dw.fact_orders GROUP BY order_status ORDER BY orders DESC
```

### Q37_payment_mix

- **Category:** Payments
- **Purpose:** Payment method mix by transactions and value (payment grain).
- **Output schema:** `payment_type_label text, transactions bigint, payment_value numeric, value_share_pct numeric, avg_installments numeric`
- **Measured:** rows = 5, runtime = 32.6 ms, status = OK
- **Source:** `sql/*/05_payments_reviews_cohorts.sql`

```sql
SELECT pt.payment_type_label, count(*) AS transactions, round(sum(p.payment_value), 2) AS payment_value,
       round(100 * sum(p.payment_value) / sum(sum(p.payment_value)) OVER (), 2) AS value_share_pct,
       round(avg(p.payment_installments), 2) AS avg_installments
FROM nexus_dw.fact_payments p JOIN nexus_dw.dim_payment_type pt ON pt.payment_type_key = p.payment_type_key
GROUP BY pt.payment_type_label ORDER BY payment_value DESC
```

### Q38_installments_vs_order_value

- **Category:** Payments
- **Purpose:** Credit-card installments bands vs average order value.
- **Output schema:** `installment_band text, orders bigint, avg_order_value numeric`
- **Measured:** rows = 5, runtime = 240.9 ms, status = OK
- **Source:** `sql/*/05_payments_reviews_cohorts.sql`

```sql
WITH cc AS (
    SELECT p.order_id, max(p.payment_installments) AS inst
    FROM nexus_dw.fact_payments p JOIN nexus_dw.dim_payment_type pt ON pt.payment_type_key = p.payment_type_key
    WHERE pt.payment_type = 'credit_card' GROUP BY p.order_id
)
SELECT CASE WHEN inst = 1 THEN '1 (single)' WHEN inst <= 3 THEN '2-3' WHEN inst <= 6 THEN '4-6'
            WHEN inst <= 10 THEN '7-10' ELSE '11+' END AS installment_band,
       count(*) AS orders, round(avg(f.order_value), 2) AS avg_order_value
FROM cc JOIN nexus_dw.fact_orders f ON f.order_id = cc.order_id
GROUP BY 1 ORDER BY min(inst)
```

### Q39_review_score_distribution

- **Category:** Reviews
- **Purpose:** Review score distribution (all responses, review grain).
- **Output schema:** `review_score smallint, reviews bigint, pct numeric, with_comment_pct numeric`
- **Measured:** rows = 5, runtime = 20.1 ms, status = OK
- **Source:** `sql/*/05_payments_reviews_cohorts.sql`

```sql
SELECT review_score, count(*) AS reviews, round(100.0 * count(*) / sum(count(*)) OVER (), 2) AS pct,
       round(100 * avg(CASE WHEN has_comment THEN 1.0 ELSE 0.0 END), 2) AS with_comment_pct
FROM nexus_dw.fact_reviews GROUP BY review_score ORDER BY review_score
```

### Q40_review_vs_delivery_delay

- **Category:** Reviews
- **Purpose:** Average review score by delivery-delay bucket – quantifies the satisfaction cost of lateness.
- **Output schema:** `delay_bucket text, orders bigint, avg_review numeric, pct_1_star numeric`
- **Measured:** rows = 6, runtime = 32.6 ms, status = OK
- **Source:** `sql/*/05_payments_reviews_cohorts.sql`

```sql
SELECT CASE WHEN delivery_delay_days <= -10 THEN 'a) 10+ days early'
            WHEN delivery_delay_days <= -1 THEN 'b) 1-9 days early'
            WHEN delivery_delay_days = 0 THEN 'c) on estimated day'
            WHEN delivery_delay_days <= 5 THEN 'd) 1-5 days late'
            WHEN delivery_delay_days <= 15 THEN 'e) 6-15 days late'
            ELSE 'f) 16+ days late' END AS delay_bucket,
       count(*) AS orders, round(avg(review_score), 3) AS avg_review,
       round(100 * avg(CASE WHEN review_score = 1 THEN 1.0 ELSE 0.0 END), 2) AS pct_1_star
FROM nexus_dw.fact_orders WHERE is_delivered AND review_score IS NOT NULL
GROUP BY 1 ORDER BY 1
```

### Q41_review_by_category_worst

- **Category:** Reviews
- **Purpose:** Categories with the lowest average review (>= 500 reviewed orders) – order-level review joined at item grain deduplicated per order.
- **Output schema:** `category text, orders bigint, avg_review numeric`
- **Measured:** rows = 15, runtime = 197.4 ms, status = OK
- **Source:** `sql/*/05_payments_reviews_cohorts.sql`

```sql
WITH oc AS (
    SELECT DISTINCT i.order_id, p.category_display_name AS category
    FROM nexus_dw.fact_order_items i JOIN nexus_dw.dim_product p ON p.product_key = i.product_key
)
SELECT oc.category, count(*) AS orders, round(avg(f.review_score), 3) AS avg_review
FROM oc JOIN nexus_dw.fact_orders f ON f.order_id = oc.order_id
WHERE f.review_score IS NOT NULL
GROUP BY oc.category HAVING count(*) >= 500 ORDER BY avg_review ASC LIMIT 15
```

### Q42_monthly_cohort_retention

- **Category:** Cohorts
- **Purpose:** Monthly acquisition cohorts: % of customers ordering again in months 1..6 after first purchase.
- **Output schema:** `cohort_month date, cohort_size bigint, m1_pct numeric, m2_pct numeric, m3_pct numeric, m4_pct numeric, m5_pct numeric, m6_pct numeric`
- **Measured:** rows = 14, runtime = 288.5 ms, status = OK
- **Source:** `sql/*/05_payments_reviews_cohorts.sql`

```sql
WITH o AS (
    SELECT c.customer_unique_id, date_trunc('month', f.purchase_timestamp)::DATE AS m
    FROM nexus_dw.fact_orders f JOIN nexus_dw.dim_customer c ON c.customer_key = f.customer_key
    WHERE f.is_revenue_order AND f.items_count > 0
), first AS (SELECT customer_unique_id, min(m) AS cohort FROM o GROUP BY 1),
act AS (
    SELECT DISTINCT f.cohort, f.customer_unique_id,
           (EXTRACT(YEAR FROM age(o.m, f.cohort)) * 12 + EXTRACT(MONTH FROM age(o.m, f.cohort)))::INT AS k
    FROM o JOIN first f USING (customer_unique_id)
)
SELECT cohort AS cohort_month, count(DISTINCT customer_unique_id) FILTER (WHERE k = 0) AS cohort_size,
       round(100.0 * count(DISTINCT customer_unique_id) FILTER (WHERE k = 1) / count(DISTINCT customer_unique_id) FILTER (WHERE k = 0), 3) AS m1_pct,
       round(100.0 * count(DISTINCT customer_unique_id) FILTER (WHERE k = 2) / count(DISTINCT customer_unique_id) FILTER (WHERE k = 0), 3) AS m2_pct,
       round(100.0 * count(DISTINCT customer_unique_id) FILTER (WHERE k = 3) / count(DISTINCT customer_unique_id) FILTER (WHERE k = 0), 3) AS m3_pct,
       round(100.0 * count(DISTINCT customer_unique_id) FILTER (WHERE k = 4) / count(DISTINCT customer_unique_id) FILTER (WHERE k = 0), 3) AS m4_pct,
       round(100.0 * count(DISTINCT customer_unique_id) FILTER (WHERE k = 5) / count(DISTINCT customer_unique_id) FILTER (WHERE k = 0), 3) AS m5_pct,
       round(100.0 * count(DISTINCT customer_unique_id) FILTER (WHERE k = 6) / count(DISTINCT customer_unique_id) FILTER (WHERE k = 0), 3) AS m6_pct
FROM act WHERE cohort BETWEEN '2017-01-01' AND '2018-02-01'
GROUP BY cohort ORDER BY cohort
```

### Q43_cohort_revenue_ltv

- **Category:** Cohorts
- **Purpose:** Cumulative revenue per acquired customer by cohort quarter (LTV curve, months since acquisition 0..6).
- **Output schema:** `cohort_quarter text, customers bigint, ltv_m0 numeric, ltv_m3 numeric, ltv_m6 numeric`
- **Measured:** rows = 5, runtime = 291.2 ms, status = OK
- **Source:** `sql/*/05_payments_reviews_cohorts.sql`

```sql
WITH o AS (
    SELECT c.customer_unique_id, f.purchase_timestamp, f.revenue
    FROM nexus_dw.fact_orders f JOIN nexus_dw.dim_customer c ON c.customer_key = f.customer_key
    WHERE f.is_revenue_order AND f.items_count > 0
), first AS (SELECT customer_unique_id, min(purchase_timestamp) AS first_ts FROM o GROUP BY 1)
SELECT to_char(f.first_ts, 'YYYY-"Q"Q') AS cohort_quarter, count(DISTINCT f.customer_unique_id) AS customers,
       round(sum(o.revenue) FILTER (WHERE o.purchase_timestamp < f.first_ts + INTERVAL '1 month') / count(DISTINCT f.customer_unique_id), 2) AS ltv_m0,
       round(sum(o.revenue) FILTER (WHERE o.purchase_timestamp < f.first_ts + INTERVAL '3 month') / count(DISTINCT f.customer_unique_id), 2) AS ltv_m3,
       round(sum(o.revenue) FILTER (WHERE o.purchase_timestamp < f.first_ts + INTERVAL '6 month') / count(DISTINCT f.customer_unique_id), 2) AS ltv_m6
FROM first f JOIN o USING (customer_unique_id)
WHERE f.first_ts BETWEEN '2017-01-01' AND '2018-02-28'
GROUP BY 1 ORDER BY 1
```

### Q44_simulated_category_margin

- **Category:** Profitability (SIMULATED)
- **Purpose:** SIMULATED gross margin by category using synthetic unit costs – NOT a real finding.
- **Output schema:** `category_name_en text, revenue numeric, simulated_cogs numeric, simulated_margin_pct numeric, is_synthetic boolean`
- **Measured:** rows = 15, runtime = 79.0 ms, status = OK
- **Source:** `sql/*/05_payments_reviews_cohorts.sql`

```sql
SELECT category_name_en, round(revenue, 2) AS revenue, round(simulated_cogs, 2) AS simulated_cogs,
       simulated_margin_pct, is_synthetic
FROM nexus_dw.vw_syn_category_margin ORDER BY revenue DESC LIMIT 15
```

### Q45_simulated_stockout_summary

- **Category:** Inventory (SIMULATED)
- **Purpose:** SIMULATED stock-out weeks and lost units per category from the synthetic inventory model – NOT a real finding.
- **Output schema:** `category text, weeks bigint, stockout_weeks bigint, lost_units bigint, is_synthetic boolean`
- **Measured:** rows = 10, runtime = 2.8 ms, status = OK
- **Source:** `sql/*/05_payments_reviews_cohorts.sql`

```sql
SELECT category, count(*) AS weeks, count(*) FILTER (WHERE is_stockout) AS stockout_weeks,
       sum(lost_sales_units) AS lost_units, bool_and(is_synthetic) AS is_synthetic
FROM nexus_dw.syn_inventory_weekly GROUP BY category ORDER BY lost_units DESC LIMIT 10
```

### Q46_optimization_explain_revenue_filter

- **Category:** Optimization
- **Purpose:** EXPLAIN (ANALYZE) of a monthly revenue query that can use the partial index ix_fo_revenue_only.
- **Output schema:** `QUERY PLAN text`
- **Measured:** rows = 25, runtime = 18.9 ms, status = OK
- **Source:** `sql/*/02_query_optimization.sql`

```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT d.month_start, sum(f.revenue)
FROM nexus_dw.fact_orders f JOIN nexus_dw.dim_date d ON d.date_key = f.purchase_date_key
WHERE f.is_revenue_order AND f.purchase_date_key BETWEEN 20180101 AND 20180331
GROUP BY d.month_start
```

### Q47_optimization_mv_vs_base

- **Category:** Optimization
- **Purpose:** EXPLAIN (ANALYZE) reading daily KPIs from the materialized view instead of re-aggregating facts.
- **Output schema:** `QUERY PLAN text`
- **Measured:** rows = 4, runtime = 2.0 ms, status = OK
- **Source:** `sql/*/02_query_optimization.sql`

```sql
EXPLAIN (ANALYZE, FORMAT TEXT)
SELECT full_date, revenue FROM nexus_dw.mv_daily_kpis WHERE full_date BETWEEN '2018-01-01' AND '2018-03-31'
```
