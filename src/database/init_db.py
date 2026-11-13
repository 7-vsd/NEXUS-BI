"""Initialise the PostgreSQL database: create schemas, tables, procedures, views.

Usage:  python -m src.database.init_db            (idempotent)
        python -m src.database.init_db --reset    (DROP and recreate all NEXUS schemas)
"""
from __future__ import annotations

import argparse

from src.config.settings import settings
from src.database.connection import raw_connection
from src.logging.logger import get_logger, log_step

log = get_logger("database.init")

# Execution order matters (dependencies)
DDL_FILES = [
    "warehouse/00_schemas.sql",
    "raw/01_raw_tables.sql",
    "staging/01_staging_tables.sql",
    "dimensions/01_dimensions.sql",
    "facts/01_facts.sql",
    "views/01_analytical_views.sql",
    "procedures/01_sp_build_warehouse.sql",
    "ml/01_ml_tables.sql",
    "warehouse/02_security_rls.sql",
]
POST_LOAD_FILES = ["optimization/01_indexes.sql"]
SCHEMAS = ("nexus_ml", "nexus_dw", "nexus_staging", "nexus_raw")


def run_sql_file(conn, relative_path: str) -> None:
    path = settings.sql_dir / relative_path
    sql = path.read_text(encoding="utf-8")
    conn.execute(sql)
    log.info("Executed %s", relative_path)


def init_database(reset: bool = False) -> None:
    with log_step("init_database", log, reset=reset):
        with raw_connection() as conn:
            if reset:
                for s in SCHEMAS:
                    conn.execute(f"DROP SCHEMA IF EXISTS {s} CASCADE")
                log.warning("Dropped schemas %s", SCHEMAS)
            for f in DDL_FILES:
                run_sql_file(conn, f)


def run_post_load_optimization() -> None:
    with raw_connection() as conn:
        for f in POST_LOAD_FILES:
            run_sql_file(conn, f)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reset", action="store_true", help="drop and recreate all NEXUS schemas")
    args = p.parse_args()
    init_database(reset=args.reset)


if __name__ == "__main__":
    main()
