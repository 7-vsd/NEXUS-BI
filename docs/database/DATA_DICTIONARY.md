# NEXUS BI – Data Dictionary

_Generated 2026-11-12 15:16 UTC by `scripts/generate_docs.py`._

## 1. Source files (raw layer)

Null % and distinct counts are measured on the supplied files. Types are the target types after ingestion.

### category_translation

| column | target_type | is_primary_key | foreign_key_to | null_pct | distinct_values | example | description |
|---|---|---|---|---|---|---|---|
| product_category_name | string | True |  | 0.0 | 71 | beleza_saude | Product category (Portuguese). |
| product_category_name_english | string | False |  | 0.0 | 71 | health_beauty | Category name translated to English. |

### customers

| column | target_type | is_primary_key | foreign_key_to | null_pct | distinct_values | example | description |
|---|---|---|---|---|---|---|---|
| customer_id | string | True |  | 0.0 | 99441 | 06b8999e2fba1a1fbc88172c00ba8bc7 | Order-scoped customer key (one per order). FK from orders. |
| customer_unique_id | string | False |  | 0.0 | 96096 | 861eff4711a542e4b93843c6dd7febb0 | Stable identifier of the real customer across orders. |
| customer_zip_code_prefix | string | False |  | 0.0 | 14994 | 14409 | First 5 digits of the customer zip code (string, zero-padded). |
| customer_city | string | False |  | 0.0 | 4119 | franca | Customer city name (lower-case, Portuguese). |
| customer_state | string | False |  | 0.0 | 27 | SP | Customer state (2-letter Brazilian UF code). |

### geolocation

| column | target_type | is_primary_key | foreign_key_to | null_pct | distinct_values | example | description |
|---|---|---|---|---|---|---|---|
| geolocation_zip_code_prefix | string | False |  | 0.0 | 19015 | 01037 | 5-digit zip-code prefix. |
| geolocation_lat | float | False |  | 0.0 | 717372 | -23.54562128115268 | Latitude (decimal degrees). |
| geolocation_lng | float | False |  | 0.0 | 717615 | -46.63929204800168 | Longitude (decimal degrees). |
| geolocation_city | string | False |  | 0.0 | 8010 | sao paulo | City name. |
| geolocation_state | string | False |  | 0.0 | 27 | SP | State (UF). |

### order_items

| column | target_type | is_primary_key | foreign_key_to | null_pct | distinct_values | example | description |
|---|---|---|---|---|---|---|---|
| order_id | string | True | orders.order_id | 0.0 | 98666 | 00010242fe8c5a6d1ba2dd792cb16214 | Unique order identifier. |
| order_item_id | int | True |  | 0.0 | 21 | 1 | Sequential item number within an order (1..n). |
| product_id | string | False | products.product_id | 0.0 | 32951 | 4244733e06e7ecb4970a6e2683c13e61 | Unique product identifier. |
| seller_id | string | False | sellers.seller_id | 0.0 | 3095 | 48436dade18ac8b2bce089ec2a041202 | Unique seller identifier. |
| shipping_limit_date | datetime | False |  | 0.0 | 93318 | 2017-09-19 09:45:35 | Seller's shipping deadline for handing the item to the carrier. |
| price | float | False |  | 0.0 | 5968 | 58.9 | Item price in BRL. |
| freight_value | float | False |  | 0.0 | 6999 | 13.29 | Freight charged for the item in BRL (split per item when the order has several). |

### orders

| column | target_type | is_primary_key | foreign_key_to | null_pct | distinct_values | example | description |
|---|---|---|---|---|---|---|---|
| order_id | string | True |  | 0.0 | 99441 | e481f51cbdc54678b7cc49136f2d6af7 | Unique order identifier. |
| customer_id | string | False | customers.customer_id | 0.0 | 99441 | 9ef432eb6251297304e76186b10a928d | Order-scoped customer key (one per order). FK from orders. |
| order_status | string | False |  | 0.0 | 8 | delivered | Lifecycle status: delivered, shipped, canceled, unavailable, invoiced, processing, created, approved. |
| order_purchase_timestamp | datetime | False |  | 0.0 | 98875 | 2017-10-02 10:56:33 | Timestamp the order was placed. |
| order_approved_at | datetime | False |  | 0.161 | 90733 | 2017-10-02 11:07:15 | Timestamp payment was approved. |
| order_delivered_carrier_date | datetime | False |  | 1.793 | 81018 | 2017-10-04 19:55:00 | Timestamp the order was handed to the logistics partner. |
| order_delivered_customer_date | datetime | False |  | 2.982 | 95664 | 2017-10-10 21:25:13 | Actual delivery timestamp to the customer. |
| order_estimated_delivery_date | datetime | False |  | 0.0 | 459 | 2017-10-18 00:00:00 | Estimated delivery date shown to the customer at purchase. |

