-- =====================================================================
-- STORED PROCEDURES – build the star schema from nexus_staging.
-- All procedures are idempotent:
--   * dimensions: SCD1 upserts (product, seller, location, payment type),
--                 SCD2 rebuild for customer from full order history;
--   * facts:      delete + insert for the affected window (p_since) or full.
-- Usage:  CALL nexus_dw.sp_build_warehouse();            -- full
--         CALL nexus_dw.sp_build_warehouse('2018-08-01'); -- incremental facts
-- =====================================================================

CREATE OR REPLACE PROCEDURE nexus_dw.sp_log(p_process TEXT, p_status TEXT, p_rows BIGINT, p_msg TEXT)
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO nexus_dw.etl_audit_log (process_name, status, rows_affected, message)
    VALUES (p_process, p_status, p_rows, p_msg);
END $$;

-- ---------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE nexus_dw.sp_load_dim_date(p_start DATE DEFAULT '2016-01-01', p_end DATE DEFAULT '2019-12-31')
LANGUAGE plpgsql AS $$
DECLARE v_rows BIGINT;
BEGIN
    INSERT INTO nexus_dw.dim_date (date_key, full_date, year, quarter, quarter_label, month, month_name, month_short,
        year_month, month_start, iso_week, week_start, day_of_month, day_of_week, day_name, is_weekend)
    SELECT to_char(d, 'YYYYMMDD')::INT, d, EXTRACT(YEAR FROM d), EXTRACT(QUARTER FROM d),
           to_char(d, 'YYYY') || '-Q' || EXTRACT(QUARTER FROM d), EXTRACT(MONTH FROM d),
           trim(to_char(d, 'Month')), to_char(d, 'Mon'), to_char(d, 'YYYY-MM'), date_trunc('month', d)::DATE,
           EXTRACT(WEEK FROM d), date_trunc('week', d)::DATE, EXTRACT(DAY FROM d), EXTRACT(ISODOW FROM d),
           trim(to_char(d, 'Day')), EXTRACT(ISODOW FROM d) IN (6, 7)
    FROM generate_series(p_start, p_end, INTERVAL '1 day') AS g(d)
    ON CONFLICT (date_key) DO NOTHING;
    GET DIAGNOSTICS v_rows = ROW_COUNT;

    -- Fixed-date Brazilian national holidays
    UPDATE nexus_dw.dim_date SET is_holiday_br = TRUE, holiday_name = h.name
    FROM (VALUES (1,1,'Confraternização Universal'), (4,21,'Tiradentes'), (5,1,'Dia do Trabalho'),
                 (9,7,'Independência'), (10,12,'Nossa Senhora Aparecida'), (11,2,'Finados'),
                 (11,15,'Proclamação da República'), (12,25,'Natal')) AS h(m, d, name)
    WHERE month = h.m AND day_of_month = h.d;
    -- Black Friday = day after the 4th Thursday of November
    UPDATE nexus_dw.dim_date dd SET is_black_friday = TRUE
    WHERE month = 11 AND day_of_week = 5 AND day_of_month BETWEEN 23 AND 29;

    CALL nexus_dw.sp_log('sp_load_dim_date', 'SUCCESS', v_rows, p_start || '..' || p_end);
END $$;

