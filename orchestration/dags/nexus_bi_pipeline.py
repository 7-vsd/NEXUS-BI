"""NEXUS BI end-to-end pipeline DAG.

EXTRACT -> VALIDATE -> TRANSFORM -> LOAD DATABASE -> RUN ANALYTICS -> GENERATE PREDICTIONS
        -> PUBLISH OUTPUTS -> SEND STATUS (success)  |  SEND FAILURE STATUS (any upstream failure)

* Schedule is configurable via the Airflow Variable ``nexus_bi_schedule`` (cron or preset,
  default "@daily"); set it to "None" for manual runs only.
* Load mode via Variable ``nexus_bi_incremental`` ("true" = watermark-based incremental load).
* Every task is idempotent: it overwrites its own outputs (files, TRUNCATE+COPY / upserts).
* Retries: 2, with exponential back-off; failures route to ``send_failure_status``.
* Requires the project root on PYTHONPATH (see docs/deployment/DEPLOYMENT_GUIDE.md).

Compatible with Airflow 2.7+ and 3.x (imports resolved at parse time).
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta

PROJECT_ROOT = os.environ.get("NEXUS_PROJECT_ROOT", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:  # Airflow 3.x
    from airflow.providers.standard.operators.python import PythonOperator
    from airflow.sdk import DAG, Variable
except ImportError:  # Airflow 2.x
    from airflow import DAG
    from airflow.models import Variable
    from airflow.operators.python import PythonOperator

try:
    from airflow.task.trigger_rule import TriggerRule      # Airflow 3.x
except ImportError:  # pragma: no cover
    from airflow.utils.trigger_rule import TriggerRule     # Airflow 2.x


def _call(task_name: str):
    """Late import so DAG parsing stays fast and does not need pandas/sklearn loaded."""
    def _run(**context):
        from orchestration.tasks import TASKS
        kwargs = {}
        if task_name == "load":
            kwargs["incremental"] = str(Variable.get("nexus_bi_incremental", default="false")).lower() == "true"
        if task_name == "send_failure_status":
            return TASKS["send_status"](status="FAILED", **context)
        return TASKS[task_name](**kwargs, **context)
    return _run


def _schedule():
    try:
        value = Variable.get("nexus_bi_schedule", default="@daily")
    except Exception:  # noqa: BLE001 - metadata DB not reachable during some parses
        value = "@daily"
    return None if str(value).strip().lower() in ("none", "") else value


default_args = {
    "owner": "nexus-data-engineering",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=30),
    "execution_timeout": timedelta(hours=2),
}

with DAG(
    dag_id="nexus_bi_pipeline",
    description="NEXUS BI: ingest, validate, transform, load warehouse, analytics, ML, publish",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule=_schedule(),
    catchup=False,
    max_active_runs=1,
    tags=["nexus-bi", "etl", "ml"],
    doc_md=__doc__,
) as dag:
    steps = [("extract", "EXTRACT"), ("validate", "VALIDATE"), ("transform", "TRANSFORM"), ("load", "LOAD_DATABASE"),
             ("analytics", "RUN_ANALYTICS"), ("predict", "GENERATE_PREDICTIONS"), ("publish", "PUBLISH_OUTPUTS")]
    ops = [PythonOperator(task_id=task_id.lower(), python_callable=_call(name)) for name, task_id in steps]
    send_status = PythonOperator(task_id="send_status", python_callable=_call("send_status"),
                                 trigger_rule=TriggerRule.ALL_SUCCESS, retries=0)
    send_failure = PythonOperator(task_id="send_failure_status", python_callable=_call("send_failure_status"),
                                  trigger_rule=TriggerRule.ONE_FAILED, retries=0)
    for upstream, downstream in zip(ops, ops[1:]):
        upstream >> downstream
    ops[-1] >> send_status
    ops >> send_failure
