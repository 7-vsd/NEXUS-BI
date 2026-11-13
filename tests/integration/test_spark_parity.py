"""PySpark ↔ pandas parity for the scale-out transforms (skipped when PySpark/Java are unavailable)."""
from __future__ import annotations

import importlib.util
import shutil

import pandas as pd
import pytest

from src.config.settings import settings

pytestmark = pytest.mark.skipif(importlib.util.find_spec("pyspark") is None or shutil.which("java") is None
                                or not (settings.processed_dir / "order_mart.parquet").exists(),
                                reason="PySpark/Java or processed data not available")


@pytest.fixture(scope="module")
def spark():
    from src.transformation.spark_jobs import get_spark
    s = get_spark("nexus-bi-tests")
    yield s
    s.stop()


def test_geolocation_parity(spark):
    from src.transformation.spark_jobs import geolocation_spark
    sp = geolocation_spark(spark, settings.raw_dir / "olist_geolocation_dataset.csv").toPandas().set_index("zip_code_prefix")
    pdf = pd.read_parquet(settings.staging_dir / "clean" / "geolocation.parquet").set_index("zip_code_prefix")
    assert set(sp.index) == set(pdf.index)
    j = pdf.join(sp, rsuffix="_spark")
    assert (j.sample_points == j.sample_points_spark).all()
    assert (j.latitude - j.latitude_spark).abs().max() < 1e-9
    assert (j.longitude - j.longitude_spark).abs().max() < 1e-9
    assert (j.state == j.state_spark).mean() > 0.999      # modal ties may resolve differently in < 0.1% of prefixes


def test_daily_revenue_parity(spark):
    from src.transformation.spark_jobs import daily_revenue_spark
    sp = daily_revenue_spark(spark, settings.processed_dir / "order_mart.parquet").toPandas()
    sp["date"] = pd.to_datetime(sp.date)
    d = pd.read_parquet(settings.processed_dir / "daily_kpis.parquet")
    d = d[d.orders > 0][["date", "revenue", "orders", "customers"]]
    m = d.merge(sp, on="date", suffixes=("", "_spark"))
    assert len(m) == len(d) == len(sp)
    assert (m.revenue - m.revenue_spark).abs().max() < 0.011
    assert (m.orders == m.orders_spark).all() and (m.customers == m.customers_spark).all()