-- ---------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE nexus_dw.sp_load_scd1_dimensions()
LANGUAGE plpgsql AS $$
DECLARE v_rows BIGINT;
BEGIN
    -- Reference: state -> region
    INSERT INTO nexus_dw.ref_state_region (state, state_name, region) VALUES
     ('AC','Acre','Norte'),('AP','Amapá','Norte'),('AM','Amazonas','Norte'),('PA','Pará','Norte'),
     ('RO','Rondônia','Norte'),('RR','Roraima','Norte'),('TO','Tocantins','Norte'),
     ('AL','Alagoas','Nordeste'),('BA','Bahia','Nordeste'),('CE','Ceará','Nordeste'),('MA','Maranhão','Nordeste'),
     ('PB','Paraíba','Nordeste'),('PE','Pernambuco','Nordeste'),('PI','Piauí','Nordeste'),
     ('RN','Rio Grande do Norte','Nordeste'),('SE','Sergipe','Nordeste'),
     ('DF','Distrito Federal','Centro-Oeste'),('GO','Goiás','Centro-Oeste'),('MT','Mato Grosso','Centro-Oeste'),
     ('MS','Mato Grosso do Sul','Centro-Oeste'),
     ('ES','Espírito Santo','Sudeste'),('MG','Minas Gerais','Sudeste'),('RJ','Rio de Janeiro','Sudeste'),
     ('SP','São Paulo','Sudeste'),
     ('PR','Paraná','Sul'),('RS','Rio Grande do Sul','Sul'),('SC','Santa Catarina','Sul')
    ON CONFLICT (state) DO NOTHING;

    -- DIM_LOCATION (SCD1) ---------------------------------------------
    INSERT INTO nexus_dw.dim_location VALUES (-1, '00000', 'unknown', NULL, 'Unknown', NULL, NULL, FALSE)
    ON CONFLICT DO NOTHING;
    WITH zips AS (
        SELECT customer_zip_code_prefix AS zip, customer_city AS city, customer_state AS state FROM nexus_staging.customers
        UNION ALL
        SELECT seller_zip_code_prefix, seller_city, seller_state FROM nexus_staging.sellers
    ), modal AS (   -- most frequent city/state per zip among customers/sellers
        SELECT DISTINCT ON (zip) zip, city, state
        FROM (SELECT zip, city, state, count(*) n FROM zips GROUP BY 1,2,3) t
        ORDER BY zip, n DESC, city
    ), all_zips AS (
        SELECT zip FROM modal UNION SELECT zip_code_prefix FROM nexus_staging.geolocation
    ), src AS (
        SELECT z.zip,
               COALESCE(g.city, m.city) AS city,
               COALESCE(g.state, m.state) AS state,
               g.latitude, g.longitude
        FROM all_zips z
        LEFT JOIN nexus_staging.geolocation g ON g.zip_code_prefix = z.zip
        LEFT JOIN modal m ON m.zip = z.zip
    )
    INSERT INTO nexus_dw.dim_location (location_key, zip_code_prefix, city, state, region, latitude, longitude, has_coordinates)
    SELECT GREATEST((SELECT max(location_key) FROM nexus_dw.dim_location), 0)
             + ROW_NUMBER() OVER (ORDER BY s.zip),
           s.zip, s.city, s.state, COALESCE(r.region, 'Unknown'), s.latitude, s.longitude, s.latitude IS NOT NULL
    FROM src s LEFT JOIN nexus_dw.ref_state_region r ON r.state = s.state
    WHERE NOT EXISTS (SELECT 1 FROM nexus_dw.dim_location l WHERE l.zip_code_prefix = s.zip);
    GET DIAGNOSTICS v_rows = ROW_COUNT;
    CALL nexus_dw.sp_log('dim_location', 'SUCCESS', v_rows, 'inserted new zip prefixes');

    -- DIM_PAYMENT_TYPE --------------------------------------------------
    INSERT INTO nexus_dw.dim_payment_type VALUES
        (-1, 'unknown', 'Unknown', FALSE), (1, 'credit_card', 'Credit Card', TRUE),
        (2, 'boleto', 'Boleto (Bank Slip)', FALSE), (3, 'voucher', 'Voucher', FALSE),
        (4, 'debit_card', 'Debit Card', TRUE), (5, 'not_defined', 'Not Defined', FALSE)
    ON CONFLICT (payment_type_key) DO UPDATE SET payment_type_label = EXCLUDED.payment_type_label;

    -- DIM_PRODUCT (SCD1 upsert) -----------------------------------------
    INSERT INTO nexus_dw.dim_product (product_key, product_id, category_name_pt, category_name_en, category_display_name)
    VALUES (-1, 'unknown', 'unknown', 'unknown', 'Unknown') ON CONFLICT DO NOTHING;
    INSERT INTO nexus_dw.dim_product (product_key, product_id, category_name_pt, category_name_en, category_display_name,
        product_name_length, product_description_length, product_photos_qty, product_weight_g, product_length_cm,
        product_height_cm, product_width_cm, product_volume_cm3, weight_band, updated_at)
    SELECT COALESCE(e.product_key,
                    (SELECT GREATEST(max(product_key), 0) FROM nexus_dw.dim_product)
                    + ROW_NUMBER() OVER (PARTITION BY e.product_key IS NULL ORDER BY p.product_id)),
           p.product_id, p.product_category_name, COALESCE(p.product_category_name_english, 'unknown'),
           COALESCE(t.category_display_name, initcap(replace(p.product_category_name_english, '_', ' ')), 'Unknown'),
           p.product_name_length, p.product_description_length, p.product_photos_qty, p.product_weight_g,
           p.product_length_cm, p.product_height_cm, p.product_width_cm, p.product_volume_cm3,
           CASE WHEN p.product_weight_g IS NULL THEN 'Unknown'
                WHEN p.product_weight_g < 500 THEN '< 0.5 kg'
                WHEN p.product_weight_g < 2000 THEN '0.5-2 kg'
                WHEN p.product_weight_g < 10000 THEN '2-10 kg' ELSE '>= 10 kg' END,
           now()
    FROM nexus_staging.products p
    LEFT JOIN nexus_staging.category_translation t ON t.product_category_name = p.product_category_name
    LEFT JOIN nexus_dw.dim_product e ON e.product_id = p.product_id
    ON CONFLICT (product_id) DO UPDATE SET
        category_name_pt = EXCLUDED.category_name_pt, category_name_en = EXCLUDED.category_name_en,
        category_display_name = EXCLUDED.category_display_name, product_weight_g = EXCLUDED.product_weight_g,
        product_volume_cm3 = EXCLUDED.product_volume_cm3, weight_band = EXCLUDED.weight_band, updated_at = now();
    GET DIAGNOSTICS v_rows = ROW_COUNT;
    CALL nexus_dw.sp_log('dim_product', 'SUCCESS', v_rows, 'SCD1 upsert');

    -- DIM_SELLER (SCD1 upsert) ------------------------------------------
    INSERT INTO nexus_dw.dim_seller (seller_key, seller_id, zip_code_prefix, city, state, region, location_key)
    VALUES (-1, 'unknown', NULL, 'unknown', NULL, 'Unknown', -1) ON CONFLICT DO NOTHING;
    INSERT INTO nexus_dw.dim_seller (seller_key, seller_id, zip_code_prefix, city, state, region, location_key, updated_at)
    SELECT COALESCE(e.seller_key,
                    (SELECT GREATEST(max(seller_key), 0) FROM nexus_dw.dim_seller)
                    + ROW_NUMBER() OVER (PARTITION BY e.seller_key IS NULL ORDER BY s.seller_id)),
           s.seller_id, s.seller_zip_code_prefix, s.seller_city, s.seller_state, COALESCE(r.region, 'Unknown'),
           COALESCE(l.location_key, -1), now()
    FROM nexus_staging.sellers s
    LEFT JOIN nexus_dw.ref_state_region r ON r.state = s.seller_state
    LEFT JOIN nexus_dw.dim_location l ON l.zip_code_prefix = s.seller_zip_code_prefix
    LEFT JOIN nexus_dw.dim_seller e ON e.seller_id = s.seller_id
    ON CONFLICT (seller_id) DO UPDATE SET zip_code_prefix = EXCLUDED.zip_code_prefix, city = EXCLUDED.city,
        state = EXCLUDED.state, region = EXCLUDED.region, location_key = EXCLUDED.location_key, updated_at = now();
    GET DIAGNOSTICS v_rows = ROW_COUNT;
    CALL nexus_dw.sp_log('dim_seller', 'SUCCESS', v_rows, 'SCD1 upsert');