### payments

| column | target_type | is_primary_key | foreign_key_to | null_pct | distinct_values | example | description |
|---|---|---|---|---|---|---|---|
| order_id | string | True | orders.order_id | 0.0 | 99440 | b81ef226f3fe1789b1e8b2acac839d17 | Unique order identifier. |
| payment_sequential | int | True |  | 0.0 | 29 | 1 | Sequence number when an order is paid with several payment methods. |
| payment_type | string | False |  | 0.0 | 5 | credit_card | credit_card, boleto, voucher, debit_card, not_defined. |
| payment_installments | int | False |  | 0.0 | 24 | 8 | Number of installments chosen by the customer. |
| payment_value | float | False |  | 0.0 | 29077 | 99.33 | Transaction value in BRL. |

### products

| column | target_type | is_primary_key | foreign_key_to | null_pct | distinct_values | example | description |
|---|---|---|---|---|---|---|---|
| product_id | string | True |  | 0.0 | 32951 | 1e9e8ef04dbcff4541ed26657ea517e5 | Unique product identifier. |
| product_category_name | string | False |  | 1.851 | 73 | perfumaria | Product category (Portuguese). |
| product_name_lenght | float | False |  | 1.851 | 66 | 40.0 | Characters in the product name (source spelling 'lenght'). |
| product_description_lenght | float | False |  | 1.851 | 2960 | 287.0 | Characters in the product description (source spelling 'lenght'). |
| product_photos_qty | float | False |  | 1.851 | 19 | 1.0 | Number of published product photos. |
| product_weight_g | float | False |  | 0.006 | 2204 | 225.0 | Product weight in grams. |
| product_length_cm | float | False |  | 0.006 | 99 | 16.0 | Product length in cm. |
| product_height_cm | float | False |  | 0.006 | 102 | 10.0 | Product height in cm. |
| product_width_cm | float | False |  | 0.006 | 95 | 14.0 | Product width in cm. |

### reviews

| column | target_type | is_primary_key | foreign_key_to | null_pct | distinct_values | example | description |
|---|---|---|---|---|---|---|---|
| review_id | string | True |  | 0.0 | 98410 | 7bc2406110b926393aa56f80a40eba40 | Survey identifier (NOT unique alone: the same review_id can cover several orders). |
| order_id | string | True | orders.order_id | 0.0 | 98673 | 73fc7af87114b39712e6da79b0a377eb | Unique order identifier. |
| review_score | int | False |  | 0.0 | 5 | 4 | Satisfaction score 1-5. |
| review_comment_title | string | False |  | 88.342 | 4179 | recomendo | Optional review title (Portuguese). |
| review_comment_message | string | False |  | 58.703 | 35617 | Recebi bem antes do prazo estipulado. | Optional review comment (Portuguese). |
| review_creation_date | datetime | False |  | 0.0 | 636 | 2018-01-18 00:00:00 | Date the satisfaction survey was sent. |
| review_answer_timestamp | datetime | False |  | 0.0 | 98248 | 2018-01-18 21:46:59 | Timestamp the survey was answered. |

### sellers

| column | target_type | is_primary_key | foreign_key_to | null_pct | distinct_values | example | description |
|---|---|---|---|---|---|---|---|
| seller_id | string | True |  | 0.0 | 3095 | 3442f8959a84dea7ee197c632cb2df15 | Unique seller identifier. |
| seller_zip_code_prefix | string | False |  | 0.0 | 2246 | 13023 | First 5 digits of the seller zip code. |
| seller_city | string | False |  | 0.0 | 611 | campinas | Seller city name. |
| seller_state | string | False |  | 0.0 | 23 | SP | Seller state (UF). |

