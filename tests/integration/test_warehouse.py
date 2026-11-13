"""SQL integration tests: key integrity, duplicates, SCD2, reconciliation, query library, idempotency.

Requires a running PostgreSQL loaded by the pipeline (NEXUS_DB_* env vars); skipped otherwise.
"""
from __future__ import annotations

import pytest

from src.database.connection import is_database_available

pytestmark = [pytest.mark.db, pytest.mark.skipif(not is_database_available(), reason="PostgreSQL not available")]


@pytest.fixture(scope="module")
def conn():
    from src.database.connection import raw_connection
    with raw_connection(autocommit=True) as c:
        yield c


def one(conn, sql):
    return conn.execute(sql).fetchone()[0]


@pytest.mark.parametrize("table,key", [
    ("fact_orders", "order_id"), ("fact_order_items", "order_id, order_item_id"),
    ("fact_payments", "order_id, payment_sequential"), ("fact_reviews", "review_id, order_id"),
    ("dim_customer", "customer_key"), ("dim_product", "product_id"), ("dim_seller", "seller_id"),
    ("dim_date", "date_key"), ("dim_location", "zip_code_prefix"),
])
def test_no_duplicate_keys(conn, table, key):
    assert one(conn, f"SELECT count(*) - count(DISTINCT ({key})) FROM nexus_dw.{table}") == 0


@pytest.mark.parametrize("fact,col,dim,dcol", [
    ("fact_orders", "customer_key", "dim_customer", "customer_key"),
    ("fact_orders", "purchase_date_key", "dim_date", "date_key"),
    ("fact_order_items", "product_key", "dim_product", "product_key"),
    ("fact_order_items", "seller_key", "dim_seller", "seller_key"),
    ("fact_payments", "payment_type_key", "dim_payment_type", "payment_type_key"),
])
def test_no_orphan_or_unknown_keys(conn, fact, col, dim, dcol):
    assert one(conn, f"SELECT count(*) FROM nexus_dw.{fact} f LEFT JOIN nexus_dw.{dim} d ON d.{dcol} = f.{col} "
                     f"WHERE d.{dcol} IS NULL") == 0
    assert one(conn, f"SELECT count(*) FROM nexus_dw.{fact} WHERE {col} = -1") == 0    # nothing fell into 'Unknown'


def test_surrogate_keys_positive_except_unknown(conn):
    for t, k in [("dim_product", "product_key"), ("dim_seller", "seller_key"), ("dim_location", "location_key")]:
        assert one(conn, f"SELECT count(*) FROM nexus_dw.{t} WHERE {k} = 0") == 0


def test_scd2_customer_versions_are_contiguous(conn):
    # exactly one current version per person, and versions never overlap
    assert one(conn, "SELECT count(*) FROM (SELECT customer_unique_id FROM nexus_dw.dim_customer WHERE customer_key > 0 "
                     "GROUP BY 1 HAVING sum(is_current::int) <> 1) x") == 0
    assert one(conn, """SELECT count(*) FROM nexus_dw.dim_customer a JOIN nexus_dw.dim_customer b
                        ON a.customer_unique_id = b.customer_unique_id AND a.customer_key < b.customer_key
                        AND a.valid_from <= b.valid_to AND b.valid_from <= a.valid_to WHERE a.customer_key > 0""") == 0
    assert one(conn, "SELECT count(*) FROM nexus_dw.dim_customer WHERE version_number > 1") > 0


def test_fact_grain_no_fanout(conn):
    # order-level money in fact_orders equals the item-level sum (no double counting)
    diff = one(conn, """SELECT max(abs(f.items_price - i.s)) FROM nexus_dw.fact_orders f
                        JOIN (SELECT order_id, sum(price) s FROM nexus_dw.fact_order_items GROUP BY 1) i USING (order_id)""")
    assert float(diff) < 0.01


def test_sql_python_reconciliation_all_pass():
    from src.analytics.reconciliation import reconcile
    res = reconcile(save=False)
    failed = [r for r in res if r["status"] != "PASS"]
    assert not failed, failed