END $$;

-- ---------------------------------------------------------------------
-- DIM_CUSTOMER full SCD2 rebuild from complete order history (used by full loads)
CREATE OR REPLACE PROCEDURE nexus_dw.sp_rebuild_dim_customer()
LANGUAGE plpgsql AS $$
DECLARE v_rows BIGINT;
BEGIN
    -- DIM_CUSTOMER (SCD2 rebuilt from full history) ------------------------
    -- Facts reference customer_key, so facts are reloaded after this step.
    TRUNCATE nexus_dw.fact_reviews, nexus_dw.fact_payments, nexus_dw.fact_order_items, nexus_dw.fact_orders,
             nexus_dw.map_customer_id, nexus_dw.dim_customer;
    INSERT INTO nexus_dw.dim_customer VALUES
        (-1, 'unknown', NULL, 'unknown', NULL, 'Unknown', -1, 1, '1900-01-01', '9999-12-31', TRUE, NULL);

    CREATE TEMP TABLE tmp_cust_hist ON COMMIT DROP AS
    WITH addr AS (
        SELECT c.customer_id, c.customer_unique_id, c.customer_zip_code_prefix AS zip, c.customer_city AS city,
               c.customer_state AS state,
               COALESCE(o.order_purchase_timestamp, TIMESTAMP '1900-01-01') AS ts
        FROM nexus_staging.customers c
        LEFT JOIN nexus_staging.orders o ON o.customer_id = c.customer_id
    ), flagged AS (
        SELECT a.*, CASE WHEN LAG(zip || '|' || coalesce(city,'') || '|' || state)
                              OVER (PARTITION BY customer_unique_id ORDER BY ts, customer_id)
                              IS DISTINCT FROM zip || '|' || coalesce(city,'') || '|' || state
                         THEN 1 ELSE 0 END AS is_change
        FROM addr a
    )
    SELECT f.*, SUM(is_change) OVER (PARTITION BY customer_unique_id ORDER BY ts, customer_id) AS version_number
    FROM flagged f;

    INSERT INTO nexus_dw.dim_customer (customer_key, customer_unique_id, zip_code_prefix, city, state, region,
        location_key, version_number, valid_from, valid_to, is_current, first_order_date)
    SELECT ROW_NUMBER() OVER (ORDER BY v.customer_unique_id, v.version_number),
           v.customer_unique_id, v.zip, v.city, v.state, COALESCE(r.region, 'Unknown'), COALESCE(l.location_key, -1),
           v.version_number, v.valid_from,
           COALESCE(LEAD(v.valid_from) OVER w - INTERVAL '1 microsecond', TIMESTAMP '9999-12-31'),
           LEAD(v.valid_from) OVER w IS NULL,
           MIN(v.valid_from) OVER (PARTITION BY v.customer_unique_id)::DATE
    FROM (SELECT customer_unique_id, version_number, min(zip) zip, min(city) city, min(state) state, min(ts) valid_from
          FROM tmp_cust_hist GROUP BY customer_unique_id, version_number) v
    LEFT JOIN nexus_dw.ref_state_region r ON r.state = v.state
    LEFT JOIN nexus_dw.dim_location l ON l.zip_code_prefix = v.zip
    WINDOW w AS (PARTITION BY v.customer_unique_id ORDER BY v.version_number);
    GET DIAGNOSTICS v_rows = ROW_COUNT;

    INSERT INTO nexus_dw.map_customer_id (customer_id, customer_key)
    SELECT h.customer_id, d.customer_key
    FROM tmp_cust_hist h
    JOIN nexus_dw.dim_customer d ON d.customer_unique_id = h.customer_unique_id AND d.version_number = h.version_number;
    CALL nexus_dw.sp_log('dim_customer', 'SUCCESS', v_rows, 'SCD2 rebuild');
