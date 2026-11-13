"""Unit tests for reusable cleaning helpers and per-dataset transforms (synthetic fixtures, no files)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.transformation import category_translation, customers, geolocation, order_items, orders, payments, products, reviews
from src.transformation.common import CleaningLog, date_key, normalize_category, normalize_city, normalize_zip, strip_accents
from src.transformation.marts import build_daily_kpis, headline_kpis


def test_strip_accents_and_city_normalisation():
    assert strip_accents("São Paulo") == "Sao Paulo"
    s = pd.Series(["  São  Paulo ", "RIO DE JANEIRO", None, "d'oeste"])
    out = normalize_city(s)
    assert out.tolist()[:2] == ["sao paulo", "rio de janeiro"]
    assert pd.isna(out.iloc[2]) and out.iloc[3] == "d oeste"


def test_zip_zero_padding():
    assert normalize_zip(pd.Series(["1037", "01037", " 22790"])).tolist() == ["01037", "01037", "22790"]


def test_category_normalisation():
    assert normalize_category(pd.Series([" Cama Mesa Banho "])).iloc[0] == "cama_mesa_banho"


def test_date_key():
    k = date_key(pd.Series(pd.to_datetime(["2017-11-24 10:00", None])))
    assert k.iloc[0] == 20171124 and pd.isna(k.iloc[1])


def _orders():
    ts = pd.Timestamp
    return pd.DataFrame({
        "order_id": ["a", "b", "c", "d"], "customer_id": ["c1", "c2", "c3", "c4"],
        "order_status": ["delivered", "delivered", "canceled", " Delivered"],
        "order_purchase_timestamp": [ts("2018-01-01 10:00")] * 4,
        "order_approved_at": [ts("2018-01-01 11:00"), ts("2017-12-31"), pd.NaT, ts("2018-01-01 12:00")],
        "order_delivered_carrier_date": [ts("2018-01-02")] * 4,
        "order_delivered_customer_date": [ts("2018-01-05"), ts("2018-01-20"), pd.NaT, ts("2018-01-10 08:00")],
        "order_estimated_delivery_date": [ts("2018-01-10"), ts("2018-01-15"), ts("2018-01-15"), ts("2018-01-10")],
    })


def test_orders_delivery_metrics_and_flags():
    log = CleaningLog()
    o = orders.transform(_orders(), log).set_index("order_id")
    assert o.loc["a", "delivery_days"] == pytest.approx(3.58, abs=0.01)
    assert bool(o.loc["a", "is_on_time"]) and not bool(o.loc["a", "is_late"])
    assert bool(o.loc["b", "is_late"]) and o.loc["b", "delivery_delay_days"] == 5
    assert bool(o.loc["d", "is_on_time"])                       # delivered on the estimated day = on time
    assert o.loc["d", "order_status"] == "delivered"            # status normalised
    assert not o.loc["c", "is_revenue_order"] and o.loc["c", "is_canceled"]
    assert pd.isna(o.loc["c", "is_on_time"])                    # not delivered -> unknown, not False
    assert pd.isna(o.loc["b", "order_approved_at"])             # approval before purchase nulled
    assert any(e["action"].startswith("null_order_approved_at") for e in log.entries)


def test_order_items_invalid_amounts_dropped():
    df = pd.DataFrame({"order_id": ["a", "a", "b"], "order_item_id": pd.array([1, 2, 1], dtype="Int64"),
                       "product_id": ["p"] * 3, "seller_id": ["s"] * 3, "shipping_limit_date": pd.NaT,
                       "price": [10.0, 0.0, 5.555], "freight_value": [1.0, 1.0, -1.0]})
    out = order_items.transform(df, CleaningLog())
    assert len(out) == 1 and out.line_total.iloc[0] == 11.0


def test_payments_installments_floor():
    df = pd.DataFrame({"order_id": ["a", "b"], "payment_sequential": pd.array([1, 1], dtype="Int64"),
                       "payment_type": ["credit_card", "BOLETO"], "payment_installments": pd.array([0, 3], dtype="Int64"),
                       "payment_value": [10.004, 5.0]})
    out = payments.transform(df, CleaningLog())
    assert out.payment_installments.min() == 1 and out.payment_type.iloc[1] == "boleto"


def test_reviews_latest_flag_and_sentiment():
    ts = pd.Timestamp
    df = pd.DataFrame({"review_id": ["r1", "r2", "r3"], "order_id": ["o1", "o1", "o2"], "review_score": pd.array([1, 5, 3], dtype="Int64"),
                       "review_comment_title": [None, None, None], "review_comment_message": ["bad", None, None],
                       "review_creation_date": [ts("2018-01-01")] * 3,
                       "review_answer_timestamp": [ts("2018-01-02"), ts("2018-01-05"), ts("2018-01-03")]})
    out = reviews.transform(df, CleaningLog()).set_index("review_id")
    assert out.loc["r2", "is_latest_for_order"] and not out.loc["r1", "is_latest_for_order"]
    assert out.loc["r1", "sentiment_band"] == "negative" and out.loc["r3", "sentiment_band"] == "neutral"


def test_products_translation_and_unknown():
    p = pd.DataFrame({"product_id": ["p1", "p2", "p3"], "product_category_name": ["beleza_saude", None, "pc_gamer"],
                      "product_name_lenght": [1.0, None, 2.0], "product_description_lenght": [1.0, None, 2.0],
                      "product_photos_qty": [1.0, None, 1.0], "product_weight_g": [0.0, 100.0, 50.0],
                      "product_length_cm": [10.0, 1.0, 1.0], "product_height_cm": [2.0, 1.0, 1.0], "product_width_cm": [3.0, 1.0, 1.0]})
    t = pd.DataFrame({"product_category_name": ["beleza_saude"], "product_category_name_english": ["health_beauty"]})
    out = products.transform(p, t, CleaningLog()).set_index("product_id")
    assert out.loc["p1", "product_category_name_english"] == "health_beauty"
    assert out.loc["p2", "product_category_name"] == "unknown"
    assert out.loc["p3", "product_category_name_english"] == "pc_gamer"
    assert pd.isna(out.loc["p1", "product_weight_g"])           # 0 g -> unknown
    assert out.loc["p1", "product_volume_cm3"] == 60
    assert "product_name_length" in out.columns                 # source typo fixed


def test_geolocation_aggregation_and_bounds():
    g = pd.DataFrame({"geolocation_zip_code_prefix": ["01001", "01001", "01001", "99999"],
                      "geolocation_lat": [-23.5, -23.6, -23.6, 40.0], "geolocation_lng": [-46.6, -46.7, -46.7, -3.0],
                      "geolocation_city": ["sao paulo", "São Paulo", "São Paulo", "madrid"], "geolocation_state": ["SP"] * 3 + ["XX"]})
    out = geolocation.transform(g, CleaningLog())
    assert list(out.zip_code_prefix) == ["01001"]                # out-of-Brazil point dropped
    assert out.city.iloc[0] == "sao paulo" and out.sample_points.iloc[0] == 2   # exact duplicate removed


def test_category_translation_appends_manual():
    t = pd.DataFrame({"product_category_name": ["beleza_saude"], "product_category_name_english": ["health_beauty"]})
    out = category_translation.transform(t, CleaningLog())
    assert {"pc_gamer", "unknown"} <= set(out.product_category_name)
    assert out.set_index("product_category_name").loc["beleza_saude", "category_display_name"] == "Health Beauty"


def test_customers_transform_keeps_keys():
    c = pd.DataFrame({"customer_id": ["a", "a"], "customer_unique_id": ["u", "u"], "customer_zip_code_prefix": ["1001", "1001"],
                      "customer_city": ["São Paulo", "São Paulo"], "customer_state": ["sp", "sp"]})
    out = customers.transform(c, CleaningLog())
    assert len(out) == 1 and out.customer_zip_code_prefix.iloc[0] == "01001" and out.customer_state.iloc[0] == "SP"


def test_headline_kpis_and_daily_gap_fill():
    om = pd.DataFrame({
        "order_id": ["a", "b", "c"], "customer_unique_id": ["u1", "u1", "u2"],
        "order_purchase_date": pd.to_datetime(["2018-01-01", "2018-01-03", "2018-01-03"]),
        "is_revenue_order": [True, True, False], "is_canceled": [False, False, True], "is_delivered": [True, True, False],
        "revenue": [100.0, 50.0, 0.0], "items_price": [90.0, 45.0, 10.0], "freight_value": [10.0, 5.0, 1.0],
        "payment_value": [100.0, 50.0, 11.0], "items_count": [1, 1, 1], "review_score": [5, 3, np.nan],
        "is_on_time": pd.array([True, False, pd.NA], dtype="boolean"), "is_late": pd.array([False, True, pd.NA], dtype="boolean"),
        "delivery_days": [3.0, 9.0, np.nan]})
    k = headline_kpis(om)
    assert k["total_revenue"] == 150 and k["total_orders"] == 2 and k["unique_customers"] == 1
    assert k["average_order_value"] == 75 and k["cancellation_rate"] == pytest.approx(1 / 3, abs=1e-6)
    assert k["on_time_delivery_rate"] == 0.5
    d = build_daily_kpis(om)
    assert len(d) == 3 and d.loc[d.date == "2018-01-02", "revenue"].iloc[0] == 0   # missing day filled with 0
