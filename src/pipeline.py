"""NEXUS BI end-to-end pipeline.

Each stage reads its inputs from disk and writes its outputs to disk, so the
stages are independent, repeatable and idempotent (re-running a stage
overwrites its own outputs). The same functions are called by the CLI, the
Makefile and the Airflow DAG.

    python -m src.pipeline --stage all              # everything
    python -m src.pipeline --stage extract|validate|transform|load|analytics|predict|publish
    python -m src.pipeline --stage load --incremental
    python -m src.pipeline --stage all --skip-db     # no PostgreSQL available
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

import pandas as pd

from src.config.settings import settings
from src.ingestion.discovery import discover_sources
from src.ingestion.reader import ingest_all, memory_mb
from src.logging.logger import get_logger, log_step
from src.transformation import (category_translation, customers, geolocation, order_items, orders, payments,
                                products, reviews, sellers)
from src.transformation.common import CleaningLog
from src.transformation import marts
from src.validation.profiling import build_data_dictionary, profile_dataset
from src.validation.quality import run_all_checks
from src.validation.report import write_quality_report

log = get_logger("pipeline")
TYPED = settings.staging_dir / "typed"
CLEAN = settings.staging_dir / "clean"
DQ_DIR = settings.reports_dir / "data_quality"


class DataQualityError(RuntimeError):
    pass


def _save(df: pd.DataFrame, path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def _read_dir(folder) -> dict[str, pd.DataFrame]:
    return {p.stem: pd.read_parquet(p) for p in sorted(folder.glob("*.parquet"))}


# --------------------------------------------------------------------------- 1
def extract() -> pd.DataFrame:
    """Discover + ingest raw CSVs (schema validated, typed) -> data/staging/typed."""
    settings.ensure_dirs()
    with log_step("extract", log) as info:
        sources = discover_sources()
        results = ingest_all(sources)
        inv = []
        for name, r in results.items():
            _save(r.frame, TYPED / f"{name}.parquet")
            src = sources[name]
            inv.append({"dataset": name, "file": src.path.name, "size_mb": round(src.size_bytes / 1e6, 2),
                        "md5": src.md5, "rows": r.rows, "columns": r.frame.shape[1],
                        "memory_mb": memory_mb(r.frame), "cast_failures": sum(r.cast_failures.values()),
                        "extra_columns": ", ".join(r.extra_columns)})
        inventory = pd.DataFrame(inv)
        DQ_DIR.mkdir(parents=True, exist_ok=True)
        inventory.to_csv(DQ_DIR / "source_inventory.csv", index=False)
        info["rows"] = int(inventory.rows.sum())
    return inventory


# --------------------------------------------------------------------------- 2
def validate(fail_on_error: bool = True) -> pd.DataFrame:
    """Profile + data-quality checks on the typed source data."""
    with log_step("validate", log) as info:
        frames = _read_dir(TYPED)
        checks = run_all_checks(frames)
        profile = pd.concat([profile_dataset(n, df) for n, df in frames.items()], ignore_index=True)
        dictionary = build_data_dictionary(frames)
        checks.to_csv(DQ_DIR / "dq_checks.csv", index=False)
        profile.to_csv(DQ_DIR / "column_profile.csv", index=False)
        dictionary.to_csv(DQ_DIR / "data_dictionary.csv", index=False)
        blocking = checks[(checks.status == "FAIL")]
        info.update(checks=len(checks), passed=int((checks.status == "PASS").sum()),
                    warnings=int((checks.status == "WARN").sum()), errors=len(blocking))
        if fail_on_error and len(blocking):
            raise DataQualityError(f"Blocking data-quality errors:\n{blocking[['dataset', 'check', 'column', 'failed_rows']]}")
    return checks


# --------------------------------------------------------------------------- 3
def transform() -> dict[str, pd.DataFrame]:
    """Clean every dataset, build marts, synthetic data, sample data and the DQ HTML report."""
    from src.synthetic import generate as syn

    with log_step("transform", log) as info:
        raw = _read_dir(TYPED)
        clog = CleaningLog()
        t = {
            "category_translation": category_translation.transform(raw["category_translation"], clog),
            "geolocation": geolocation.transform(raw["geolocation"], clog),
            "customers": customers.transform(raw["customers"], clog),
            "sellers": sellers.transform(raw["sellers"], clog),
            "products": products.transform(raw["products"], raw["category_translation"], clog),
            "orders": orders.transform(raw["orders"], clog),
            "order_items": order_items.transform(raw["order_items"], clog),
            "payments": payments.transform(raw["payments"], clog),
            "reviews": reviews.transform(raw["reviews"], clog),
        }
        for name, df in t.items():
            _save(df, CLEAN / f"{name}.parquet")

        items = marts.build_items_enriched(t)
        om = marts.build_order_mart(t, items)
        cm = marts.build_customer_mart(om)
        daily = marts.build_daily_kpis(om)
        catw = marts.build_category_weekly(items)
        P = settings.processed_dir
        _save(items, P / "items_enriched.parquet")
        _save(om, P / "order_mart.parquet")
        _save(cm, P / "customer_mart.parquet")
        _save(daily, P / "daily_kpis.parquet")
        _save(catw, P / "category_weekly.parquet")
        kpis = marts.headline_kpis(om)
        (P / "headline_kpis.json").write_text(json.dumps(kpis, indent=2))

        # SYNTHETIC (clearly separated)
        costs = syn.product_costs(items)
        inv = syn.weekly_inventory(catw)
        settings.synthetic_dir.mkdir(parents=True, exist_ok=True)
        costs.to_csv(settings.synthetic_dir / "synthetic_product_costs.csv", index=False)
        inv.to_csv(settings.synthetic_dir / "synthetic_inventory_weekly.csv", index=False)

        # Small GitHub-friendly sample (first 2,000 orders + related rows)
        _write_sample(t)

        clog_df = clog.to_frame()
        clog_df.to_csv(DQ_DIR / "cleaning_log.csv", index=False)
        inventory = pd.read_csv(DQ_DIR / "source_inventory.csv")
        checks = pd.read_csv(DQ_DIR / "dq_checks.csv")
        profile = pd.read_csv(DQ_DIR / "column_profile.csv")
        write_quality_report(DQ_DIR / "data_quality_report.html", inventory, checks, profile, clog_df)
        info.update(orders=len(om), customers=len(cm), revenue=kpis["total_revenue"])
    return t


def _write_sample(t: dict[str, pd.DataFrame], n_orders: int = 2000) -> None:
    o = t["orders"].sort_values("order_purchase_timestamp").iloc[::max(1, len(t["orders"]) // n_orders)].head(n_orders)
    ids = set(o.order_id)
    sample = {
        "orders": o,
        "order_items": t["order_items"][t["order_items"].order_id.isin(ids)],
        "payments": t["payments"][t["payments"].order_id.isin(ids)],
        "reviews": t["reviews"][t["reviews"].order_id.isin(ids)],
        "customers": t["customers"][t["customers"].customer_id.isin(o.customer_id)],
    }
    sample["products"] = t["products"][t["products"].product_id.isin(sample["order_items"].product_id)]
    sample["sellers"] = t["sellers"][t["sellers"].seller_id.isin(sample["order_items"].seller_id)]
    for name, df in sample.items():
        df.to_csv(settings.sample_dir / f"sample_{name}.csv", index=False)


# --------------------------------------------------------------------------- 4
def load(incremental: bool = False) -> dict:
    """Initialise DB objects and load raw -> staging -> warehouse (+ synthetic)."""
    from src.database import loader
    from src.database.init_db import init_database, run_post_load_optimization

    with log_step("load", log, incremental=incremental) as info:
        init_database()
        clean = _read_dir(CLEAN)
        since = None
        if incremental:
            wm = loader.get_watermark()
            if wm is not None:
                new_orders = clean["orders"][clean["orders"].order_purchase_timestamp > wm]
                ids = set(new_orders.order_id)
                for k in ("order_items", "payments", "reviews"):
                    clean[k] = clean[k][clean[k].order_id.isin(ids)]
                clean["orders"] = new_orders
                since = new_orders.order_purchase_timestamp.min() if len(new_orders) else None
                log.info("Incremental load: %d new orders after watermark %s", len(new_orders), wm)
                loader.load_staging(clean, mode="incremental")
                counts = loader.build_warehouse(since=since) if since is not None else {}
                info.update(new_orders=len(new_orders))
                return counts
        loader.load_raw_layer(discover_sources(with_checksum=False))
        loader.load_staging(clean, mode="full")
        counts = loader.build_warehouse()
        costs = pd.read_csv(settings.synthetic_dir / "synthetic_product_costs.csv")
        loader.load_frame(costs.rename(columns={"product_category_name_english": "category_name_en"}),
                          "nexus_dw.syn_product_cost",
                          ["product_id", "category_name_en", "median_price", "cost_ratio", "unit_cost_brl", "is_synthetic"])
        inv = pd.read_csv(settings.synthetic_dir / "synthetic_inventory_weekly.csv").rename(columns={"week": "week_start"})
        loader.load_frame(inv, "nexus_dw.syn_inventory_weekly")
        run_post_load_optimization()
        info.update(counts)
    return counts


# --------------------------------------------------------------------------- 5
def analytics(skip_db: bool = False) -> dict:
    from src.analytics.reconciliation import reconcile
    from src.analytics.sql_runner import run_query_library

    with log_step("analytics", log, skip_db=skip_db) as info:
        result = {}
        if not skip_db:
            result["queries"] = run_query_library()
            result["reconciliation"] = reconcile()
            info.update(queries_ok=sum(1 for q in result["queries"] if q["status"] == "OK"),
                        reconciliation_pass=all(r["status"] == "PASS" for r in result["reconciliation"]))
    return result


# --------------------------------------------------------------------------- 6
def predict() -> dict:
    from ml.train_all import train_all

    with log_step("predict", log) as info:
        metrics = train_all()
        info["modules"] = list(metrics)
    return metrics


# --------------------------------------------------------------------------- 7
def publish(skip_db: bool = False) -> dict:
    """Write ML outputs to nexus_ml, export Power BI CSVs, write a status file."""
    from src.analytics.publish import publish_outputs

    with log_step("publish", log, skip_db=skip_db) as info:
        out = publish_outputs(skip_db=skip_db)
        info.update(out)
    return out


def write_status(status: str, stages: list[str], error: str | None = None) -> None:
    payload = {"status": status, "stages": stages, "error": error,
               "finished_at": datetime.now(timezone.utc).isoformat()}
    (settings.logs_dir / "last_pipeline_status.json").write_text(json.dumps(payload, indent=2))


STAGES = ["extract", "validate", "transform", "load", "analytics", "predict", "publish"]


def run(stage: str = "all", incremental: bool = False, skip_db: bool = False) -> None:
    todo = STAGES if stage == "all" else [stage]
    if skip_db:
        todo = [s for s in todo if s != "load"]
    done: list[str] = []
    try:
        for s in todo:
            if s == "extract":
                extract()
            elif s == "validate":
                validate()
            elif s == "transform":
                transform()
            elif s == "load":
                load(incremental=incremental)
            elif s == "analytics":
                analytics(skip_db=skip_db)
            elif s == "predict":
                predict()
            elif s == "publish":
                publish(skip_db=skip_db)
            done.append(s)
        write_status("SUCCESS", done)
    except Exception as exc:
        write_status("FAILED", done, repr(exc))
        raise


def main() -> None:
    p = argparse.ArgumentParser(description="NEXUS BI pipeline")
    p.add_argument("--stage", default="all", choices=["all", *STAGES])
    p.add_argument("--incremental", action="store_true", help="incremental load based on the orders watermark")
    p.add_argument("--skip-db", action="store_true", help="run without PostgreSQL (file outputs only)")
    a = p.parse_args()
    run(a.stage, a.incremental, a.skip_db)


if __name__ == "__main__":
    main()
