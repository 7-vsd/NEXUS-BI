"""Data-quality assertions on the real processed outputs (skip if the pipeline has not run)."""
from __future__ import annotations

import json

import pandas as pd
import pytest

from src.config.settings import settings

P = settings.processed_dir
pytestmark = pytest.mark.skipif(not (P / "order_mart.parquet").exists(), reason="run the pipeline first")


@pytest.fixture(scope="module")
def om():
    return pd.read_parquet(P / "order_mart.parquet")


@pytest.fixture(scope="module")
def clean():
    d = settings.staging_dir / "clean"
    return {p.stem: pd.read_parquet(p) for p in d.glob("*.parquet")}


def test_primary_keys_unique(clean):
    keys = {"customers": ["customer_id"], "orders": ["order_id"], "order_items": ["order_id", "order_item_id"],
            "payments": ["order_id", "payment_sequential"], "reviews": ["review_id", "order_id"],
            "products": ["product_id"], "sellers": ["seller_id"], "geolocation": ["zip_code_prefix"]}
    for t, k in keys.items():
        assert not clean[t].duplicated(k).any(), t


def test_referential_integrity(clean):
    assert clean["orders"].customer_id.isin(clean["customers"].customer_id).all()
    assert clean["order_items"].order_id.isin(clean["orders"].order_id).all()
    assert clean["order_items"].product_id.isin(clean["products"].product_id).all()
    assert clean["order_items"].seller_id.isin(clean["sellers"].seller_id).all()
    assert clean["payments"].order_id.isin(clean["orders"].order_id).all()
    assert clean["reviews"].order_id.isin(clean["orders"].order_id).all()


def test_raw_rows_preserved(clean):
    inv = pd.read_csv(settings.reports_dir / "data_quality" / "source_inventory.csv").set_index("dataset").rows
    for t in ["customers", "orders", "order_items", "payments", "reviews", "products", "sellers"]:
        assert len(clean[t]) == inv[t], f"{t}: rows lost in cleaning"


def test_domain_rules(clean, om):
    assert (clean["order_items"].price > 0).all() and (clean["order_items"].freight_value >= 0).all()
    assert clean["reviews"].review_score.between(1, 5).all()
    assert (clean["payments"].payment_installments >= 1).all()
    assert clean["customers"].customer_zip_code_prefix.str.fullmatch(r"\d{5}").all()
    assert clean["products"].product_category_name_english.notna().all()
    d = om[om.is_delivered]
    assert (d.delivery_days >= 0).all()


def test_order_mart_no_fanout(om, clean):
    assert om.order_id.is_unique and len(om) == len(clean["orders"])
    items = clean["order_items"].groupby("order_id")[["price", "freight_value"]].sum()
    m = om.set_index("order_id")[["items_price", "freight_value"]].join(items, how="inner", rsuffix="_items")
    assert (m.items_price - m.price).abs().max() < 0.01
    assert (m.freight_value - m.freight_value_items).abs().max() < 0.01          # no double counting through payments/reviews joins


def test_one_latest_review_per_order(clean):
    r = clean["reviews"]
    assert r[r.is_latest_for_order].order_id.is_unique


def test_synthetic_data_is_labelled():
    for f in ["synthetic_product_costs.csv", "synthetic_inventory_weekly.csv"]:
        df = pd.read_csv(settings.synthetic_dir / f)
        assert df.is_synthetic.all(), f


def test_headline_kpis_consistent(om):
    k = json.loads((P / "headline_kpis.json").read_text())
    assert k["total_revenue"] == pytest.approx(k["product_revenue"] + k["freight_revenue"], abs=0.05)
    assert k["average_order_value"] == pytest.approx(k["total_revenue"] / k["total_orders"], abs=0.01)
    assert 0 < k["on_time_delivery_rate"] < 1 and 1 <= k["avg_review_score"] <= 5