END $$;

-- ---------------------------------------------------------------------
-- DIM_CUSTOMER incremental SCD2 merge (used by incremental loads).
-- For every customer_id not yet mapped (processed in purchase order):
--   same address as current version -> map to current key
--   new address / new person         -> close current version, open a new one
CREATE OR REPLACE PROCEDURE nexus_dw.sp_merge_dim_customer()
LANGUAGE plpgsql AS $$
DECLARE
    rec RECORD; v_key INTEGER; v_new BIGINT := 0; v_mapped BIGINT := 0;
    c_key INTEGER; c_zip CHAR(5); c_city TEXT; c_state CHAR(2); c_ver SMALLINT; c_first DATE; v_found BOOLEAN;
BEGIN
    FOR rec IN
        SELECT c.customer_id, c.customer_unique_id, c.customer_zip_code_prefix AS zip, c.customer_city AS city,
               c.customer_state AS state, COALESCE(o.order_purchase_timestamp, TIMESTAMP '1900-01-01') AS ts
        FROM nexus_staging.customers c
        LEFT JOIN nexus_staging.orders o ON o.customer_id = c.customer_id
        WHERE NOT EXISTS (SELECT 1 FROM nexus_dw.map_customer_id m WHERE m.customer_id = c.customer_id)
        ORDER BY ts, c.customer_id
    LOOP
        SELECT customer_key, zip_code_prefix, city, state, version_number, first_order_date
          INTO c_key, c_zip, c_city, c_state, c_ver, c_first
        FROM nexus_dw.dim_customer
        WHERE customer_unique_id = rec.customer_unique_id AND is_current;
        v_found := FOUND;
        IF v_found AND c_zip = rec.zip AND c_city IS NOT DISTINCT FROM rec.city AND c_state = rec.state THEN
            INSERT INTO nexus_dw.map_customer_id VALUES (rec.customer_id, c_key);
            v_mapped := v_mapped + 1;
        ELSE
            IF v_found THEN
                UPDATE nexus_dw.dim_customer SET valid_to = rec.ts - INTERVAL '1 microsecond', is_current = FALSE
                WHERE customer_key = c_key;
            END IF;
            SELECT GREATEST(max(customer_key), 0) + 1 INTO v_key FROM nexus_dw.dim_customer;
            INSERT INTO nexus_dw.dim_customer (customer_key, customer_unique_id, zip_code_prefix, city, state, region,
                location_key, version_number, valid_from, valid_to, is_current, first_order_date)
            SELECT v_key, rec.customer_unique_id, rec.zip, rec.city, rec.state, COALESCE(r.region, 'Unknown'),
                   COALESCE(l.location_key, -1), COALESCE(c_ver, 0) + 1, rec.ts, TIMESTAMP '9999-12-31',
                   TRUE, COALESCE(c_first, rec.ts::DATE)
            FROM (SELECT 1) one
            LEFT JOIN nexus_dw.ref_state_region r ON r.state = rec.state
            LEFT JOIN nexus_dw.dim_location l ON l.zip_code_prefix = rec.zip;
            INSERT INTO nexus_dw.map_customer_id VALUES (rec.customer_id, v_key);
            v_new := v_new + 1;
        END IF;
    END LOOP;
    CALL nexus_dw.sp_log('dim_customer', 'SUCCESS', v_new, 'SCD2 merge: ' || v_new || ' new versions, ' || v_mapped || ' mapped to current');
