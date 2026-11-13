-- =====================================================================
-- DIMENSIONS (nexus_dw). Surrogate keys; key -1 = "Unknown" member so that
-- facts never lose rows through failed lookups.
-- =====================================================================

-- DIM_DATE: one row per calendar day ---------------------------------
CREATE TABLE IF NOT EXISTS nexus_dw.dim_date (
    date_key        INTEGER PRIMARY KEY,          -- YYYYMMDD
    full_date       DATE    NOT NULL UNIQUE,
    year            SMALLINT NOT NULL,
    quarter         SMALLINT NOT NULL,
    quarter_label   CHAR(7)  NOT NULL,            -- 2017-Q4
    month           SMALLINT NOT NULL,
    month_name      VARCHAR(9) NOT NULL,
    month_short     CHAR(3)  NOT NULL,
    year_month      CHAR(7)  NOT NULL,            -- 2017-11
    month_start     DATE     NOT NULL,
    iso_week        SMALLINT NOT NULL,
    week_start      DATE     NOT NULL,            -- Monday
    day_of_month    SMALLINT NOT NULL,
    day_of_week     SMALLINT NOT NULL,            -- 1=Mon..7=Sun
    day_name        VARCHAR(9) NOT NULL,
    is_weekend      BOOLEAN  NOT NULL,
    is_holiday_br   BOOLEAN  NOT NULL DEFAULT FALSE,
    holiday_name    TEXT,
    is_black_friday BOOLEAN  NOT NULL DEFAULT FALSE
);

-- DIM_LOCATION: one row per 5-digit zip-code prefix -------------------
CREATE TABLE IF NOT EXISTS nexus_dw.dim_location (
    location_key    INTEGER PRIMARY KEY,
    zip_code_prefix CHAR(5)  NOT NULL UNIQUE,
    city            TEXT,
    state           CHAR(2),
    region          VARCHAR(12),                  -- Norte, Nordeste, Centro-Oeste, Sudeste, Sul
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    has_coordinates BOOLEAN NOT NULL
);

-- DIM_CUSTOMER: SCD TYPE 2 on customer address -------------------------
-- Grain: one row per (customer_unique_id, address version). A new version is
-- opened when a returning customer orders from a different zip/city/state.
CREATE TABLE IF NOT EXISTS nexus_dw.dim_customer (
    customer_key       INTEGER PRIMARY KEY,
    customer_unique_id VARCHAR(32) NOT NULL,
    zip_code_prefix    CHAR(5),
    city               TEXT,
    state              CHAR(2),
    region             VARCHAR(12),
    location_key       INTEGER NOT NULL REFERENCES nexus_dw.dim_location (location_key),
    version_number     SMALLINT NOT NULL,
    valid_from         TIMESTAMP NOT NULL,
    valid_to           TIMESTAMP NOT NULL,        -- 9999-12-31 for the current version
    is_current         BOOLEAN NOT NULL,
    first_order_date   DATE,
    UNIQUE (customer_unique_id, version_number)
);

-- Bridge from the order-scoped source customer_id to the SCD2 customer_key
CREATE TABLE IF NOT EXISTS nexus_dw.map_customer_id (
    customer_id  VARCHAR(32) PRIMARY KEY,
    customer_key INTEGER NOT NULL REFERENCES nexus_dw.dim_customer (customer_key)
);

-- DIM_PRODUCT: SCD TYPE 1 (overwrite) ---------------------------------
CREATE TABLE IF NOT EXISTS nexus_dw.dim_product (
    product_key                INTEGER PRIMARY KEY,
    product_id                 VARCHAR(32) NOT NULL UNIQUE,
    category_name_pt           TEXT NOT NULL,
    category_name_en           TEXT NOT NULL,
    category_display_name      TEXT NOT NULL,
    product_name_length        INTEGER,
    product_description_length INTEGER,
    product_photos_qty         INTEGER,
    product_weight_g           NUMERIC(10,2),
    product_length_cm          NUMERIC(10,2),
    product_height_cm          NUMERIC(10,2),
    product_width_cm           NUMERIC(10,2),
    product_volume_cm3         NUMERIC(14,2),
    weight_band                VARCHAR(16),
    updated_at                 TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- DIM_SELLER: SCD TYPE 1 ---------------------------------------------
CREATE TABLE IF NOT EXISTS nexus_dw.dim_seller (
    seller_key      INTEGER PRIMARY KEY,
    seller_id       VARCHAR(32) NOT NULL UNIQUE,
    zip_code_prefix CHAR(5),
    city            TEXT,
    state           CHAR(2),
    region          VARCHAR(12),
    location_key    INTEGER NOT NULL REFERENCES nexus_dw.dim_location (location_key),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- DIM_PAYMENT_TYPE ---------------------------------------------------
CREATE TABLE IF NOT EXISTS nexus_dw.dim_payment_type (
    payment_type_key   SMALLINT PRIMARY KEY,
    payment_type       VARCHAR(20) NOT NULL UNIQUE,
    payment_type_label TEXT NOT NULL,
    is_card            BOOLEAN NOT NULL
);

-- Brazilian state -> macro-region reference (IBGE)
CREATE TABLE IF NOT EXISTS nexus_dw.ref_state_region (
    state      CHAR(2) PRIMARY KEY,
    state_name TEXT NOT NULL,
    region     VARCHAR(12) NOT NULL
);
