# Database Schema – NEXUS BI (PostgreSQL 16)

Schemas: `nexus_raw` (TEXT landing), `nexus_staging` (typed, PK/CHECK constraints), `nexus_dw` (star schema),
`nexus_ml` (model outputs). DDL: `sql/`. Initialise: `python -m src.database.init_db` (idempotent; `--reset` drops).

## Star schema

```mermaid
erDiagram
    DIM_DATE ||--o{ FACT_ORDERS : "purchase_date_key (active), delivered_date_key (inactive in PBI)"
    DIM_CUSTOMER ||--o{ FACT_ORDERS : customer_key
    DIM_LOCATION ||--o{ FACT_ORDERS : customer_location_key
    DIM_PAYMENT_TYPE ||--o{ FACT_ORDERS : main_payment_type_key
    FACT_ORDERS ||--|{ FACT_ORDER_ITEMS : order_id
    FACT_ORDERS ||--|{ FACT_PAYMENTS : order_id
    FACT_ORDERS ||--o{ FACT_REVIEWS : order_id
    DIM_PRODUCT ||--o{ FACT_ORDER_ITEMS : product_key
    DIM_SELLER ||--o{ FACT_ORDER_ITEMS : seller_key
    DIM_DATE ||--o{ FACT_ORDER_ITEMS : purchase_date_key
    DIM_PAYMENT_TYPE ||--o{ FACT_PAYMENTS : payment_type_key
    DIM_DATE ||--o{ FACT_REVIEWS : purchase_date_key
    DIM_LOCATION ||--o{ DIM_CUSTOMER : location_key
    DIM_LOCATION ||--o{ DIM_SELLER : location_key

    FACT_ORDERS {
        varchar order_id PK
        int customer_key FK
        int purchase_date_key FK
        numeric revenue
        numeric items_price
        numeric freight_value
        bool is_on_time
        numeric delivery_days
        smallint review_score
    }
    FACT_ORDER_ITEMS {
        varchar order_id PK
        smallint order_item_id PK
        int product_key FK
        int seller_key FK
        numeric price
        numeric freight_value
    }
    FACT_PAYMENTS {
        varchar order_id PK
        smallint payment_sequential PK
        smallint payment_type_key FK
        numeric payment_value
    }
    FACT_REVIEWS {
        varchar review_id PK
        varchar order_id PK
        smallint review_score
        bool is_latest_for_order
    }
    DIM_CUSTOMER {
        int customer_key PK
        varchar customer_unique_id
        smallint version_number
        timestamp valid_from
        timestamp valid_to
        bool is_current
    }
```

## Fact grains (avoiding fan-out)

| Fact | Grain | Measures | Rule |
|---|---|---|---|
| `fact_orders` | 1 row per `order_id` | revenue, items_price, freight, payment_value, delivery metrics, latest review | All order-level KPIs come from here. |
| `fact_order_items` | 1 row per (`order_id`, `order_item_id`) | price, freight, line_total | Category/seller revenue only from here. |
| `fact_payments` | 1 row per (`order_id`, `payment_sequential`) | payment_value, installments | Never join to items directly (fan-out); aggregate first. |
| `fact_reviews` | 1 row per (`review_id`, `order_id`) | review_score, response time | `review_id` alone is not unique in the source. |

Row counts after load (= source rows; verified by reconciliation): fact_orders 99,441 · fact_order_items 112,650 ·
fact_payments 103,886 · fact_reviews 99,224 · dim_customer 96,356 (incl. Unknown) · dim_product 32,952 ·
dim_seller 3,096 · dim_location 19,175 · dim_date 1,827 (2016-01-01 → 2020-12-31, derived from data range).

## Slowly changing dimensions
* **DIM_CUSTOMER – Type 2** on (zip, city, state) per `customer_unique_id`; `valid_from/valid_to/is_current/version_number`.
  `map_customer_id` bridges the order-scoped source `customer_id` to the version valid at order time.
  Full load: `sp_rebuild_dim_customer()`; incremental: `sp_merge_dim_customer()` (closes the current version and opens a new one when the address changes).
* **DIM_PRODUCT, DIM_SELLER, DIM_LOCATION – Type 1** upserts (`ON CONFLICT DO UPDATE`), keys stable across runs.

## Procedures
`sp_build_warehouse(p_since)` → `sp_load_dim_date` (range derived from data) → `sp_load_scd1_dimensions` →
(`sp_rebuild_dim_customer` + `sp_load_facts(NULL)`) or (`sp_merge_dim_customer` + `sp_load_facts(p_since)`) →
`sp_refresh_materialized_views`. Every step logs into `nexus_dw.etl_audit_log`; `etl_watermark` stores the last loaded purchase timestamp.

## Views
`vw_orders`, `vw_order_items`, `vw_seller_scorecard` (aggregates each fact at its own grain before joining),
`vw_customer_360`, `vw_syn_category_margin` (SIMULATED). Materialized: `mv_daily_kpis`, `mv_monthly_category_sales`, `mv_customer_rfm`.

## Indexes & optimisation
FK indexes on all fact keys, partial covering index for revenue orders, BRIN on `purchase_timestamp`, `ANALYZE` after load
(`sql/optimization/01_indexes.sql`). Query rewrite case study: SQL_QUERY_DOCUMENTATION.md (Q27: 266 s → 0.18 s).

## Security
`nexus_bi_reader` (read-only) and `nexus_regional_analyst` roles (NOLOGIN; grant login out-of-band), RLS policy on
`dim_customer` driven by `security_user_region` (`sql/warehouse/02_security_rls.sql`). No passwords in SQL files.
