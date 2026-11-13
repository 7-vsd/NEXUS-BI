"""Bulk loading into PostgreSQL using COPY (fast, batched, transactional).

* ``load_raw_layer``     – raw CSV bytes -> nexus_raw.* (TRUNCATE + COPY)
* ``load_staging``       – cleaned frames -> nexus_staging.* (full or incremental upsert)
* ``build_warehouse``    – CALL nexus_dw.sp_build_warehouse(...)
* ``load_frame``         – generic frame -> table (used for synthetic + ML outputs)
* ``export_tables_csv``  – warehouse tables -> CSV (Power BI import source)
"""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd

from src.config.settings import settings
from src.database.connection import raw_connection
from src.logging.logger import get_logger, log_step
from src.validation.schemas import SCHEMAS

log = get_logger("database.loader")

STAGING_COLUMNS: dict[str, list[str]] = {
    "customers": ["customer_id", "customer_unique_id", "customer_zip_code_prefix", "customer_city", "customer_state"],
    "sellers": ["seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"],
    "geolocation": ["zip_code_prefix", "latitude", "longitude", "sample_points", "city", "state"],
    "category_translation": ["product_category_name", "product_category_name_english", "category_display_name"],
    "products": ["product_id", "product_category_name", "product_name_length", "product_description_length",
                 "product_photos_qty", "product_weight_g", "product_length_cm", "product_height_cm",
                 "product_width_cm", "product_category_name_english", "product_volume_cm3"],
    "orders": ["order_id", "customer_id", "order_status", "order_purchase_timestamp", "order_approved_at",
               "order_delivered_carrier_date", "order_delivered_customer_date", "order_estimated_delivery_date"],
    "order_items": ["order_id", "order_item_id", "product_id", "seller_id", "shipping_limit_date", "price", "freight_value"],
    "payments": ["order_id", "payment_sequential", "payment_type", "payment_installments", "payment_value"],
    "reviews": ["review_id", "order_id", "review_score", "review_comment_title", "review_comment_message",
                "review_creation_date", "review_answer_timestamp"],
}
STAGING_PK = {
    "customers": ["customer_id"], "sellers": ["seller_id"], "geolocation": ["zip_code_prefix"],
    "category_translation": ["product_category_name"], "products": ["product_id"], "orders": ["order_id"],
    "order_items": ["order_id", "order_item_id"], "payments": ["order_id", "payment_sequential"],
    "reviews": ["review_id", "order_id"],
}
# Load order respects logical dependencies
STAGING_ORDER = ["category_translation", "geolocation", "customers", "sellers", "products",
                 "orders", "order_items", "payments", "reviews"]


def _copy_frame(cur, df: pd.DataFrame, table: str, columns: list[str], batch_size: int) -> int:
    cols = ", ".join(columns)
    total = 0
    for start in range(0, len(df), batch_size):
        chunk = df.iloc[start:start + batch_size][columns]
        buf = io.StringIO()
        chunk.to_csv(buf, index=False, header=False, na_rep="", date_format="%Y-%m-%d %H:%M:%S")
        with cur.copy(f"COPY {table} ({cols}) FROM STDIN WITH (FORMAT csv, NULL '')") as cp:
            cp.write(buf.getvalue())
        total += len(chunk)
    return total


def load_raw_layer(sources: dict) -> dict[str, int]:
    """Copy every raw CSV as-is into nexus_raw (TEXT columns)."""
    counts: dict[str, int] = {}
    with log_step("load_raw_layer", log) as info, raw_connection() as conn:
        with conn.cursor() as cur:
            for name, src in sources.items():
                cols = ", ".join(SCHEMAS[name].columns)
                cur.execute(f"TRUNCATE nexus_raw.{name}")
                with src.path.open("r", encoding="utf-8-sig") as fh, \
                        cur.copy(f"COPY nexus_raw.{name} ({cols}) FROM STDIN WITH (FORMAT csv, HEADER true)") as cp:
                    while block := fh.read(1 << 20):
                        cp.write(block)
                cur.execute(f"UPDATE nexus_raw.{name} SET _source_file = %s", (src.path.name,))
                counts[name] = cur.rowcount
                log.info("raw.%s <- %s (%d rows)", name, src.path.name, counts[name])
        info["rows"] = sum(counts.values())
    return counts


