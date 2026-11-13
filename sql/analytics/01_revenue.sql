-- @query Q01_headline_kpis
-- @category Revenue
-- @description Headline KPIs: revenue, orders, customers, AOV for revenue-recognised orders (status not canceled/unavailable).
-- @output total_revenue numeric, product_revenue numeric, freight_revenue numeric, total_orders bigint, unique_customers bigint, avg_order_value numeric
SELECT round(sum(f.revenue), 2)                                         AS total_revenue,
       round(sum(f.items_price) FILTER (WHERE f.is_revenue_order), 2)   AS product_revenue,
       round(sum(f.freight_value) FILTER (WHERE f.is_revenue_order), 2) AS freight_revenue,
       count(*) FILTER (WHERE f.is_revenue_order)                       AS total_orders,
       count(DISTINCT c.customer_unique_id) FILTER (WHERE f.is_revenue_order) AS unique_customers,
       round(sum(f.revenue) / NULLIF(count(*) FILTER (WHERE f.is_revenue_order), 0), 2) AS avg_order_value
FROM nexus_dw.fact_orders f
JOIN nexus_dw.dim_customer c ON c.customer_key = f.customer_key;

-- @query Q02_monthly_revenue_mom_growth
-- @category Revenue
-- @description Monthly revenue with month-over-month growth (LAG window function).
-- @output month_start date, revenue numeric, orders bigint, prev_revenue numeric, mom_growth_pct numeric
WITH m AS (
    SELECT d.month_start, sum(f.revenue) AS revenue, count(*) FILTER (WHERE f.is_revenue_order) AS orders
    FROM nexus_dw.fact_orders f JOIN nexus_dw.dim_date d ON d.date_key = f.purchase_date_key
    GROUP BY d.month_start
)
SELECT month_start, round(revenue, 2) AS revenue, orders,
       round(LAG(revenue) OVER (ORDER BY month_start), 2) AS prev_revenue,
       round(100 * (revenue / NULLIF(LAG(revenue) OVER (ORDER BY month_start), 0) - 1), 2) AS mom_growth_pct
FROM m ORDER BY month_start;

-- @query Q03_quarterly_revenue_qoq
-- @category Revenue
-- @description Quarterly revenue and quarter-over-quarter growth.
-- @output quarter_label text, revenue numeric, orders bigint, qoq_growth_pct numeric
WITH q AS (
    SELECT d.year, d.quarter, d.quarter_label, sum(f.revenue) AS revenue,
           count(*) FILTER (WHERE f.is_revenue_order) AS orders
    FROM nexus_dw.fact_orders f JOIN nexus_dw.dim_date d ON d.date_key = f.purchase_date_key
    GROUP BY d.year, d.quarter, d.quarter_label
)
SELECT quarter_label, round(revenue, 2) AS revenue, orders,
       round(100 * (revenue / NULLIF(LAG(revenue) OVER (ORDER BY year, quarter), 0) - 1), 2) AS qoq_growth_pct
FROM q ORDER BY year, quarter;

-- @query Q04_yoy_monthly_comparison
-- @category Revenue
-- @description Year-over-year comparison by calendar month (2018 vs 2017) – self-join on month number.
-- @output month smallint, month_name text, revenue_2017 numeric, revenue_2018 numeric, yoy_growth_pct numeric
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
ORDER BY a.month;

-- @query Q05_ytd_revenue_comparison
-- @category Revenue
-- @description Year-to-date revenue Jan–Aug, 2017 vs 2018 (same period comparison, data ends Aug-2018).
-- @output year smallint, ytd_revenue numeric, ytd_orders bigint, yoy_growth_pct numeric
WITH y AS (
    SELECT d.year, sum(f.revenue) AS ytd_revenue, count(*) FILTER (WHERE f.is_revenue_order) AS ytd_orders
    FROM nexus_dw.fact_orders f JOIN nexus_dw.dim_date d ON d.date_key = f.purchase_date_key
    WHERE d.month BETWEEN 1 AND 8 AND d.year IN (2017, 2018)
    GROUP BY d.year
)
SELECT year, round(ytd_revenue, 2) AS ytd_revenue, ytd_orders,
       round(100 * (ytd_revenue / NULLIF(LAG(ytd_revenue) OVER (ORDER BY year), 0) - 1), 2) AS yoy_growth_pct
FROM y ORDER BY year;

-- @query Q06_running_total_revenue
-- @category Revenue
-- @description Cumulative (running total) revenue by month, and share of all-time revenue reached.
-- @output month_start date, revenue numeric, running_revenue numeric, pct_of_total numeric
WITH m AS (
    SELECT d.month_start, sum(f.revenue) AS revenue
    FROM nexus_dw.fact_orders f JOIN nexus_dw.dim_date d ON d.date_key = f.purchase_date_key
    GROUP BY d.month_start
)
SELECT month_start, round(revenue, 2) AS revenue,
       round(sum(revenue) OVER (ORDER BY month_start ROWS UNBOUNDED PRECEDING), 2) AS running_revenue,
       round(100 * sum(revenue) OVER (ORDER BY month_start ROWS UNBOUNDED PRECEDING) / sum(revenue) OVER (), 2) AS pct_of_total
FROM m ORDER BY month_start;

-- @query Q07_rolling_7_30_day_revenue
-- @category Revenue
-- @description Daily revenue with 7-day and 30-day rolling averages (RANGE frame on dates, gaps filled by dim_date).
-- @output full_date date, revenue numeric, rolling_7d_avg numeric, rolling_30d_avg numeric
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
FROM daily ORDER BY full_date;

-- @query Q08_revenue_by_weekday
-- @category Revenue
-- @description Revenue and order volume by day of week (average per calendar day to normalise).
-- @output day_of_week smallint, day_name text, total_revenue numeric, avg_daily_revenue numeric, avg_daily_orders numeric
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
FROM daily GROUP BY day_of_week, day_name ORDER BY day_of_week;

-- @query Q09_revenue_by_hour
-- @category Revenue
-- @description Revenue and orders by hour of purchase (local timestamp).
-- @output purchase_hour int, orders bigint, revenue numeric, pct_orders numeric
SELECT EXTRACT(HOUR FROM purchase_timestamp)::INT AS purchase_hour,
       count(*) AS orders, round(sum(revenue), 2) AS revenue,
       round(100.0 * count(*) / sum(count(*)) OVER (), 2) AS pct_orders
FROM nexus_dw.fact_orders WHERE is_revenue_order
GROUP BY 1 ORDER BY 1;

-- @query Q10_black_friday_impact
-- @category Revenue
-- @description Black Friday 2017 vs average of the 4 preceding same weekdays (dim_date flag).
-- @output full_date date, revenue numeric, orders bigint, baseline_revenue numeric, uplift_x numeric
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
FROM daily dl JOIN bf ON bf.full_date = dl.full_date;