def test_query_library_runs_and_has_40_plus():
    from src.analytics.sql_runner import run_query_library
    res = run_query_library(save=False)
    assert len(res) >= 40
    assert all(r["status"] == "OK" for r in res), [r for r in res if r["status"] != "OK"]
    assert all(r["rows"] > 0 for r in res)


def test_sql_matches_python_for_category_and_state(conn):
    import pandas as pd
    from src.config.settings import settings
    items = pd.read_parquet(settings.processed_dir / "items_enriched.parquet")
    py = items[items.is_revenue_order].groupby("product_category_name_english").price.sum()
    sql = dict(conn.execute("""SELECT p.category_name_en, sum(i.price) FROM nexus_dw.fact_order_items i
                               JOIN nexus_dw.dim_product p USING (product_key) WHERE i.is_revenue_order GROUP BY 1""").fetchall())
    for cat in py.nlargest(10).index:
        assert float(sql[cat]) == pytest.approx(py[cat], abs=0.05)
    om = pd.read_parquet(settings.processed_dir / "order_mart.parquet")
    py_state = om[om.is_revenue_order].groupby("customer_state").revenue.sum()
    sql_state = dict(conn.execute("""SELECT c.state, sum(f.revenue) FROM nexus_dw.fact_orders f
                                     JOIN nexus_dw.dim_customer c USING (customer_key) WHERE f.is_revenue_order GROUP BY 1""").fetchall())
    for s in py_state.index:
        assert float(sql_state[s]) == pytest.approx(py_state[s], abs=0.05)


def test_materialized_views_populated(conn):
    for mv in ("mv_daily_kpis", "mv_monthly_category_sales", "mv_customer_rfm"):
        assert one(conn, f"SELECT count(*) FROM nexus_dw.{mv}") > 0


def test_ml_tables_published(conn):
    for t in ("customer_segments", "churn_scores", "revenue_forecast", "demand_forecast", "anomalies"):
        assert one(conn, f"SELECT count(*) FROM nexus_ml.{t}") > 0


def test_incremental_fact_reload_is_idempotent(conn):
    """Delete the last month of facts, reload incrementally via the procedure, and compare with the original."""
    before = conn.execute("SELECT count(*), sum(revenue) FROM nexus_dw.fact_orders").fetchone()
    before_items = one(conn, "SELECT count(*) FROM nexus_dw.fact_order_items")
    conn.execute("CALL nexus_dw.sp_load_facts('2018-08-01')")
    conn.execute("CALL nexus_dw.sp_load_facts('2018-08-01')")          # twice -> still identical
    after = conn.execute("SELECT count(*), sum(revenue) FROM nexus_dw.fact_orders").fetchone()
    assert before == after and one(conn, "SELECT count(*) FROM nexus_dw.fact_order_items") == before_items


def test_scd2_merge_adds_version_for_moved_customer(conn):
    """Simulate a returning customer with a new address arriving incrementally, then roll back."""
    conn.execute("BEGIN")
    try:
        uid = one(conn, "SELECT customer_unique_id FROM nexus_dw.dim_customer WHERE customer_key > 0 AND is_current LIMIT 1")
        n0 = one(conn, f"SELECT count(*) FROM nexus_dw.dim_customer WHERE customer_unique_id = '{uid}'")
        conn.execute(f"""INSERT INTO nexus_staging.customers VALUES ('zztestcust0000000000000000000000', '{uid}', '69900', 'rio branco', 'AC')""")
        conn.execute("""INSERT INTO nexus_staging.orders (order_id, customer_id, order_status, order_purchase_timestamp,
                        order_estimated_delivery_date) VALUES ('zztestorder000000000000000000000', 'zztestcust0000000000000000000000',
                        'processing', '2018-09-01', '2018-09-20')""")
        conn.execute("CALL nexus_dw.sp_merge_dim_customer()")
        rows = conn.execute(f"""SELECT version_number, is_current, state FROM nexus_dw.dim_customer
                                WHERE customer_unique_id = '{uid}' ORDER BY version_number""").fetchall()
        assert len(rows) == n0 + 1 and rows[-1][1] is True and rows[-1][2] == "AC"
        assert sum(r[1] for r in rows) == 1
    finally:
        conn.execute("ROLLBACK")
