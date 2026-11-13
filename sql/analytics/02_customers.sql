-- @query Q11_repeat_customer_rate
-- @category Customers
-- @description Share of customers (customer_unique_id) with more than one revenue order.
-- @output customers bigint, repeat_customers bigint, repeat_rate_pct numeric, repeat_revenue_share_pct numeric
WITH c AS (
    SELECT dc.customer_unique_id, count(*) AS orders, sum(f.revenue) AS revenue
    FROM nexus_dw.fact_orders f JOIN nexus_dw.dim_customer dc ON dc.customer_key = f.customer_key
    WHERE f.is_revenue_order AND f.items_count > 0
    GROUP BY dc.customer_unique_id
)
SELECT count(*) AS customers, count(*) FILTER (WHERE orders > 1) AS repeat_customers,
       round(100.0 * count(*) FILTER (WHERE orders > 1) / count(*), 3) AS repeat_rate_pct,
       round(100.0 * sum(revenue) FILTER (WHERE orders > 1) / sum(revenue), 3) AS repeat_revenue_share_pct
FROM c;

-- @query Q12_order_frequency_distribution
-- @category Customers
-- @description Distribution of customers by number of orders.
-- @output orders_per_customer bigint, customers bigint, pct_customers numeric
WITH c AS (
    SELECT dc.customer_unique_id, count(*) AS n
    FROM nexus_dw.fact_orders f JOIN nexus_dw.dim_customer dc ON dc.customer_key = f.customer_key
    WHERE f.is_revenue_order AND f.items_count > 0 GROUP BY 1
)
SELECT LEAST(n, 5) AS orders_per_customer, count(*) AS customers,
       round(100.0 * count(*) / sum(count(*)) OVER (), 3) AS pct_customers
FROM c GROUP BY 1 ORDER BY 1;

-- @query Q13_customer_lifetime_value_estimate
-- @category Customers
-- @description Historical CLV estimate = AOV x purchase frequency x observed lifespan factor; plus revenue deciles (NTILE).
-- @output decile int, customers bigint, avg_revenue numeric, min_revenue numeric, max_revenue numeric, revenue_share_pct numeric
WITH c AS (
    SELECT dc.customer_unique_id, sum(f.revenue) AS revenue
    FROM nexus_dw.fact_orders f JOIN nexus_dw.dim_customer dc ON dc.customer_key = f.customer_key
    WHERE f.is_revenue_order AND f.items_count > 0 GROUP BY 1
), d AS (SELECT *, ntile(10) OVER (ORDER BY revenue DESC) AS decile FROM c)
SELECT decile, count(*) AS customers, round(avg(revenue), 2) AS avg_revenue,
       round(min(revenue), 2) AS min_revenue, round(max(revenue), 2) AS max_revenue,
       round(100 * sum(revenue) / sum(sum(revenue)) OVER (), 2) AS revenue_share_pct
FROM d GROUP BY decile ORDER BY decile;

-- @query Q14_clv_formula_by_state
-- @category Customers
-- @description Simple CLV estimate per customer state: AOV x avg orders per customer (historical, BRL).
-- @output state text, customers bigint, aov numeric, orders_per_customer numeric, est_clv numeric
WITH c AS (
    SELECT dc.customer_unique_id, max(dc.state) AS state, count(*) AS orders, sum(f.revenue) AS revenue
    FROM nexus_dw.fact_orders f JOIN nexus_dw.dim_customer dc ON dc.customer_key = f.customer_key
    WHERE f.is_revenue_order AND f.items_count > 0 GROUP BY 1
)
SELECT state, count(*) AS customers, round(sum(revenue) / sum(orders), 2) AS aov,
       round(avg(orders), 4) AS orders_per_customer,
       round(sum(revenue) / sum(orders) * avg(orders), 2) AS est_clv
FROM c GROUP BY state HAVING count(*) >= 100 ORDER BY est_clv DESC;

-- @query Q15_top_customers_ranking
-- @category Customers
-- @description Top 20 customers by lifetime revenue with RANK and DENSE_RANK.
-- @output customer_unique_id text, orders bigint, lifetime_revenue numeric, revenue_rank bigint, dense_rank bigint
SELECT customer_unique_id, orders, round(lifetime_revenue, 2) AS lifetime_revenue,
       RANK() OVER (ORDER BY lifetime_revenue DESC) AS revenue_rank,
       DENSE_RANK() OVER (ORDER BY orders DESC) AS dense_rank
FROM nexus_dw.vw_customer_360
ORDER BY lifetime_revenue DESC LIMIT 20;

-- @query Q16_days_between_purchases
-- @category Customers
-- @description For repeat customers: days between consecutive orders (LAG) – median and percentiles.
-- @output repeat_gaps bigint, p25_days numeric, median_days numeric, p75_days numeric, mean_days numeric
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
FROM g;

-- @query Q17_rfm_segment_summary
-- @category Customers
-- @description RFM segments from the materialized view mv_customer_rfm (rule-based labelling).
-- @output rfm_segment text, customers bigint, avg_recency numeric, avg_frequency numeric, avg_monetary numeric, revenue_share_pct numeric
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
FROM s GROUP BY rfm_segment ORDER BY customers DESC;

-- @query Q18_customers_with_address_changes
-- @category Customers
-- @description SCD Type 2 insight: customers whose address changed between orders.
-- @output customers_with_changes bigint, total_versions bigint, max_versions int
SELECT count(*) FILTER (WHERE address_versions > 1) AS customers_with_changes,
       sum(address_versions) AS total_versions, max(address_versions) AS max_versions
FROM nexus_dw.vw_customer_360;