END $$;

-- ---------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE nexus_dw.sp_load_facts(p_since TIMESTAMP DEFAULT NULL)
LANGUAGE plpgsql AS $$
DECLARE v_rows BIGINT;
BEGIN
    IF p_since IS NULL THEN
        TRUNCATE nexus_dw.fact_reviews, nexus_dw.fact_payments, nexus_dw.fact_order_items, nexus_dw.fact_orders;
    ELSE   -- incremental: reload the window of orders purchased on/after p_since
        DELETE FROM nexus_dw.fact_reviews     WHERE order_id IN (SELECT order_id FROM nexus_dw.fact_orders WHERE purchase_timestamp >= p_since);
        DELETE FROM nexus_dw.fact_payments    WHERE order_id IN (SELECT order_id FROM nexus_dw.fact_orders WHERE purchase_timestamp >= p_since);
        DELETE FROM nexus_dw.fact_order_items WHERE order_id IN (SELECT order_id FROM nexus_dw.fact_orders WHERE purchase_timestamp >= p_since);
        DELETE FROM nexus_dw.fact_orders      WHERE purchase_timestamp >= p_since;
    END IF;

    -- FACT_ORDERS ------------------------------------------------------
    INSERT INTO nexus_dw.fact_orders (order_id, customer_key, customer_location_key, purchase_date_key, approved_date_key,
        delivered_date_key, estimated_date_key, main_payment_type_key, order_status, purchase_timestamp,
        is_revenue_order, is_canceled, is_delivered, is_on_time, is_late, items_count, distinct_sellers, items_price,
        freight_value, order_value, revenue, payment_value, payment_count, approval_hours, delivery_days,
        estimated_delivery_days, delivery_delay_days, review_score)
    WITH it AS (
        SELECT order_id, count(*) items_count, count(DISTINCT seller_id) distinct_sellers,
               sum(price) items_price, sum(freight_value) freight_value
        FROM nexus_staging.order_items GROUP BY order_id
    ), pay AS (
        SELECT order_id, sum(payment_value) payment_value, count(*) payment_count FROM nexus_staging.payments GROUP BY order_id
    ), main_pay AS (
        SELECT DISTINCT ON (order_id) order_id, payment_type FROM nexus_staging.payments
        ORDER BY order_id, payment_value DESC, payment_sequential
    ), rev AS (
        SELECT DISTINCT ON (order_id) order_id, review_score FROM nexus_staging.reviews
        ORDER BY order_id, review_answer_timestamp DESC NULLS LAST
    ), base AS (
        SELECT o.*,
               o.order_status NOT IN ('canceled', 'unavailable') AS is_rev,
               (o.order_status = 'delivered' AND o.order_delivered_customer_date IS NOT NULL) AS is_dlv,
               (o.order_delivered_customer_date::DATE - o.order_estimated_delivery_date::DATE) AS delay
        FROM nexus_staging.orders o
        WHERE p_since IS NULL OR o.order_purchase_timestamp >= p_since
    )
    SELECT b.order_id, COALESCE(mc.customer_key, -1), COALESCE(dc.location_key, -1),
           to_char(b.order_purchase_timestamp, 'YYYYMMDD')::INT,
           to_char(b.order_approved_at, 'YYYYMMDD')::INT,
           to_char(b.order_delivered_customer_date, 'YYYYMMDD')::INT,
           to_char(b.order_estimated_delivery_date, 'YYYYMMDD')::INT,
           COALESCE(pt.payment_type_key, -1), b.order_status, b.order_purchase_timestamp,
           b.is_rev, b.order_status = 'canceled', b.is_dlv,
           CASE WHEN b.is_dlv THEN b.delay <= 0 END, CASE WHEN b.is_dlv THEN b.delay > 0 END,
           COALESCE(it.items_count, 0), COALESCE(it.distinct_sellers, 0),
           COALESCE(it.items_price, 0), COALESCE(it.freight_value, 0),
           COALESCE(it.items_price, 0) + COALESCE(it.freight_value, 0),
           CASE WHEN b.is_rev THEN COALESCE(it.items_price, 0) + COALESCE(it.freight_value, 0) ELSE 0 END,
           COALESCE(pay.payment_value, 0), COALESCE(pay.payment_count, 0),
           round(EXTRACT(EPOCH FROM b.order_approved_at - b.order_purchase_timestamp) / 3600.0, 2),
           round(EXTRACT(EPOCH FROM b.order_delivered_customer_date - b.order_purchase_timestamp) / 86400.0, 2),
           round(EXTRACT(EPOCH FROM b.order_estimated_delivery_date - b.order_purchase_timestamp) / 86400.0, 2),
           b.delay, rev.review_score
    FROM base b
    LEFT JOIN nexus_dw.map_customer_id mc ON mc.customer_id = b.customer_id
    LEFT JOIN nexus_dw.dim_customer dc ON dc.customer_key = mc.customer_key
    LEFT JOIN it ON it.order_id = b.order_id
    LEFT JOIN pay ON pay.order_id = b.order_id
    LEFT JOIN main_pay mp ON mp.order_id = b.order_id
    LEFT JOIN nexus_dw.dim_payment_type pt ON pt.payment_type = mp.payment_type
    LEFT JOIN rev ON rev.order_id = b.order_id;
    GET DIAGNOSTICS v_rows = ROW_COUNT;
    CALL nexus_dw.sp_log('fact_orders', 'SUCCESS', v_rows, COALESCE('since ' || p_since, 'full'));

    -- FACT_ORDER_ITEMS -------------------------------------------------
    INSERT INTO nexus_dw.fact_order_items
    SELECT i.order_id, i.order_item_id, COALESCE(p.product_key, -1), COALESCE(s.seller_key, -1), f.customer_key,
           f.purchase_date_key, to_char(i.shipping_limit_date, 'YYYYMMDD')::INT,
           f.order_status, f.is_revenue_order, i.price, i.freight_value, i.price + i.freight_value
    FROM nexus_staging.order_items i
    JOIN nexus_dw.fact_orders f ON f.order_id = i.order_id
    LEFT JOIN nexus_dw.dim_product p ON p.product_id = i.product_id
    LEFT JOIN nexus_dw.dim_seller s ON s.seller_id = i.seller_id
    WHERE p_since IS NULL OR f.purchase_timestamp >= p_since;
    GET DIAGNOSTICS v_rows = ROW_COUNT;
    CALL nexus_dw.sp_log('fact_order_items', 'SUCCESS', v_rows, NULL);

    -- FACT_PAYMENTS ----------------------------------------------------
    INSERT INTO nexus_dw.fact_payments
    SELECT p.order_id, p.payment_sequential, COALESCE(pt.payment_type_key, -1), f.customer_key, f.purchase_date_key,
           p.payment_installments, p.payment_value, f.is_revenue_order
    FROM nexus_staging.payments p
    JOIN nexus_dw.fact_orders f ON f.order_id = p.order_id
    LEFT JOIN nexus_dw.dim_payment_type pt ON pt.payment_type = p.payment_type
    WHERE p_since IS NULL OR f.purchase_timestamp >= p_since;
    GET DIAGNOSTICS v_rows = ROW_COUNT;
    CALL nexus_dw.sp_log('fact_payments', 'SUCCESS', v_rows, NULL);

    -- FACT_REVIEWS -----------------------------------------------------
    INSERT INTO nexus_dw.fact_reviews
    SELECT r.review_id, r.order_id, f.customer_key, f.purchase_date_key,
           to_char(r.review_creation_date, 'YYYYMMDD')::INT, to_char(r.review_answer_timestamp, 'YYYYMMDD')::INT,
           r.review_score, r.review_comment_message IS NOT NULL, r.review_comment_title IS NOT NULL,
           round(EXTRACT(EPOCH FROM r.review_answer_timestamp - r.review_creation_date) / 3600.0, 2),
           ROW_NUMBER() OVER (PARTITION BY r.order_id ORDER BY r.review_answer_timestamp DESC NULLS LAST) = 1
    FROM nexus_staging.reviews r
    JOIN nexus_dw.fact_orders f ON f.order_id = r.order_id
    WHERE p_since IS NULL OR f.purchase_timestamp >= p_since;
    GET DIAGNOSTICS v_rows = ROW_COUNT;
    CALL nexus_dw.sp_log('fact_reviews', 'SUCCESS', v_rows, NULL);
