-- @query Q19_top_categories_revenue
-- @category Products
-- @description Top 15 categories by item revenue (item grain – no fan-out), with share and cumulative share (Pareto).
-- @output category text, units bigint, revenue numeric, revenue_share_pct numeric, cumulative_share_pct numeric
WITH c AS (
    SELECT p.category_display_name AS category, count(*) AS units, sum(i.price) AS revenue
    FROM nexus_dw.fact_order_items i JOIN nexus_dw.dim_product p ON p.product_key = i.product_key
    WHERE i.is_revenue_order GROUP BY 1
)
SELECT category, units, round(revenue, 2) AS revenue,
       round(100 * revenue / sum(revenue) OVER (), 2) AS revenue_share_pct,
       round(100 * sum(revenue) OVER (ORDER BY revenue DESC) / sum(revenue) OVER (), 2) AS cumulative_share_pct
FROM c ORDER BY revenue DESC LIMIT 15;

-- @query Q20_category_growth_2018_vs_2017
-- @category Products
-- @description Category revenue Jan–Aug 2018 vs Jan–Aug 2017 (from mv_monthly_category_sales).
-- @output category_name_en text, revenue_2017 numeric, revenue_2018 numeric, growth_pct numeric
SELECT category_name_en,
       round(sum(product_revenue) FILTER (WHERE month_start BETWEEN '2017-01-01' AND '2017-08-01'), 2) AS revenue_2017,
       round(sum(product_revenue) FILTER (WHERE month_start BETWEEN '2018-01-01' AND '2018-08-01'), 2) AS revenue_2018,
       round(100 * (sum(product_revenue) FILTER (WHERE month_start BETWEEN '2018-01-01' AND '2018-08-01')
             / NULLIF(sum(product_revenue) FILTER (WHERE month_start BETWEEN '2017-01-01' AND '2017-08-01'), 0) - 1), 1) AS growth_pct
FROM nexus_dw.mv_monthly_category_sales
GROUP BY category_name_en
HAVING sum(product_revenue) FILTER (WHERE month_start BETWEEN '2017-01-01' AND '2017-08-01') > 50000
ORDER BY growth_pct DESC;

-- @query Q21_category_rank_by_month
-- @category Products
-- @description Category rank per month (RANK partitioned by month) – top 3 categories for every month.
-- @output month_start date, category_name_en text, revenue numeric, month_rank bigint
SELECT * FROM (
    SELECT month_start, category_name_en, round(product_revenue, 2) AS revenue,
           RANK() OVER (PARTITION BY month_start ORDER BY product_revenue DESC) AS month_rank
    FROM nexus_dw.mv_monthly_category_sales
    WHERE month_start BETWEEN '2017-01-01' AND '2018-08-01'
) r WHERE month_rank <= 3 ORDER BY month_start, month_rank;

-- @query Q22_price_percentiles_by_category
-- @category Products
-- @description Price distribution (P10/P50/P90) per top category – percentile_cont.
-- @output category text, items bigint, p10 numeric, p50 numeric, p90 numeric, avg_price numeric
SELECT p.category_display_name AS category, count(*) AS items,
       round(percentile_cont(0.1) WITHIN GROUP (ORDER BY i.price)::NUMERIC, 2) AS p10,
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY i.price)::NUMERIC, 2) AS p50,
       round(percentile_cont(0.9) WITHIN GROUP (ORDER BY i.price)::NUMERIC, 2) AS p90,
       round(avg(i.price), 2) AS avg_price
FROM nexus_dw.fact_order_items i JOIN nexus_dw.dim_product p ON p.product_key = i.product_key
WHERE i.is_revenue_order
GROUP BY 1 HAVING count(*) >= 2000 ORDER BY p50 DESC;

-- @query Q23_freight_ratio_by_category
-- @category Products
-- @description Freight as % of item price per category – identifies categories where shipping cost erodes value.
-- @output category text, items bigint, avg_price numeric, avg_freight numeric, freight_ratio_pct numeric
SELECT p.category_display_name AS category, count(*) AS items, round(avg(i.price), 2) AS avg_price,
       round(avg(i.freight_value), 2) AS avg_freight,
       round(100 * sum(i.freight_value) / sum(i.price), 2) AS freight_ratio_pct
FROM nexus_dw.fact_order_items i JOIN nexus_dw.dim_product p ON p.product_key = i.product_key
WHERE i.is_revenue_order
GROUP BY 1 HAVING count(*) >= 1000 ORDER BY freight_ratio_pct DESC;

-- @query Q24_top_sellers_scorecard
-- @category Sellers
-- @description Top 20 sellers by GMV with operational KPIs (fan-out-safe view vw_seller_scorecard).
-- @output seller_id text, state text, orders bigint, gmv numeric, avg_review numeric, late_rate_pct numeric, gmv_rank bigint
SELECT seller_id, state, orders, round(gmv, 2) AS gmv, round(avg_review, 2) AS avg_review,
       round(100 * late_rate, 2) AS late_rate_pct, RANK() OVER (ORDER BY gmv DESC) AS gmv_rank
FROM nexus_dw.vw_seller_scorecard ORDER BY gmv DESC LIMIT 20;

-- @query Q25_seller_concentration
-- @category Sellers
-- @description Seller revenue concentration: share of GMV from top 1%, 5%, 10%, 20% of sellers.
-- @output top_pct_sellers int, sellers bigint, gmv_share_pct numeric
WITH s AS (SELECT seller_id, gmv, PERCENT_RANK() OVER (ORDER BY gmv DESC) AS pr FROM nexus_dw.vw_seller_scorecard),
t AS (SELECT unnest(ARRAY[1, 5, 10, 20]) AS top_pct)
SELECT t.top_pct AS top_pct_sellers, count(s.seller_id) AS sellers,
       round(100 * sum(s.gmv) / (SELECT sum(gmv) FROM nexus_dw.vw_seller_scorecard), 2) AS gmv_share_pct
FROM t JOIN s ON s.pr < t.top_pct / 100.0
GROUP BY t.top_pct ORDER BY t.top_pct;

-- @query Q26_seller_quality_quadrant
-- @category Sellers
-- @description Sellers (>=30 orders) classified into volume x review-quality quadrants relative to medians.
-- @output quadrant text, sellers bigint, gmv numeric, avg_review numeric
WITH s AS (SELECT * FROM nexus_dw.vw_seller_scorecard WHERE orders >= 30),
m AS (SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY orders) AS mo,
             percentile_cont(0.5) WITHIN GROUP (ORDER BY avg_review) AS mr FROM s)
SELECT CASE WHEN s.orders >= m.mo AND s.avg_review >= m.mr THEN 'Stars (high volume, high quality)'
            WHEN s.orders >= m.mo THEN 'Volume at risk (high volume, low quality)'
            WHEN s.avg_review >= m.mr THEN 'Growth candidates (low volume, high quality)'
            ELSE 'Watch list (low volume, low quality)' END AS quadrant,
       count(*) AS sellers, round(sum(s.gmv), 2) AS gmv, round(avg(s.avg_review), 2) AS avg_review
FROM s CROSS JOIN m GROUP BY 1 ORDER BY gmv DESC;

-- @query Q27_products_above_category_average
-- @category Products
-- @description Products whose avg price exceeds 2x their category average (top 20 by units). OPTIMISED: category averages computed once in a CTE + window function instead of a correlated subquery (measured 266 s -> well under 1 s on this dataset; see docs/database/SQL_QUERY_DOCUMENTATION.md).
-- @output product_id text, category text, units bigint, avg_price numeric, category_avg_price numeric
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
ORDER BY units DESC LIMIT 20;
