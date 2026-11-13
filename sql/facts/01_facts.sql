-- =====================================================================
-- FACT TABLES (nexus_dw)
-- Each fact has an explicit grain. Order-level money lives ONLY in
-- fact_orders; item-level money ONLY in fact_order_items. Never join
-- fact_order_items to fact_payments directly (fan-out) – aggregate first
-- or go through the shared dimensions.
-- =====================================================================

-- GRAIN: one row per order (order_id)
CREATE TABLE IF NOT EXISTS nexus_dw.fact_orders (
    order_id                VARCHAR(32) PRIMARY KEY,
    customer_key            INTEGER  NOT NULL REFERENCES nexus_dw.dim_customer (customer_key),
    customer_location_key   INTEGER  NOT NULL REFERENCES nexus_dw.dim_location (location_key),
    purchase_date_key       INTEGER  NOT NULL REFERENCES nexus_dw.dim_date (date_key),
    approved_date_key       INTEGER  REFERENCES nexus_dw.dim_date (date_key),
    delivered_date_key      INTEGER  REFERENCES nexus_dw.dim_date (date_key),
    estimated_date_key      INTEGER  REFERENCES nexus_dw.dim_date (date_key),
    main_payment_type_key   SMALLINT NOT NULL REFERENCES nexus_dw.dim_payment_type (payment_type_key),
    order_status            VARCHAR(20) NOT NULL,
    purchase_timestamp      TIMESTAMP NOT NULL,
    is_revenue_order        BOOLEAN  NOT NULL,
    is_canceled             BOOLEAN  NOT NULL,
    is_delivered            BOOLEAN  NOT NULL,
    is_on_time              BOOLEAN,
    is_late                 BOOLEAN,
    items_count             SMALLINT NOT NULL,
    distinct_sellers        SMALLINT NOT NULL,
    items_price             NUMERIC(14,2) NOT NULL,
    freight_value           NUMERIC(14,2) NOT NULL,
    order_value             NUMERIC(14,2) NOT NULL,   -- items_price + freight_value
    revenue                 NUMERIC(14,2) NOT NULL,   -- order_value if revenue order else 0
    payment_value           NUMERIC(14,2) NOT NULL,
    payment_count           SMALLINT NOT NULL,
    approval_hours          NUMERIC(10,2),
    delivery_days           NUMERIC(10,2),
    estimated_delivery_days NUMERIC(10,2),
    delivery_delay_days     INTEGER,
    review_score            SMALLINT,                 -- latest review for the order
    loaded_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- GRAIN: one row per order line (order_id, order_item_id)
CREATE TABLE IF NOT EXISTS nexus_dw.fact_order_items (
    order_id                 VARCHAR(32) NOT NULL REFERENCES nexus_dw.fact_orders (order_id),
    order_item_id            SMALLINT NOT NULL,
    product_key              INTEGER  NOT NULL REFERENCES nexus_dw.dim_product (product_key),
    seller_key               INTEGER  NOT NULL REFERENCES nexus_dw.dim_seller (seller_key),
    customer_key             INTEGER  NOT NULL REFERENCES nexus_dw.dim_customer (customer_key),
    purchase_date_key        INTEGER  NOT NULL REFERENCES nexus_dw.dim_date (date_key),
    shipping_limit_date_key  INTEGER  REFERENCES nexus_dw.dim_date (date_key),
    order_status             VARCHAR(20) NOT NULL,
    is_revenue_order         BOOLEAN NOT NULL,
    price                    NUMERIC(12,2) NOT NULL,
    freight_value            NUMERIC(12,2) NOT NULL,
    line_total               NUMERIC(12,2) NOT NULL,
    PRIMARY KEY (order_id, order_item_id)
);

-- GRAIN: one row per payment transaction (order_id, payment_sequential)
CREATE TABLE IF NOT EXISTS nexus_dw.fact_payments (
    order_id             VARCHAR(32) NOT NULL REFERENCES nexus_dw.fact_orders (order_id),
    payment_sequential   SMALLINT NOT NULL,
    payment_type_key     SMALLINT NOT NULL REFERENCES nexus_dw.dim_payment_type (payment_type_key),
    customer_key         INTEGER  NOT NULL REFERENCES nexus_dw.dim_customer (customer_key),
    purchase_date_key    INTEGER  NOT NULL REFERENCES nexus_dw.dim_date (date_key),
    payment_installments SMALLINT NOT NULL,
    payment_value        NUMERIC(12,2) NOT NULL,
    is_revenue_order     BOOLEAN NOT NULL,
    PRIMARY KEY (order_id, payment_sequential)
);

-- GRAIN: one row per review response per order (review_id, order_id)
CREATE TABLE IF NOT EXISTS nexus_dw.fact_reviews (
    review_id            VARCHAR(32) NOT NULL,
    order_id             VARCHAR(32) NOT NULL REFERENCES nexus_dw.fact_orders (order_id),
    customer_key         INTEGER NOT NULL REFERENCES nexus_dw.dim_customer (customer_key),
    purchase_date_key    INTEGER NOT NULL REFERENCES nexus_dw.dim_date (date_key),
    review_date_key      INTEGER REFERENCES nexus_dw.dim_date (date_key),
    answer_date_key      INTEGER REFERENCES nexus_dw.dim_date (date_key),
    review_score         SMALLINT NOT NULL CHECK (review_score BETWEEN 1 AND 5),
    has_comment          BOOLEAN NOT NULL,
    has_title            BOOLEAN NOT NULL,
    response_hours       NUMERIC(10,2),
    is_latest_for_order  BOOLEAN NOT NULL,
    PRIMARY KEY (review_id, order_id)
);

-- SYNTHETIC tables (clearly prefixed syn_ ; never real findings) -------
CREATE TABLE IF NOT EXISTS nexus_dw.syn_product_cost (
    product_id      VARCHAR(32) PRIMARY KEY,
    category_name_en TEXT,
    median_price    NUMERIC(12,2),
    cost_ratio      NUMERIC(6,4),
    unit_cost_brl   NUMERIC(12,2),
    is_synthetic    BOOLEAN NOT NULL DEFAULT TRUE CHECK (is_synthetic)
);

CREATE TABLE IF NOT EXISTS nexus_dw.syn_inventory_weekly (
    category         TEXT NOT NULL,
    week_start       DATE NOT NULL,
    opening_stock    INTEGER, received_units INTEGER, demand_units INTEGER,
    fulfilled_units  INTEGER, lost_sales_units INTEGER, closing_stock INTEGER,
    reorder_point    INTEGER, is_stockout BOOLEAN,
    is_synthetic     BOOLEAN NOT NULL DEFAULT TRUE CHECK (is_synthetic),
    PRIMARY KEY (category, week_start)
);
