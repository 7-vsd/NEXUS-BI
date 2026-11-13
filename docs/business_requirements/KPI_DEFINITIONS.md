# KPI Definitions (single source of truth)

These definitions are implemented identically in Python (`src/transformation/marts.py`), SQL (`sql/procedures`,
`src/analytics/reconciliation.py`), DAX (`powerbi/dax/measures.py`) and the API. Equality is enforced by
`reports/sql_results/_reconciliation.csv` and `powerbi/validate_pbip.py`.

| KPI | Definition | Grain / source | Notes |
|---|---|---|---|
| **Revenue-recognised order** | `order_status NOT IN ('canceled','unavailable')` | order | Includes delivered, shipped, invoiced, processing, created, approved. |
| **Total Revenue** | Σ (item price + item freight) over revenue-recognised orders | `fact_orders.revenue` | BRL. Item-based (not payment-based) so it can be split by product/seller. |
| Product Revenue | Σ item price, revenue orders | `fact_orders.items_price` | |
| Freight Revenue | Σ item freight, revenue orders | `fact_orders.freight_value` | |
| Item Revenue | Σ `fact_order_items.price`, revenue orders | order line | Use for category/seller analysis (no fan-out). |
| Total Payment Value | Σ payment transactions (all statuses) | `fact_payments` | Differs from revenue: includes canceled orders' payments and installment interest. |
| **Total Orders** | Count of revenue-recognised orders | order | 98,207 |
| All Orders | Count of all orders | order | 99,441 |
| **Unique Customers** | Distinct `customer_unique_id` with ≥ 1 revenue order | person | `customer_id` is order-scoped in Olist – never count it as a customer. |
| **Average Order Value** | Total Revenue / Total Orders | | |
| Repeat Customer Rate | Customers with > 1 revenue order *that has items* / customers | person | |
| Estimated CLV | AOV × orders per customer (historical) | | Not a predictive CLV. |
| Delivered order | `status = 'delivered'` AND delivered date present | order | |
| **On-Time Delivery %** | delivered orders with `delivered_date ≤ estimated_date` (date granularity) / delivered orders | order | Delivery on the estimated day counts as on time. |
| Late Delivery % | 1 − On-Time % (delivered orders) | | |
| Delivery Days | (delivered timestamp − purchase timestamp) in days | order | |
| Cancellation Rate | orders with status `canceled` / all orders | | `unavailable` reported separately. |
| Avg Review Score | mean of the **latest** review per order | order | 551 orders have > 1 review; only the latest counts. |
| Revenue YoY % | (Revenue − Revenue same period last year) / Revenue PY | | |
| Revenue growth vs prior period (API/app) | vs the immediately preceding period of equal length | | Not computed when that period starts before 2017-01-01 (2016 = sparse test data). |

## Reliable data window
Order capture collapses after **2018-08-22** (186 → 11 orders/day, then only cancellations). Forecasting, anomaly
detection and trend statements use **2017-01-05 → 2018-08-21** (`ml/common.reliable_window`). Headline totals use all data.
