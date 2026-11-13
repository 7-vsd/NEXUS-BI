-- =====================================================================
-- STAGING LAYER: typed, cleaned output of the Python ETL (src/transformation).
-- Natural primary keys are enforced here so duplicates fail fast.
-- =====================================================================
CREATE TABLE IF NOT EXISTS nexus_staging.customers (
    customer_id              VARCHAR(32) PRIMARY KEY,
    customer_unique_id       VARCHAR(32) NOT NULL,
    customer_zip_code_prefix CHAR(5)     NOT NULL,
    customer_city            TEXT,
    customer_state           CHAR(2)     NOT NULL
);

CREATE TABLE IF NOT EXISTS nexus_staging.sellers (
    seller_id              VARCHAR(32) PRIMARY KEY,
    seller_zip_code_prefix CHAR(5)     NOT NULL,
    seller_city            TEXT,
    seller_state           CHAR(2)     NOT NULL
);

CREATE TABLE IF NOT EXISTS nexus_staging.geolocation (
    zip_code_prefix CHAR(5) PRIMARY KEY,
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    sample_points   INTEGER,
    city            TEXT,
    state           CHAR(2)
);

CREATE TABLE IF NOT EXISTS nexus_staging.category_translation (
    product_category_name         TEXT PRIMARY KEY,
    product_category_name_english TEXT NOT NULL,
    category_display_name         TEXT
);

CREATE TABLE IF NOT EXISTS nexus_staging.products (
    product_id                    VARCHAR(32) PRIMARY KEY,
    product_category_name         TEXT NOT NULL,
    product_name_length           INTEGER,
    product_description_length    INTEGER,
    product_photos_qty            INTEGER,
    product_weight_g              NUMERIC(10,2),
    product_length_cm             NUMERIC(10,2),
    product_height_cm             NUMERIC(10,2),
    product_width_cm              NUMERIC(10,2),
    product_category_name_english TEXT,
    product_volume_cm3            NUMERIC(14,2)
);

CREATE TABLE IF NOT EXISTS nexus_staging.orders (
    order_id                      VARCHAR(32) PRIMARY KEY,
    customer_id                   VARCHAR(32) NOT NULL,
    order_status                  VARCHAR(20) NOT NULL,
    order_purchase_timestamp      TIMESTAMP   NOT NULL,
    order_approved_at             TIMESTAMP,
    order_delivered_carrier_date  TIMESTAMP,
    order_delivered_customer_date TIMESTAMP,
    order_estimated_delivery_date TIMESTAMP
);

CREATE TABLE IF NOT EXISTS nexus_staging.order_items (
    order_id            VARCHAR(32) NOT NULL,
    order_item_id       SMALLINT    NOT NULL,
    product_id          VARCHAR(32) NOT NULL,
    seller_id           VARCHAR(32) NOT NULL,
    shipping_limit_date TIMESTAMP,
    price               NUMERIC(12,2) NOT NULL CHECK (price > 0),
    freight_value       NUMERIC(12,2) NOT NULL CHECK (freight_value >= 0),
    PRIMARY KEY (order_id, order_item_id)
);

CREATE TABLE IF NOT EXISTS nexus_staging.payments (
    order_id             VARCHAR(32) NOT NULL,
    payment_sequential   SMALLINT    NOT NULL,
    payment_type         VARCHAR(20) NOT NULL,
    payment_installments SMALLINT    NOT NULL CHECK (payment_installments >= 1),
    payment_value        NUMERIC(12,2) NOT NULL,
    PRIMARY KEY (order_id, payment_sequential)
);

CREATE TABLE IF NOT EXISTS nexus_staging.reviews (
    review_id               VARCHAR(32) NOT NULL,
    order_id                VARCHAR(32) NOT NULL,
    review_score            SMALLINT    NOT NULL CHECK (review_score BETWEEN 1 AND 5),
    review_comment_title    TEXT,
    review_comment_message  TEXT,
    review_creation_date    TIMESTAMP,
    review_answer_timestamp TIMESTAMP,
    PRIMARY KEY (review_id, order_id)
);

CREATE INDEX IF NOT EXISTS ix_stg_orders_customer  ON nexus_staging.orders (customer_id);
CREATE INDEX IF NOT EXISTS ix_stg_orders_purchase  ON nexus_staging.orders (order_purchase_timestamp);
CREATE INDEX IF NOT EXISTS ix_stg_customers_unique ON nexus_staging.customers (customer_unique_id);
CREATE INDEX IF NOT EXISTS ix_stg_reviews_order    ON nexus_staging.reviews (order_id);