### Documented source corrections

| Item | Treatment |
|---|---|
| `product_name_lenght`, `product_description_lenght` | Misspelt in source; renamed to `*_length` in staging. |
| `pc_gamer`, `portateis_cozinha_e_preparadores_de_alimentos` | Missing from the translation file; translated manually to `pc_gamer`, `portable_kitchen_food_preparers`. |
| Missing product category (610 products) | Set to `unknown`. |
| `product_weight_g = 0` (4 products) | Treated as unknown (NULL). |
| `payment_installments = 0` (2 rows) | Set to 1. |
| Carrier date before purchase (166 orders) | Set to NULL (impossible sequence). |
| Geolocation | Exact duplicates removed, points outside Brazil removed, aggregated to one row per zip prefix (median lat/lng). |

## 2. Warehouse & ML tables (PostgreSQL information_schema)

### nexus_dw.dim_customer

| column_name | data_type | is_nullable |
|---|---|---|
| customer_key | integer | NO |
| customer_unique_id | character varying | NO |
| zip_code_prefix | character | YES |
| city | text | YES |
| state | character | YES |
| region | character varying | YES |
| location_key | integer | NO |
| version_number | smallint | NO |
| valid_from | timestamp without time zone | NO |
| valid_to | timestamp without time zone | NO |
| is_current | boolean | NO |
| first_order_date | date | YES |

### nexus_dw.dim_date

| column_name | data_type | is_nullable |
|---|---|---|
| date_key | integer | NO |
| full_date | date | NO |
| year | smallint | NO |
| quarter | smallint | NO |
| quarter_label | character | NO |
| month | smallint | NO |
| month_name | character varying | NO |
| month_short | character | NO |
| year_month | character | NO |
| month_start | date | NO |
| iso_week | smallint | NO |
| week_start | date | NO |
| day_of_month | smallint | NO |
| day_of_week | smallint | NO |
| day_name | character varying | NO |
| is_weekend | boolean | NO |
| is_holiday_br | boolean | NO |
| holiday_name | text | YES |
| is_black_friday | boolean | NO |

### nexus_dw.dim_location

| column_name | data_type | is_nullable |
|---|---|---|
| location_key | integer | NO |
| zip_code_prefix | character | NO |
| city | text | YES |
| state | character | YES |
| region | character varying | YES |
| latitude | double precision | YES |
| longitude | double precision | YES |
| has_coordinates | boolean | NO |

### nexus_dw.dim_payment_type

| column_name | data_type | is_nullable |
|---|---|---|
| payment_type_key | smallint | NO |
| payment_type | character varying | NO |
| payment_type_label | text | NO |
| is_card | boolean | NO |

### nexus_dw.dim_product

| column_name | data_type | is_nullable |
|---|---|---|
| product_key | integer | NO |
| product_id | character varying | NO |
| category_name_pt | text | NO |
| category_name_en | text | NO |
| category_display_name | text | NO |
| product_name_length | integer | YES |
| product_description_length | integer | YES |
| product_photos_qty | integer | YES |
| product_weight_g | numeric | YES |
| product_length_cm | numeric | YES |
| product_height_cm | numeric | YES |
| product_width_cm | numeric | YES |
| product_volume_cm3 | numeric | YES |
| weight_band | character varying | YES |
| updated_at | timestamp with time zone | NO |

### nexus_dw.dim_seller

| column_name | data_type | is_nullable |
|---|---|---|
| seller_key | integer | NO |
| seller_id | character varying | NO |
| zip_code_prefix | character | YES |
| city | text | YES |
| state | character | YES |
| region | character varying | YES |
| location_key | integer | NO |
| updated_at | timestamp with time zone | NO |

### nexus_dw.fact_order_items

| column_name | data_type | is_nullable |
|---|---|---|
| order_id | character varying | NO |
| order_item_id | smallint | NO |
| product_key | integer | NO |
| seller_key | integer | NO |
| customer_key | integer | NO |
| purchase_date_key | integer | NO |
| shipping_limit_date_key | integer | YES |
| order_status | character varying | NO |
| is_revenue_order | boolean | NO |
| price | numeric | NO |
| freight_value | numeric | NO |
| line_total | numeric | NO |

### nexus_dw.fact_orders

