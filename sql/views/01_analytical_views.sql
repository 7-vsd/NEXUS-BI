-- =====================================================================
-- ANALYTICAL VIEWS (nexus_dw). Business-friendly, fan-out-safe views.
-- =====================================================================

-- Order-level view with customer & date attributes (grain: order)
CREATE OR REPLACE VIEW nexus_dw.vw_orders AS
SELECT f.order_id, f.order_status, f.purchase_timestamp, d.full_date AS purchase_date, d.year, d.quarter_label,
       d.year_month, d.month_start, c.customer_unique_id, c.state AS customer_state, c.region AS customer_region,
       c.city AS customer_city, pt.payment_type AS main_payment_type, f.is_revenue_order, f.is_canceled,
       f.is_delivered, f.is_on_time, f.is_late, f.items_count, f.items_price, f.freight_value, f.order_value,
       f.revenue, f.payment_value, f.delivery_days, f.estimated_delivery_days, f.delivery_delay_days, f.review_score
FROM nexus_dw.fact_orders f
JOIN nexus_dw.dim_date d          ON d.date_key = f.purchase_date_key
JOIN nexus_dw.dim_customer c      ON c.customer_key = f.customer_key
JOIN nexus_dw.dim_payment_type pt ON pt.payment_type_key = f.main_payment_type_key;

-- Item-level view (grain: order line) – the ONLY place category revenue should come from
CREATE OR REPLACE VIEW nexus_dw.vw_order_items AS
SELECT i.order_id, i.order_item_id, d.full_date AS purchase_date, d.year_month, d.month_start,
       p.product_id, p.category_name_en, p.category_display_name, s.seller_id, s.state AS seller_state,
       s.region AS seller_region, c.customer_unique_id, c.state AS customer_state,
       i.is_revenue_order, i.price, i.freight_value, i.line_total
FROM nexus_dw.fact_order_items i
JOIN nexus_dw.dim_date d     ON d.date_key = i.purchase_date_key
JOIN nexus_dw.dim_product p  ON p.product_key = i.product_key
JOIN nexus_dw.dim_seller s   ON s.seller_key = i.seller_key
JOIN nexus_dw.dim_customer c ON c.customer_key = i.customer_key;

-- Seller scorecard (each fact aggregated at its own grain before joining -> no fan-out)
CREATE OR REPLACE VIEW nexus_dw.vw_seller_scorecard AS
WITH items AS (
    SELECT seller_key, count(*) AS items_sold, count(DISTINCT order_id) AS orders, sum(price) AS gmv,
           sum(freight_value) AS freight
    FROM nexus_dw.fact_order_items WHERE is_revenue_order GROUP BY seller_key
), seller_orders AS (
    SELECT DISTINCT i.seller_key, i.order_id FROM nexus_dw.fact_order_items i
), ops AS (
    SELECT so.seller_key, avg(f.review_score) AS avg_review, avg(f.delivery_days) AS avg_delivery_days,
           avg(CASE WHEN f.is_late THEN 1.0 WHEN f.is_on_time THEN 0.0 END) AS late_rate,
           avg(CASE WHEN f.is_canceled THEN 1.0 ELSE 0.0 END) AS cancel_rate
    FROM seller_orders so JOIN nexus_dw.fact_orders f ON f.order_id = so.order_id GROUP BY so.seller_key
)
SELECT s.seller_id, s.city, s.state, s.region, i.items_sold, i.orders, i.gmv, i.freight,
       o.avg_review, o.avg_delivery_days, o.late_rate, o.cancel_rate
FROM nexus_dw.dim_seller s
JOIN items i ON i.seller_key = s.seller_key
LEFT JOIN ops o ON o.seller_key = s.seller_key;

-- Customer 360 at person level (customer_unique_id), across SCD2 versions
CREATE OR REPLACE VIEW nexus_dw.vw_customer_360 AS
SELECT c.customer_unique_id,
       max(c.state) FILTER (WHERE c.is_current) AS current_state,
       count(DISTINCT f.order_id) AS orders,
       sum(f.revenue) AS lifetime_revenue,
       min(f.purchase_timestamp) AS first_purchase, max(f.purchase_timestamp) AS last_purchase,
       avg(f.review_score) AS avg_review, count(DISTINCT c.customer_key) AS address_versions
