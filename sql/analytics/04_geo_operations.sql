-- @query Q28_revenue_by_state
-- @category Geography
-- @description Revenue, orders, AOV and share by customer state.
-- @output state text, region text, orders bigint, revenue numeric, aov numeric, revenue_share_pct numeric
SELECT c.state, c.region, count(*) AS orders, round(sum(f.revenue), 2) AS revenue,
       round(sum(f.revenue) / count(*), 2) AS aov,
       round(100 * sum(f.revenue) / sum(sum(f.revenue)) OVER (), 2) AS revenue_share_pct
FROM nexus_dw.fact_orders f JOIN nexus_dw.dim_customer c ON c.customer_key = f.customer_key
WHERE f.is_revenue_order GROUP BY c.state, c.region ORDER BY revenue DESC;

-- @query Q29_region_performance
-- @category Geography
-- @description Macro-region scorecard: revenue, delivery time, on-time rate and review score.
-- @output region text, orders bigint, revenue numeric, avg_delivery_days numeric, on_time_pct numeric, avg_review numeric
SELECT c.region, count(*) AS orders, round(sum(f.revenue), 2) AS revenue,
       round(avg(f.delivery_days), 2) AS avg_delivery_days,
       round(100 * avg(CASE WHEN f.is_on_time THEN 1.0 WHEN f.is_late THEN 0.0 END), 2) AS on_time_pct,
       round(avg(f.review_score), 3) AS avg_review
FROM nexus_dw.fact_orders f JOIN nexus_dw.dim_customer c ON c.customer_key = f.customer_key
WHERE f.is_revenue_order GROUP BY c.region ORDER BY revenue DESC;

-- @query Q30_top_cities
-- @category Geography
-- @description Top 15 customer cities by revenue.
-- @output city text, state text, customers bigint, revenue numeric
SELECT c.city, c.state, count(DISTINCT c.customer_unique_id) AS customers, round(sum(f.revenue), 2) AS revenue
FROM nexus_dw.fact_orders f JOIN nexus_dw.dim_customer c ON c.customer_key = f.customer_key
WHERE f.is_revenue_order GROUP BY c.city, c.state ORDER BY revenue DESC LIMIT 15;

-- @query Q31_intra_vs_inter_state_shipping
-- @category Operations
-- @description Same-state vs cross-state seller->customer shipments: delivery time, freight and late rate (item grain, delivered orders).
-- @output route_type text, items bigint, avg_freight numeric, avg_delivery_days numeric, late_rate_pct numeric
SELECT CASE WHEN s.state = c.state THEN 'Same state' ELSE 'Cross state' END AS route_type,
       count(*) AS items, round(avg(i.freight_value), 2) AS avg_freight,
       round(avg(f.delivery_days), 2) AS avg_delivery_days,
       round(100 * avg(CASE WHEN f.is_late THEN 1.0 ELSE 0.0 END), 2) AS late_rate_pct
FROM nexus_dw.fact_order_items i
JOIN nexus_dw.fact_orders f ON f.order_id = i.order_id
JOIN nexus_dw.dim_seller s ON s.seller_key = i.seller_key
JOIN nexus_dw.dim_customer c ON c.customer_key = i.customer_key
WHERE f.is_delivered GROUP BY 1;

-- @query Q32_delivery_performance_monthly
-- @category Operations
-- @description Monthly delivery KPIs for delivered orders: avg/median days, on-time %, avg delay of late orders.
-- @output month_start date, delivered bigint, avg_days numeric, median_days numeric, on_time_pct numeric, avg_late_delay numeric
SELECT d.month_start, count(*) AS delivered, round(avg(f.delivery_days), 2) AS avg_days,
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY f.delivery_days)::NUMERIC, 2) AS median_days,
       round(100 * avg(CASE WHEN f.is_on_time THEN 1.0 ELSE 0.0 END), 2) AS on_time_pct,
       round(avg(f.delivery_delay_days) FILTER (WHERE f.is_late), 2) AS avg_late_delay
FROM nexus_dw.fact_orders f JOIN nexus_dw.dim_date d ON d.date_key = f.purchase_date_key
WHERE f.is_delivered GROUP BY d.month_start ORDER BY d.month_start;

-- @query Q33_late_delivery_by_state
-- @category Operations
-- @description Late-delivery rate and estimated-vs-actual gap per customer state (states with >=500 deliveries).
-- @output state text, delivered bigint, late_rate_pct numeric, avg_actual_days numeric, avg_estimated_days numeric, avg_buffer_days numeric
SELECT c.state, count(*) AS delivered,
       round(100 * avg(CASE WHEN f.is_late THEN 1.0 ELSE 0.0 END), 2) AS late_rate_pct,
       round(avg(f.delivery_days), 2) AS avg_actual_days, round(avg(f.estimated_delivery_days), 2) AS avg_estimated_days,
       round(avg(f.estimated_delivery_days - f.delivery_days), 2) AS avg_buffer_days
FROM nexus_dw.fact_orders f JOIN nexus_dw.dim_customer c ON c.customer_key = f.customer_key
WHERE f.is_delivered GROUP BY c.state HAVING count(*) >= 500 ORDER BY late_rate_pct DESC;

-- @query Q34_delivery_time_percentiles
-- @category Operations
-- @description Delivery-time percentiles (P50/P75/P90/P95/P99) – service-level view.
-- @output p50 numeric, p75 numeric, p90 numeric, p95 numeric, p99 numeric
SELECT round(percentile_cont(0.50) WITHIN GROUP (ORDER BY delivery_days)::NUMERIC, 1) AS p50,
       round(percentile_cont(0.75) WITHIN GROUP (ORDER BY delivery_days)::NUMERIC, 1) AS p75,
       round(percentile_cont(0.90) WITHIN GROUP (ORDER BY delivery_days)::NUMERIC, 1) AS p90,
       round(percentile_cont(0.95) WITHIN GROUP (ORDER BY delivery_days)::NUMERIC, 1) AS p95,
       round(percentile_cont(0.99) WITHIN GROUP (ORDER BY delivery_days)::NUMERIC, 1) AS p99
FROM nexus_dw.fact_orders WHERE is_delivered;

-- @query Q35_cancellation_analysis
-- @category Operations
-- @description Order status mix and cancellation/unavailability rate by month.
-- @output month_start date, all_orders bigint, canceled bigint, unavailable bigint, cancel_rate_pct numeric
SELECT d.month_start, count(*) AS all_orders,
       count(*) FILTER (WHERE f.order_status = 'canceled') AS canceled,
       count(*) FILTER (WHERE f.order_status = 'unavailable') AS unavailable,
       round(100.0 * count(*) FILTER (WHERE f.order_status IN ('canceled', 'unavailable')) / count(*), 3) AS cancel_rate_pct
FROM nexus_dw.fact_orders f JOIN nexus_dw.dim_date d ON d.date_key = f.purchase_date_key
GROUP BY d.month_start ORDER BY d.month_start;

-- @query Q36_order_status_distribution
-- @category Operations
-- @description Order status distribution with value at stake.
-- @output order_status text, orders bigint, pct_orders numeric, order_value numeric
SELECT order_status, count(*) AS orders, round(100.0 * count(*) / sum(count(*)) OVER (), 3) AS pct_orders,
       round(sum(order_value), 2) AS order_value
FROM nexus_dw.fact_orders GROUP BY order_status ORDER BY orders DESC;
