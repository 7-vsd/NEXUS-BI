"""Database connectivity helpers (SQLAlchemy engine + raw psycopg connection)."""
from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator

import psycopg
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from src.config.settings import settings
from src.logging.logger import get_logger

log = get_logger("database")


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    log.info("Creating engine for %s", settings.safe_database_url)
    return create_engine(settings.database_url, pool_pre_ping=True, future=True)


def psycopg_conninfo() -> str:
    parts = {"host": settings.db_host, "port": settings.db_port, "dbname": settings.db_name, "user": settings.db_user}
    if settings.db_password:
        parts["password"] = settings.db_password
    return " ".join(f"{k}={v}" for k, v in parts.items())


@contextmanager
def raw_connection(autocommit: bool = False) -> Iterator[psycopg.Connection]:
    conn = psycopg.connect(psycopg_conninfo(), autocommit=autocommit)
    try:
        yield conn
        if not autocommit:
            conn.commit()
    except Exception:
        if not autocommit:
            conn.rollback()
        raise
    finally:
        conn.close()


def is_database_available(timeout_s: int = 3) -> bool:
    try:
        with psycopg.connect(psycopg_conninfo(), connect_timeout=timeout_s) as conn:
            conn.execute("SELECT 1")
        return True
    except Exception as exc:  # noqa: BLE001 - availability probe
        log.warning("Database not available: %s", exc.__class__.__name__)
        return False


def scalar(sql: str, **params):
    with get_engine().connect() as conn:
        return conn.execute(text(sql), params).scalar()
