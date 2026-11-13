-- =====================================================================
-- INDEXES & OPTIMIZATION for nexus_dw
-- Rationale:
--  * FK columns used in star joins and in Power BI DirectQuery filters
--  * date keys are the most common filter -> B-tree on every fact date key
--  * partial index for the dominant "revenue orders" filter
--  * BRIN on purchase_timestamp: append-mostly, naturally ordered data
-- =====================================================================
CREATE INDEX IF NOT EXISTS ix_fo_customer      ON nexus_dw.fact_orders (customer_key);
CREATE INDEX IF NOT EXISTS ix_fo_purchase_date ON nexus_dw.fact_orders (purchase_date_key);
CREATE INDEX IF NOT EXISTS ix_fo_location      ON nexus_dw.fact_orders (customer_location_key);
CREATE INDEX IF NOT EXISTS ix_fo_status        ON nexus_dw.fact_orders (order_status);
CREATE INDEX IF NOT EXISTS ix_fo_revenue_only  ON nexus_dw.fact_orders (purchase_date_key) INCLUDE (revenue, customer_key)
    WHERE is_revenue_order;
CREATE INDEX IF NOT EXISTS brin_fo_purchase_ts ON nexus_dw.fact_orders USING brin (purchase_timestamp);

CREATE INDEX IF NOT EXISTS ix_foi_product      ON nexus_dw.fact_order_items (product_key);
CREATE INDEX IF NOT EXISTS ix_foi_seller       ON nexus_dw.fact_order_items (seller_key);
CREATE INDEX IF NOT EXISTS ix_foi_customer     ON nexus_dw.fact_order_items (customer_key);
CREATE INDEX IF NOT EXISTS ix_foi_date         ON nexus_dw.fact_order_items (purchase_date_key);

CREATE INDEX IF NOT EXISTS ix_fp_type          ON nexus_dw.fact_payments (payment_type_key);
CREATE INDEX IF NOT EXISTS ix_fp_date          ON nexus_dw.fact_payments (purchase_date_key);
CREATE INDEX IF NOT EXISTS ix_fr_order         ON nexus_dw.fact_reviews (order_id);
CREATE INDEX IF NOT EXISTS ix_fr_date          ON nexus_dw.fact_reviews (purchase_date_key);

CREATE INDEX IF NOT EXISTS ix_dc_unique        ON nexus_dw.dim_customer (customer_unique_id) WHERE is_current;
CREATE INDEX IF NOT EXISTS ix_dc_state         ON nexus_dw.dim_customer (state);
CREATE INDEX IF NOT EXISTS ix_dp_category      ON nexus_dw.dim_product (category_name_en);
CREATE INDEX IF NOT EXISTS ix_ds_state         ON nexus_dw.dim_seller (state);
CREATE INDEX IF NOT EXISTS ix_dd_month         ON nexus_dw.dim_date (month_start);

-- Planner statistics after bulk loads
ANALYZE nexus_dw.fact_orders;
ANALYZE nexus_dw.fact_order_items;
ANALYZE nexus_dw.fact_payments;
ANALYZE nexus_dw.fact_reviews;
ANALYZE nexus_dw.dim_customer;