| column_name | data_type | is_nullable |
|---|---|---|
| order_id | character varying | NO |
| customer_key | integer | NO |
| customer_location_key | integer | NO |
| purchase_date_key | integer | NO |
| approved_date_key | integer | YES |
| delivered_date_key | integer | YES |
| estimated_date_key | integer | YES |
| main_payment_type_key | smallint | NO |
| order_status | character varying | NO |
| purchase_timestamp | timestamp without time zone | NO |
| is_revenue_order | boolean | NO |
| is_canceled | boolean | NO |
| is_delivered | boolean | NO |
| is_on_time | boolean | YES |
| is_late | boolean | YES |
| items_count | smallint | NO |
| distinct_sellers | smallint | NO |
| items_price | numeric | NO |
| freight_value | numeric | NO |
| order_value | numeric | NO |
| revenue | numeric | NO |
| payment_value | numeric | NO |
| payment_count | smallint | NO |
| approval_hours | numeric | YES |
| delivery_days | numeric | YES |
| estimated_delivery_days | numeric | YES |
| delivery_delay_days | integer | YES |
| review_score | smallint | YES |
| loaded_at | timestamp with time zone | NO |

### nexus_dw.fact_payments

| column_name | data_type | is_nullable |
|---|---|---|
| order_id | character varying | NO |
| payment_sequential | smallint | NO |
| payment_type_key | smallint | NO |
| customer_key | integer | NO |
| purchase_date_key | integer | NO |
| payment_installments | smallint | NO |
| payment_value | numeric | NO |
| is_revenue_order | boolean | NO |

### nexus_dw.fact_reviews

| column_name | data_type | is_nullable |
|---|---|---|
| review_id | character varying | NO |
| order_id | character varying | NO |
| customer_key | integer | NO |
| purchase_date_key | integer | NO |
| review_date_key | integer | YES |
| answer_date_key | integer | YES |
| review_score | smallint | NO |
| has_comment | boolean | NO |
| has_title | boolean | NO |
| response_hours | numeric | YES |
| is_latest_for_order | boolean | NO |

### nexus_dw.map_customer_id

| column_name | data_type | is_nullable |
|---|---|---|
| customer_id | character varying | NO |
| customer_key | integer | NO |

### nexus_dw.ref_state_region

| column_name | data_type | is_nullable |
|---|---|---|
| state | character | NO |
| state_name | text | NO |
| region | character varying | NO |

### nexus_dw.security_user_region

| column_name | data_type | is_nullable |
|---|---|---|
| db_user | text | NO |
| region | character varying | NO |

### nexus_dw.syn_inventory_weekly

| column_name | data_type | is_nullable |
|---|---|---|
| category | text | NO |
| week_start | date | NO |
| opening_stock | integer | YES |
| received_units | integer | YES |
| demand_units | integer | YES |
| fulfilled_units | integer | YES |
| lost_sales_units | integer | YES |
| closing_stock | integer | YES |
| reorder_point | integer | YES |
| is_stockout | boolean | YES |
| is_synthetic | boolean | NO |

### nexus_dw.syn_product_cost

| column_name | data_type | is_nullable |
|---|---|---|
| product_id | character varying | NO |
| category_name_en | text | YES |
| median_price | numeric | YES |
| cost_ratio | numeric | YES |
| unit_cost_brl | numeric | YES |
| is_synthetic | boolean | NO |

### nexus_dw.vw_customer_360

| column_name | data_type | is_nullable |
|---|---|---|
| customer_unique_id | character varying | YES |
| current_state | character | YES |
| orders | bigint | YES |
| lifetime_revenue | numeric | YES |
| first_purchase | timestamp without time zone | YES |
| last_purchase | timestamp without time zone | YES |
| avg_review | numeric | YES |
| address_versions | bigint | YES |

### nexus_dw.vw_order_items

| column_name | data_type | is_nullable |
|---|---|---|
| order_id | character varying | YES |
| order_item_id | smallint | YES |
| purchase_date | date | YES |
| year_month | character | YES |
| month_start | date | YES |
| product_id | character varying | YES |
| category_name_en | text | YES |
| category_display_name | text | YES |
| seller_id | character varying | YES |
| seller_state | character | YES |
| seller_region | character varying | YES |
| customer_unique_id | character varying | YES |
| customer_state | character | YES |
| is_revenue_order | boolean | YES |
| price | numeric | YES |
| freight_value | numeric | YES |
| line_total | numeric | YES |

