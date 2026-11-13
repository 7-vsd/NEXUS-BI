"""Airflow-independent task callables for the NEXUS BI DAG.

Keeping the logic here (not inside the DAG file) means every task can be unit
tested and run locally without an Airflow installation:

    python -m orchestration.tasks extract
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

from src import pipeline
from src.config.settings import settings
from src.logging.logger import get_logger

log = get_logger("orchestration")


def task_extract(**_) -> dict:
    inv = pipeline.extract()
    return {"rows": int(inv.rows.sum()), "files": len(inv)}


def task_validate(**_) -> dict:
    checks = pipeline.validate(fail_on_error=True)   # raises DataQualityError -> task fails -> retries/alerts
    return {"checks": len(checks), "warnings": int((checks.status == "WARN").sum())}


def task_transform(**_) -> dict:
    t = pipeline.transform()
    return {"orders": len(t["orders"])}


def task_load(incremental: bool = False, **_) -> dict:
    return {k: int(v) for k, v in pipeline.load(incremental=incremental).items()}


def task_analytics(**_) -> dict:
    res = pipeline.analytics(skip_db=False)
    failed = [r for r in res["reconciliation"] if r["status"] != "PASS"]
    if failed:
        raise RuntimeError(f"SQL/Python reconciliation failed: {[r['check'] for r in failed]}")
    return {"queries": len(res["queries"]), "reconciliation": "PASS"}


def task_predict(**_) -> dict:
    m = pipeline.predict()
    return {"modules": list(m)}


def task_publish(**_) -> dict:
    return pipeline.publish(skip_db=False)


def task_send_status(status: str = "SUCCESS", **context) -> dict:
    """Write a status record (consumed by the Streamlit System Monitoring page).

    Hook point for e-mail/Teams/Slack: configure an Airflow connection and
    replace the log call; no external notification is sent by default.
    """
    payload = {"status": status, "dag_run": str(context.get("run_id", "local")),
               "finished_at": datetime.now(timezone.utc).isoformat()}
    (settings.logs_dir / "last_pipeline_status.json").write_text(json.dumps(payload, indent=2))
    log.info("Pipeline status: %s", payload)
    return payload


TASKS = {"extract": task_extract, "validate": task_validate, "transform": task_transform, "load": task_load,
         "analytics": task_analytics, "predict": task_predict, "publish": task_publish, "send_status": task_send_status}

if __name__ == "__main__":
    print(TASKS[sys.argv[1]]())
