"""Unit tests for discovery, schema validation, type casting and data-quality rules."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.ingestion.discovery import discover_sources
from src.ingestion.reader import SchemaValidationError, cast_frame, ingest, validate_columns
from src.validation.quality import CheckResult, check_duplicates, check_nulls
from src.validation.schemas import SCHEMAS


def _write(tmp: Path, name: str, text: str) -> Path:
    p = tmp / name
    p.write_text(text, encoding="utf-8")
    return p


def test_discovery_matches_all_and_rejects_missing(tmp_path):
    for n in ["olist_customers_dataset.csv", "olist_orders_dataset.csv", "olist_order_items_dataset.csv",
              "olist_order_payments_dataset.csv", "olist_order_reviews_dataset.csv", "olist_products_dataset.csv",
              "olist_sellers_dataset.csv", "olist_geolocation_dataset.csv", "product_category_name_translation.csv"]:
        _write(tmp_path, n, "x\n")
    found = discover_sources(tmp_path, with_checksum=False)
    assert set(found) == set(SCHEMAS)
    assert found["orders"].path.name == "olist_orders_dataset.csv"        # not order_items/payments/reviews
    (tmp_path / "olist_sellers_dataset.csv").unlink()
    with pytest.raises(FileNotFoundError, match="sellers"):
        discover_sources(tmp_path, with_checksum=False)


def test_schema_validation_missing_column():
    with pytest.raises(SchemaValidationError):
        validate_columns(pd.DataFrame({"seller_id": ["a"]}), SCHEMAS["sellers"])


def test_cast_counts_failures_and_keeps_zip_as_text(tmp_path):
    p = _write(tmp_path, "s.csv", "seller_id,seller_zip_code_prefix,seller_city,seller_state,extra\n"
                                  "a,01037,sao paulo,SP,1\nb,22790,rio,RJ,2\n")
    r = ingest("sellers", p)
    assert r.frame.seller_zip_code_prefix.tolist() == ["01037", "22790"]   # leading zero preserved
    assert r.extra_columns == ["extra"]
    df = pd.DataFrame({"order_id": ["a"], "payment_sequential": ["x"], "payment_type": ["boleto"],
                       "payment_installments": ["1"], "payment_value": ["9.5"]})
    typed, fails = cast_frame(df, SCHEMAS["payments"])
    assert fails == {"payment_sequential": 1} and typed.payment_value.iloc[0] == 9.5


def test_bom_header_is_handled(tmp_path):
    p = _write(tmp_path, "t.csv", "﻿product_category_name,product_category_name_english\nbeleza_saude,health_beauty\n")
    assert ingest("category_translation", p).rows == 1


def test_quality_rules():
    df = pd.DataFrame({"seller_id": ["a", "a", None], "seller_zip_code_prefix": ["01001"] * 3,
                       "seller_city": ["x", "x", "y"], "seller_state": ["SP"] * 3})
    dup = {c.check: c for c in check_duplicates("sellers", df)}
    assert dup["duplicate_primary_key"].failed_rows == 1 and dup["duplicate_primary_key"].status == "FAIL"
    nulls = {c.column: c for c in check_nulls("sellers", df)}
    assert nulls["seller_id"].status == "FAIL" and nulls["seller_city"].status == "PASS"


def test_check_result_status_mapping():
    assert CheckResult("d", "c", "x", 0, 10, "ERROR").status == "PASS"
    assert CheckResult("d", "c", "x", 1, 10, "ERROR").status == "FAIL"
    assert CheckResult("d", "c", "x", 1, 10, "WARNING").status == "WARN"
    assert CheckResult("d", "c", "x", 1, 10, "INFO").status == "NOTE"
    assert CheckResult("d", "c", "x", 1, 4, "INFO").failed_pct == 25.0
