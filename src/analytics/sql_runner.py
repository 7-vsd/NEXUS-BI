"""Run the SQL analytics library, save every result set and build a catalogue.

Query files contain blocks introduced by ``-- @query <id>`` followed by
``-- @category``, ``-- @description`` and ``-- @output`` metadata lines.

    python -m src.analytics.sql_runner
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.config.settings import settings
from src.database.connection import raw_connection
from src.logging.logger import get_logger

log = get_logger("analytics.sql")
QUERY_DIRS = [settings.sql_dir / "analytics", settings.sql_dir / "optimization"]
OUT_DIR = settings.reports_dir / "sql_results"


@dataclass
class SqlQuery:
    query_id: str
    category: str
    description: str
    output: str
    sql: str
    source_file: str


def parse_query_file(path: Path) -> list[SqlQuery]:
    text = path.read_text(encoding="utf-8")
    blocks = re.split(r"^-- @query\s+", text, flags=re.M)[1:]
    queries = []
    for b in blocks:
        lines = b.splitlines()
        qid = lines[0].strip()
        meta = {k: "" for k in ("category", "description", "output")}
        body = []
        for ln in lines[1:]:
            m = re.match(r"^-- @(category|description|output)\s+(.*)$", ln)
            if m:
                meta[m.group(1)] = m.group(2).strip()
            else:
                body.append(ln)
        sql = "\n".join(body).strip().rstrip(";")
        queries.append(SqlQuery(qid, meta["category"], meta["description"], meta["output"], sql, path.name))
    return queries


def load_library() -> list[SqlQuery]:
    qs: list[SqlQuery] = []
    for d in QUERY_DIRS:
        for f in sorted(d.glob("*.sql")):
            if f.name.startswith("01_indexes"):
                continue
            qs += parse_query_file(f)
    return qs


def run_query(conn, q: SqlQuery) -> pd.DataFrame:
    with conn.cursor() as cur:
        cur.execute(q.sql)
        cols = [c.name for c in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


def run_query_library(save: bool = True) -> list[dict]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    with raw_connection() as conn:
        for q in load_library():
            t0 = time.perf_counter()
            try:
                df = run_query(conn, q)
                status, err = "OK", ""
                if save:
                    df.to_csv(OUT_DIR / f"{q.query_id}.csv", index=False)
            except Exception as exc:  # noqa: BLE001 - recorded per query
                conn.rollback()
                df, status, err = pd.DataFrame(), "ERROR", str(exc).splitlines()[0]
                log.error("%s failed: %s", q.query_id, err)
            results.append({"query_id": q.query_id, "category": q.category, "description": q.description,
                            "output_schema": q.output, "source_file": q.source_file, "status": status,
                            "rows": len(df), "ms": round(1000 * (time.perf_counter() - t0), 1), "error": err})
    cat = pd.DataFrame(results)
    if save:
        cat.to_csv(OUT_DIR / "_query_catalog.csv", index=False)
    log.info("SQL library: %d queries, %d OK", len(cat), int((cat.status == "OK").sum()))
    return results


if __name__ == "__main__":
    for r in run_query_library():
        print(f"{r['status']:5} {r['query_id']:45} rows={r['rows']:<5} {r['ms']}ms {r['error']}")