def load_staging(frames: dict[str, pd.DataFrame], mode: str = "full") -> dict[str, int]:
    """Load cleaned frames into nexus_staging.

    mode='full'        TRUNCATE + COPY every table.
    mode='incremental' COPY into a temp table and INSERT .. ON CONFLICT DO UPDATE
                       (only rows passed in ``frames`` are touched).
    """
    if mode not in ("full", "incremental"):
        raise ValueError("mode must be 'full' or 'incremental'")
    counts: dict[str, int] = {}
    with log_step("load_staging", log, mode=mode) as info, raw_connection() as conn:
        with conn.cursor() as cur:
            if mode == "full":
                cur.execute("TRUNCATE " + ", ".join(f"nexus_staging.{t}" for t in STAGING_ORDER))
            for name in STAGING_ORDER:
                if name not in frames:
                    continue
                df, cols = frames[name], STAGING_COLUMNS[name]
                if mode == "full":
                    counts[name] = _copy_frame(cur, df, f"nexus_staging.{name}", cols, settings.load_batch_size)
                else:
                    tmp = f"tmp_{name}"
                    cur.execute(f"CREATE TEMP TABLE {tmp} (LIKE nexus_staging.{name} INCLUDING DEFAULTS) ON COMMIT DROP")
                    _copy_frame(cur, df, tmp, cols, settings.load_batch_size)
                    pk = STAGING_PK[name]
                    upd = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c not in pk)
                    cur.execute(f"INSERT INTO nexus_staging.{name} ({', '.join(cols)}) SELECT {', '.join(cols)} FROM {tmp} "
                                f"ON CONFLICT ({', '.join(pk)}) DO UPDATE SET {upd}")
                    counts[name] = cur.rowcount
                log.info("staging.%s <- %d rows (%s)", name, counts[name], mode)
            cur.execute("""INSERT INTO nexus_dw.etl_watermark (table_name, watermark_ts, rows_loaded)
                           SELECT 'staging.orders', max(order_purchase_timestamp), count(*) FROM nexus_staging.orders
                           ON CONFLICT (table_name) DO UPDATE SET watermark_ts = EXCLUDED.watermark_ts,
                               rows_loaded = EXCLUDED.rows_loaded, last_loaded_at = now()""")
        info["rows"] = sum(counts.values())
    return counts


def get_watermark(table_name: str = "staging.orders"):
    with raw_connection() as conn:
        row = conn.execute("SELECT watermark_ts FROM nexus_dw.etl_watermark WHERE table_name = %s",
                           (table_name,)).fetchone()
    return row[0] if row else None


def build_warehouse(since=None) -> dict[str, int]:
    with log_step("build_warehouse", log, since=str(since) if since else "full") as info, raw_connection() as conn:
        conn.execute("CALL nexus_dw.sp_build_warehouse(%s)", (since,))
        counts = {}
        for t in ("dim_date", "dim_location", "dim_customer", "dim_product", "dim_seller", "dim_payment_type",
                  "fact_orders", "fact_order_items", "fact_payments", "fact_reviews"):
            counts[t] = conn.execute(f"SELECT count(*) FROM nexus_dw.{t}").fetchone()[0]
        info.update(counts)
    return counts


def load_frame(df: pd.DataFrame, table: str, columns: list[str] | None = None, truncate: bool = True) -> int:
    columns = columns or list(df.columns)
    with raw_connection() as conn, conn.cursor() as cur:
        if truncate:
            cur.execute(f"TRUNCATE {table}")
        n = _copy_frame(cur, df, table, columns, settings.load_batch_size)
    log.info("%s <- %d rows", table, n)
    return n


def query_df(sql: str, params: tuple | None = None) -> pd.DataFrame:
    with raw_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [d.name for d in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


def export_tables_csv(tables: list[str], out_dir: Path) -> dict[str, int]:
    """Export warehouse tables to CSV (UTF-8, ISO dates) for Power BI import mode."""
    out_dir.mkdir(parents=True, exist_ok=True)
    counts = {}
    with raw_connection() as conn, conn.cursor() as cur:
        for t in tables:
            schema, name = t.split(".")
            cols = cur.execute("""SELECT column_name, data_type FROM information_schema.columns
                                  WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position""",
                               (schema, name)).fetchall()
            # booleans as 'true'/'false' (Power Query parses these; PostgreSQL's default 't'/'f' it does not)
            select = ", ".join(f'"{c}"::text AS "{c}"' if dt == "boolean" else f'"{c}"' for c, dt in cols)
            path = out_dir / f"{name}.csv"
            with path.open("wb") as fh, cur.copy(f"COPY (SELECT {select} FROM {t}) TO STDOUT WITH (FORMAT csv, HEADER true)") as cp:
                for data in cp:
                    fh.write(data)
            counts[t] = sum(1 for _ in path.open("rb")) - 1
    return counts
