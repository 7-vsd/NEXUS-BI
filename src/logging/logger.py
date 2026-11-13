"""Structured logging for every NEXUS BI module.

Logs go to the console and to ``logs/nexus_bi.log``. Pipeline steps are also
appended as JSON lines to ``logs/pipeline_runs.jsonl`` so the Streamlit
"System Monitoring" page can display execution history.
"""
from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

from src.config.settings import settings

_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_configured = False


def _configure() -> None:
    global _configured
    if _configured:
        return
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger("nexus")
    root.setLevel(settings.log_level.upper())
    fmt = logging.Formatter(_FORMAT)
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    file_handler = logging.FileHandler(settings.logs_dir / "nexus_bi.log", encoding="utf-8")
    file_handler.setFormatter(fmt)
    root.addHandler(console)
    root.addHandler(file_handler)
    root.propagate = False
    _configured = True


def get_logger(name: str) -> logging.Logger:
    _configure()
    return logging.getLogger(f"nexus.{name}")


def _write_run_record(record: dict) -> None:
    path = settings.logs_dir / "pipeline_runs.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=str) + "\n")


@contextmanager
def log_step(step: str, logger: logging.Logger | None = None, **context) -> Iterator[dict]:
    """Time a pipeline step, log start/end, and persist a JSON run record.

    The yielded dict can be enriched by the caller (e.g. ``info['rows'] = n``).
    Exceptions are logged, recorded with status FAILED and re-raised.
    """
    log = logger or get_logger("pipeline")
    info: dict = {"step": step, **context}
    start = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    log.info("START %s %s", step, context or "")
    try:
        yield info
    except Exception as exc:
        info.update(status="FAILED", error=repr(exc))
        log.exception("FAILED %s", step)
        raise
    else:
        info.setdefault("status", "SUCCESS")
        log.info("END   %s (%.2fs) %s", step, time.perf_counter() - start,
                 {k: v for k, v in info.items() if k not in ("step", "status")})
    finally:
        info.update(started_at=started_at, duration_s=round(time.perf_counter() - start, 3))
        _write_run_record(info)
