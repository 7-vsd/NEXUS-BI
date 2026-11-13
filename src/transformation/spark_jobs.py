"""Optional PySpark implementations for scale-out processing.

The pandas pipeline comfortably handles the Olist volume (~1.5M rows) on one
machine. These Spark jobs implement the two heaviest transforms – the 1M-row
geolocation aggregation and the daily KPI aggregation – with IDENTICAL business
rules, so the platform can move to a Spark cluster (e.g. Azure Databricks /
Synapse) when volumes grow. Parity with pandas is asserted by
``tests/integration/test_spark_parity.py``.

    python -m src.transformation.spark_jobs      # runs both jobs locally (local[*])
"""
from __future__ import annotations

from pathlib import Path

from src.config.settings import settings
from src.validation.quality import BRAZIL_LAT, BRAZIL_LNG


def get_spark(app: str = "nexus-bi"):
    from pyspark.sql import SparkSession

    return (SparkSession.builder.appName(app).master("local[*]")
            .config("spark.sql.shuffle.partitions", "8").config("spark.ui.enabled", "false")
            .config("spark.sql.session.timeZone", "UTC").getOrCreate())


def geolocation_spark(spark, raw_csv: Path):
    """Spark equivalent of src.transformation.geolocation.transform."""
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    import pandas as pd

    from src.transformation.common import normalize_city

    df = spark.read.csv(str(raw_csv), header=True, inferSchema=False)
    # City normalisation must match pandas exactly (full Unicode NFKD accent stripping). Spark has no NFKD
    # function, so the SAME Python function is applied to the few thousand DISTINCT city spellings on the
    # driver and broadcast-joined back – exact parity, still scalable to billions of rows.
    raw_cities = [r[0] for r in df.select("geolocation_city").distinct().collect() if r[0] is not None]
    mapping = pd.DataFrame({"geolocation_city": raw_cities})
    mapping["city"] = normalize_city(pd.Series(raw_cities, dtype="string")).astype(object)
    city_map = spark.createDataFrame(mapping.astype(str))
    df = df.join(F.broadcast(city_map), "geolocation_city", "left")
    df = (df.select(F.lpad(F.trim("geolocation_zip_code_prefix"), 5, "0").alias("zip_code_prefix"),
                    F.col("geolocation_lat").cast("double").alias("lat"),
                    F.col("geolocation_lng").cast("double").alias("lng"),
                    F.col("city"), F.upper(F.trim("geolocation_state")).alias("state"))
            .dropDuplicates()
            .where(F.col("lat").between(*BRAZIL_LAT) & F.col("lng").between(*BRAZIL_LNG)))
    agg = df.groupBy("zip_code_prefix").agg(F.percentile_approx("lat", 0.5, 100000).alias("latitude_approx"),
                                            F.expr("median(lat)").alias("latitude"),
                                            F.expr("median(lng)").alias("longitude"),
                                            F.count("*").alias("sample_points"))
    w = Window.partitionBy("zip_code_prefix").orderBy(F.desc("n"), F.asc("city"), F.asc("state"))
    modal = (df.groupBy("zip_code_prefix", "city", "state").agg(F.count("*").alias("n"))
               .withColumn("rk", F.row_number().over(w)).where("rk = 1").drop("rk", "n"))
    return agg.drop("latitude_approx").join(modal, "zip_code_prefix", "left")


def daily_revenue_spark(spark, order_mart_parquet: Path):
    """Spark equivalent of the revenue/orders part of marts.build_daily_kpis."""
    from pyspark.sql import functions as F

    om = spark.read.parquet(str(order_mart_parquet))
    return (om.where(F.col("is_revenue_order"))
              .groupBy(F.to_date("order_purchase_timestamp").alias("date"))
              .agg(F.round(F.sum("revenue"), 2).alias("revenue"), F.countDistinct("order_id").alias("orders"),
                   F.countDistinct("customer_unique_id").alias("customers")))


if __name__ == "__main__":
    spark = get_spark()
    g = geolocation_spark(spark, settings.raw_dir / "olist_geolocation_dataset.csv")
    print("geolocation zip prefixes:", g.count())
    d = daily_revenue_spark(spark, settings.processed_dir / "order_mart.parquet")
    print("days with revenue:", d.count())
    spark.stop()
