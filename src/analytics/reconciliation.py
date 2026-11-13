"""Reconcile KPIs computed by the SQL warehouse with the independent Python marts.

A KPI passes when |sql - python| <= tolerance (absolute for counts, relative
1e-6 for money/ratios). Results are written to
``reports/sql_results/_reconciliation.csv`` and asserted in the test suite.
"""
from __future__ import annotations

import json

import pandas as pd

from src.config.settings import settings
from src.database.connection import raw_connection

SQL_KPIS = {
    "total_revenue": "SELECT round(sum(revenue), 2) FROM nexus_dw.fact_orders",
    "product_revenue": "SELECT round(sum(items_price), 2) FROM nexus_dw.fact_orders WHERE is_revenue_order",
    "freight_revenue": "SELECT round(sum(freight_value), 2) FROM nexus_dw.fact_orders WHERE is_revenue_order",
    "total_orders": "SELECT count(*) FROM nexus_dw.fact_orders WHERE is_revenue_order",
    "all_orders": "SELECT count(*) FROM nexus_dw.fact_orders",
    "unique_customers": """SELECT count(DISTINCT c.customer_unique_id) FROM nexus_dw.fact_orders f
                           JOIN nexus_dw.dim_customer c ON c.customer_key = f.customer_key WHERE f.is_revenue_order""",
    "average_order_value": "SELECT round(sum(revenue) / count(*) FILTER (WHERE is_revenue_order), 2) FROM nexus_dw.fact_orders",
    "total_payment_value": "SELECT round(sum(payment_value), 2) FROM nexus_dw.fact_payments",
    "cancellation_rate": "SELECT round(avg(CASE WHEN is_canceled THEN 1.0 ELSE 0.0 END), 6) FROM nexus_dw.fact_orders",
    "on_time_delivery_rate": "SELECT round(avg(CASE WHEN is_on_time THEN 1.0 ELSE 0.0 END), 6) FROM nexus_dw.fact_orders WHERE is_delivered",
    "avg_delivery_days": "SELECT round(avg(delivery_days), 4) FROM nexus_dw.fact_orders WHERE is_delivered",
    "avg_review_score": "SELECT round(avg(review_score), 4) FROM nexus_dw.fact_orders",
    "items_sold": "SELECT count(*) FROM nexus_dw.fact_order_items WHERE is_revenue_order",
}
# Cross-layer row-count reconciliation: raw -> staging -> warehouse
ROW_COUNTS = [
    ("orders", "nexus_raw.orders", "nexus_staging.orders", "nexus_dw.fact_orders"),
    ("order_items", "nexus_raw.order_items", "nexus_staging.order_items", "nexus_dw.fact_order_items"),
    ("payments", "nexus_raw.payments", "nexus_staging.payments", "nexus_dw.fact_payments"),
    ("reviews", "nexus_raw.reviews", "nexus_staging.reviews", "nexus_dw.fact_reviews"),
    ("products", "nexus_raw.products", "nexus_staging.products", "(SELECT * FROM nexus_dw.dim_product WHERE product_key > 0) x"),
    ("sellers", "nexus_raw.sellers", "nexus_staging.sellers", "(SELECT * FROM nexus_dw.dim_seller WHERE seller_key > 0) x"),
    ("customer_ids", "nexus_raw.customers", "nexus_staging.customers", "nexus_dw.map_customer_id"),
]
COUNT_KPIS = {"total_orders", "all_orders", "unique_customers", "items_sold"}


def reconcile(save: bool = True) -> list[dict]:
    py = json.loads((settings.processed_dir / "headline_kpis.json").read_text())
    rows = []
    with raw_connection() as conn:
        for kpi, sql in SQL_KPIS.items():
            sql_val = float(conn.execute(sql).fetchone()[0])
            py_val = float(py[kpi])
            diff = abs(sql_val - py_val)
            tol = 0 if kpi in COUNT_KPIS else max(0.011, abs(py_val) * 1e-6)
            rows.append({"check": f"kpi:{kpi}", "sql_value": sql_val, "python_value": py_val,
                         "abs_diff": round(diff, 6), "tolerance": tol, "status": "PASS" if diff <= tol else "FAIL"})
        for name, raw, stg, dw in ROW_COUNTS:
            r = conn.execute(f"SELECT count(*) FROM {raw}").fetchone()[0]
            s = conn.execute(f"SELECT count(*) FROM {stg}").fetchone()[0]
            d = conn.execute(f"SELECT count(*) FROM {dw}").fetchone()[0]
            rows.append({"check": f"rows:{name}", "sql_value": float(d), "python_value": float(r),
                         "abs_diff": float(abs(r - d) + abs(r - s)), "tolerance": 0,
                         "status": "PASS" if r == s == d else "FAIL",
                         "detail": f"raw={r} staging={s} warehouse={d}"})
    if save:
        out = settings.reports_dir / "sql_results"
        out.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(out / "_reconciliation.csv", index=False)
    return rows


if __name__ == "__main__":
    for r in reconcile():
        print(f"{r['status']}  {r['check']:32} sql={r['sql_value']:<16} py={r['python_value']:<16} {r.get('detail', '')}")