FROM nexus_dw.dim_customer c
JOIN nexus_dw.fact_orders f ON f.customer_key = c.customer_key AND f.is_revenue_order
GROUP BY c.customer_unique_id;

-- Synthetic profitability (clearly labelled SIMULATED)
CREATE OR REPLACE VIEW nexus_dw.vw_syn_category_margin AS
SELECT p.category_name_en, sum(i.price) AS revenue, sum(sc.unit_cost_brl) AS simulated_cogs,
       sum(i.price) - sum(sc.unit_cost_brl) AS simulated_gross_margin,
       round(1 - sum(sc.unit_cost_brl) / NULLIF(sum(i.price), 0), 4) AS simulated_margin_pct,
       TRUE AS is_synthetic
FROM nexus_dw.fact_order_items i
JOIN nexus_dw.dim_product p ON p.product_key = i.product_key
JOIN nexus_dw.syn_product_cost sc ON sc.product_id = p.product_id
WHERE i.is_revenue_order
GROUP BY p.category_name_en;

-- ---------------------------------------------------------------------
-- MATERIALIZED VIEWS (refreshed by sp_refresh_materialized_views)
-- ---------------------------------------------------------------------
CREATE MATERIALIZED VIEW IF NOT EXISTS nexus_dw.mv_daily_kpis AS
SELECT d.full_date,
       sum(f.revenue) AS revenue,
       count(*) FILTER (WHERE f.is_revenue_order) AS orders,
       count(DISTINCT c.customer_unique_id) FILTER (WHERE f.is_revenue_order) AS customers,
       count(*) AS all_orders,
       count(*) FILTER (WHERE f.is_canceled) AS canceled_orders,
       count(*) FILTER (WHERE f.is_delivered) AS delivered_orders,
       count(*) FILTER (WHERE f.is_late) AS late_orders,
       avg(f.review_score) FILTER (WHERE f.is_revenue_order) AS avg_review
FROM nexus_dw.fact_orders f
JOIN nexus_dw.dim_date d ON d.date_key = f.purchase_date_key
JOIN nexus_dw.dim_customer c ON c.customer_key = f.customer_key
GROUP BY d.full_date
WITH NO DATA;
CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_daily_kpis ON nexus_dw.mv_daily_kpis (full_date);

CREATE MATERIALIZED VIEW IF NOT EXISTS nexus_dw.mv_monthly_category_sales AS
SELECT d.month_start, p.category_name_en, count(*) AS units, sum(i.price) AS product_revenue,
       sum(i.line_total) AS revenue, count(DISTINCT i.order_id) AS orders
FROM nexus_dw.fact_order_items i
JOIN nexus_dw.dim_date d ON d.date_key = i.purchase_date_key
JOIN nexus_dw.dim_product p ON p.product_key = i.product_key
WHERE i.is_revenue_order
GROUP BY d.month_start, p.category_name_en
WITH NO DATA;
CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_monthly_cat ON nexus_dw.mv_monthly_category_sales (month_start, category_name_en);

CREATE MATERIALIZED VIEW IF NOT EXISTS nexus_dw.mv_customer_rfm AS
WITH snap AS (SELECT max(purchase_timestamp)::DATE + 1 AS snapshot_date FROM nexus_dw.fact_orders),
base AS (
    SELECT c.customer_unique_id,
           (SELECT snapshot_date FROM snap) - max(f.purchase_timestamp)::DATE AS recency_days,
           count(DISTINCT f.order_id) AS frequency,
           sum(f.revenue) AS monetary
    FROM nexus_dw.fact_orders f
    JOIN nexus_dw.dim_customer c ON c.customer_key = f.customer_key
    WHERE f.is_revenue_order AND f.items_count > 0
    GROUP BY c.customer_unique_id
)
SELECT b.*,
       6 - ntile(5) OVER (ORDER BY recency_days) AS r_score,
       CASE WHEN frequency >= 3 THEN 5 WHEN frequency = 2 THEN 4 ELSE 1 END AS f_score,
       ntile(5) OVER (ORDER BY monetary) AS m_score
FROM base b
WITH NO DATA;
CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_rfm ON nexus_dw.mv_customer_rfm (customer_unique_id);
