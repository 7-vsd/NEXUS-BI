-- @query Q37_payment_mix
-- @category Payments
-- @description Payment method mix by transactions and value (payment grain).
-- @output payment_type_label text, transactions bigint, payment_value numeric, value_share_pct numeric, avg_installments numeric
SELECT pt.payment_type_label, count(*) AS transactions, round(sum(p.payment_value), 2) AS payment_value,
       round(100 * sum(p.payment_value) / sum(sum(p.payment_value)) OVER (), 2) AS value_share_pct,
       round(avg(p.payment_installments), 2) AS avg_installments
FROM nexus_dw.fact_payments p JOIN nexus_dw.dim_payment_type pt ON pt.payment_type_key = p.payment_type_key
GROUP BY pt.payment_type_label ORDER BY payment_value DESC;

-- @query Q38_installments_vs_order_value
-- @category Payments
-- @description Credit-card installments bands vs average order value.
-- @output installment_band text, orders bigint, avg_order_value numeric
WITH cc AS (
    SELECT p.order_id, max(p.payment_installments) AS inst
    FROM nexus_dw.fact_payments p JOIN nexus_dw.dim_payment_type pt ON pt.payment_type_key = p.payment_type_key
    WHERE pt.payment_type = 'credit_card' GROUP BY p.order_id
)
SELECT CASE WHEN inst = 1 THEN '1 (single)' WHEN inst <= 3 THEN '2-3' WHEN inst <= 6 THEN '4-6'
            WHEN inst <= 10 THEN '7-10' ELSE '11+' END AS installment_band,
       count(*) AS orders, round(avg(f.order_value), 2) AS avg_order_value
FROM cc JOIN nexus_dw.fact_orders f ON f.order_id = cc.order_id
GROUP BY 1 ORDER BY min(inst);

-- @query Q39_review_score_distribution
-- @category Reviews
-- @description Review score distribution (all responses, review grain).
-- @output review_score smallint, reviews bigint, pct numeric, with_comment_pct numeric
SELECT review_score, count(*) AS reviews, round(100.0 * count(*) / sum(count(*)) OVER (), 2) AS pct,
       round(100 * avg(CASE WHEN has_comment THEN 1.0 ELSE 0.0 END), 2) AS with_comment_pct
FROM nexus_dw.fact_reviews GROUP BY review_score ORDER BY review_score;

-- @query Q40_review_vs_delivery_delay
-- @category Reviews
-- @description Average review score by delivery-delay bucket – quantifies the satisfaction cost of lateness.
-- @output delay_bucket text, orders bigint, avg_review numeric, pct_1_star numeric
SELECT CASE WHEN delivery_delay_days <= -10 THEN 'a) 10+ days early'
            WHEN delivery_delay_days <= -1 THEN 'b) 1-9 days early'
            WHEN delivery_delay_days = 0 THEN 'c) on estimated day'
            WHEN delivery_delay_days <= 5 THEN 'd) 1-5 days late'
            WHEN delivery_delay_days <= 15 THEN 'e) 6-15 days late'
            ELSE 'f) 16+ days late' END AS delay_bucket,
       count(*) AS orders, round(avg(review_score), 3) AS avg_review,
       round(100 * avg(CASE WHEN review_score = 1 THEN 1.0 ELSE 0.0 END), 2) AS pct_1_star
FROM nexus_dw.fact_orders WHERE is_delivered AND review_score IS NOT NULL
GROUP BY 1 ORDER BY 1;

-- @query Q41_review_by_category_worst
-- @category Reviews
-- @description Categories with the lowest average review (>= 500 reviewed orders) – order-level review joined at item grain deduplicated per order.
-- @output category text, orders bigint, avg_review numeric
WITH oc AS (
    SELECT DISTINCT i.order_id, p.category_display_name AS category
    FROM nexus_dw.fact_order_items i JOIN nexus_dw.dim_product p ON p.product_key = i.product_key
)
SELECT oc.category, count(*) AS orders, round(avg(f.review_score), 3) AS avg_review
FROM oc JOIN nexus_dw.fact_orders f ON f.order_id = oc.order_id
WHERE f.review_score IS NOT NULL
GROUP BY oc.category HAVING count(*) >= 500 ORDER BY avg_review ASC LIMIT 15;

-- @query Q42_monthly_cohort_retention
-- @category Cohorts
-- @description Monthly acquisition cohorts: % of customers ordering again in months 1..6 after first purchase.
-- @output cohort_month date, cohort_size bigint, m1_pct numeric, m2_pct numeric, m3_pct numeric, m4_pct numeric, m5_pct numeric, m6_pct numeric
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
GROUP BY cohort ORDER BY cohort;

-- @query Q43_cohort_revenue_ltv
-- @category Cohorts
-- @description Cumulative revenue per acquired customer by cohort quarter (LTV curve, months since acquisition 0..6).
-- @output cohort_quarter text, customers bigint, ltv_m0 numeric, ltv_m3 numeric, ltv_m6 numeric
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
GROUP BY 1 ORDER BY 1;

-- @query Q44_simulated_category_margin
-- @category Profitability (SIMULATED)
-- @description SIMULATED gross margin by category using synthetic unit costs – NOT a real finding.
-- @output category_name_en text, revenue numeric, simulated_cogs numeric, simulated_margin_pct numeric, is_synthetic boolean
SELECT category_name_en, round(revenue, 2) AS revenue, round(simulated_cogs, 2) AS simulated_cogs,
       simulated_margin_pct, is_synthetic
FROM nexus_dw.vw_syn_category_margin ORDER BY revenue DESC LIMIT 15;

-- @query Q45_simulated_stockout_summary
-- @category Inventory (SIMULATED)
-- @description SIMULATED stock-out weeks and lost units per category from the synthetic inventory model – NOT a real finding.
-- @output category text, weeks bigint, stockout_weeks bigint, lost_units bigint, is_synthetic boolean
SELECT category, count(*) AS weeks, count(*) FILTER (WHERE is_stockout) AS stockout_weeks,
       sum(lost_sales_units) AS lost_units, bool_and(is_synthetic) AS is_synthetic
FROM nexus_dw.syn_inventory_weekly GROUP BY category ORDER BY lost_units DESC LIMIT 10;