### nexus_dw.vw_orders

| column_name | data_type | is_nullable |
|---|---|---|
| order_id | character varying | YES |
| order_status | character varying | YES |
| purchase_timestamp | timestamp without time zone | YES |
| purchase_date | date | YES |
| year | smallint | YES |
| quarter_label | character | YES |
| year_month | character | YES |
| month_start | date | YES |
| customer_unique_id | character varying | YES |
| customer_state | character | YES |
| customer_region | character varying | YES |
| customer_city | text | YES |
| main_payment_type | character varying | YES |
| is_revenue_order | boolean | YES |
| is_canceled | boolean | YES |
| is_delivered | boolean | YES |
| is_on_time | boolean | YES |
| is_late | boolean | YES |
| items_count | smallint | YES |
| items_price | numeric | YES |
| freight_value | numeric | YES |
| order_value | numeric | YES |
| revenue | numeric | YES |
| payment_value | numeric | YES |
| delivery_days | numeric | YES |
| estimated_delivery_days | numeric | YES |
| delivery_delay_days | integer | YES |
| review_score | smallint | YES |

### nexus_dw.vw_seller_scorecard

| column_name | data_type | is_nullable |
|---|---|---|
| seller_id | character varying | YES |
| city | text | YES |
| state | character | YES |
| region | character varying | YES |
| items_sold | bigint | YES |
| orders | bigint | YES |
| gmv | numeric | YES |
| freight | numeric | YES |
| avg_review | numeric | YES |
| avg_delivery_days | numeric | YES |
| late_rate | numeric | YES |
| cancel_rate | numeric | YES |

### nexus_dw.vw_syn_category_margin

| column_name | data_type | is_nullable |
|---|---|---|
| category_name_en | text | YES |
| revenue | numeric | YES |
| simulated_cogs | numeric | YES |
| simulated_gross_margin | numeric | YES |
| simulated_margin_pct | numeric | YES |
| is_synthetic | boolean | YES |

### nexus_ml.anomalies

| column_name | data_type | is_nullable |
|---|---|---|
| metric_date | date | NO |
| revenue | numeric | YES |
| orders | integer | YES |
| aov | numeric | YES |
| late_rate | numeric | YES |
| avg_review | numeric | YES |
| iforest_score | numeric | YES |
| iforest_flag | boolean | YES |
| rolling_z | numeric | YES |
| rolling_flag | boolean | YES |
| global_z | numeric | YES |
| zscore_flag | boolean | YES |
| votes | smallint | YES |
| is_anomaly | boolean | YES |
| severity | text | YES |
| direction | text | YES |

### nexus_ml.churn_scores

| column_name | data_type | is_nullable |
|---|---|---|
| customer_unique_id | character varying | NO |
| cutoff_date | date | NO |
| churn_probability | numeric | YES |
| risk_band | text | YES |
| model_name | text | YES |
| actual_churn | boolean | YES |

### nexus_ml.customer_segments

| column_name | data_type | is_nullable |
|---|---|---|
| customer_unique_id | character varying | NO |
| recency_days | integer | YES |
| frequency | integer | YES |
| monetary | numeric | YES |
| r_score | smallint | YES |
| f_score | smallint | YES |
| m_score | smallint | YES |
| rfm_segment | text | YES |
| cluster | smallint | YES |
| cluster_name | text | YES |
| recommended_strategy | text | YES |
| scored_at | timestamp with time zone | YES |

### nexus_ml.demand_forecast

| column_name | data_type | is_nullable |
|---|---|---|
| category | text | NO |
| week_start | date | NO |
| model_name | text | NO |
| kind | text | NO |
| actual | numeric | YES |
| predicted | numeric | YES |
| lower_95 | numeric | YES |
| upper_95 | numeric | YES |

### nexus_ml.revenue_forecast

| column_name | data_type | is_nullable |
|---|---|---|
| forecast_date | date | NO |
| model_name | text | NO |
| kind | text | NO |
| actual | numeric | YES |
| predicted | numeric | YES |
| lower_95 | numeric | YES |
| upper_95 | numeric | YES |