END $$;

-- ---------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE nexus_dw.sp_refresh_materialized_views()
LANGUAGE plpgsql AS $$
BEGIN
    REFRESH MATERIALIZED VIEW nexus_dw.mv_daily_kpis;
    REFRESH MATERIALIZED VIEW nexus_dw.mv_monthly_category_sales;
    REFRESH MATERIALIZED VIEW nexus_dw.mv_customer_rfm;
    CALL nexus_dw.sp_log('materialized_views', 'SUCCESS', NULL, 'refreshed');
END $$;

-- ---------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE nexus_dw.sp_build_warehouse(p_since TIMESTAMP DEFAULT NULL)
LANGUAGE plpgsql AS $$
DECLARE v_min DATE; v_max DATE;
BEGIN
    CALL nexus_dw.sp_log('sp_build_warehouse', 'STARTED', NULL, COALESCE('since ' || p_since, 'full'));
    -- dim_date must cover every date referenced by any fact (incl. outliers such as
    -- shipping limits in 2020) plus one forecast year beyond the data.
    SELECT least(date_trunc('year', min(d))::DATE, DATE '2016-01-01'),
           greatest((date_trunc('year', max(d)) + INTERVAL '1 year - 1 day')::DATE, DATE '2019-12-31')
      INTO v_min, v_max
    FROM (SELECT order_purchase_timestamp AS d FROM nexus_staging.orders
          UNION ALL SELECT order_estimated_delivery_date FROM nexus_staging.orders
          UNION ALL SELECT order_delivered_customer_date FROM nexus_staging.orders
          UNION ALL SELECT shipping_limit_date FROM nexus_staging.order_items
          UNION ALL SELECT review_answer_timestamp FROM nexus_staging.reviews) x;
    CALL nexus_dw.sp_load_dim_date(v_min, v_max);
    CALL nexus_dw.sp_load_scd1_dimensions();
    IF p_since IS NULL THEN
        CALL nexus_dw.sp_rebuild_dim_customer();   -- SCD2 rebuild truncates facts, so a full fact load follows
        CALL nexus_dw.sp_load_facts(NULL);
    ELSE
        CALL nexus_dw.sp_merge_dim_customer();     -- SCD2 merge keeps existing keys stable
        CALL nexus_dw.sp_load_facts(p_since);
    END IF;
    CALL nexus_dw.sp_refresh_materialized_views();
    CALL nexus_dw.sp_log('sp_build_warehouse', 'SUCCESS', NULL, NULL);
END $$;
