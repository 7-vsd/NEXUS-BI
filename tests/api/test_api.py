"""API endpoint, validation and error-handling tests (FastAPI TestClient)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api import services as svc
from api.main import app

client = TestClient(app)
pytestmark = pytest.mark.skipif(not all(svc.models_status().values()), reason="ML artifacts not trained")

CHURN_EXAMPLE = {"recency_days": 45, "frequency": 1, "monetary": 189.9, "avg_order_value": 189.9, "tenure_days": 0,
                 "avg_items": 1, "avg_review": 5, "last_review": 5, "pct_late": 0, "avg_delivery_days": 9.5,
                 "avg_freight_ratio": 0.18, "max_installments": 3, "n_categories": 1, "days_since_first": 45,
                 "customer_region": "Sudeste", "last_payment_type": "credit_card"}


def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["data_available"] and all(body["models_loaded"].values())


def test_openapi_documents_all_required_endpoints():
    paths = client.get("/openapi.json").json()["paths"]
    for p in ["/health", "/api/business-kpis", "/api/customer-segments", "/api/predict-churn",
              "/api/forecast-revenue", "/api/forecast-demand", "/api/detect-anomaly"]:
        assert p in paths


def test_business_kpis_matches_reconciled_headline():
    import json
    from src.config.settings import settings
    head = json.loads((settings.processed_dir / "headline_kpis.json").read_text())
    k = client.get("/api/business-kpis").json()
    assert k["total_revenue"] == pytest.approx(head["total_revenue"], abs=0.01)
    assert k["total_orders"] == head["total_orders"]
    assert k["unique_customers"] == head["unique_customers"]
    assert k["currency"] == "BRL"


def test_business_kpis_filters_and_growth():
    r = client.get("/api/business-kpis", params={"start_date": "2018-01-01", "end_date": "2018-03-31", "state": "SP"})
    assert r.status_code == 200
    body = r.json()
    assert body["filters"]["state"] == "SP" and body["total_orders"] > 0
    assert body["revenue_growth_pct"] is not None


def test_business_kpis_invalid_range_422():
    r = client.get("/api/business-kpis", params={"start_date": "2018-05-01", "end_date": "2018-01-01"})
    assert r.status_code == 422


def test_business_kpis_no_match_404():
    r = client.get("/api/business-kpis", params={"state": "ZZ"})
    assert r.status_code == 404


def test_customer_segments_summary_and_lookup():
    body = client.get("/api/customer-segments").json()
    assert body["selected_k"] == len(body["clusters"]) >= 3
    assert abs(sum(c["customer_share_pct"] for c in body["clusters"]) - 100) < 0.1
    cid = svc.table("customer_segments").customer_unique_id.iloc[0]
    one = client.get("/api/customer-segments", params={"customer_unique_id": cid}).json()
    assert one["customer"]["customer_unique_id"] == cid


def test_customer_segments_unknown_customer_404():
    r = client.get("/api/customer-segments", params={"customer_unique_id": "0" * 32})
    assert r.status_code == 404


def test_predict_churn_valid():
    r = client.post("/api/predict-churn", json={"customers": [CHURN_EXAMPLE, {**CHURN_EXAMPLE, "recency_days": 300,
                                                                               "days_since_first": 300}]})
    assert r.status_code == 200
    preds = r.json()["predictions"]
    assert len(preds) == 2
    for p in preds:
        assert 0 <= p["churn_probability"] <= 1
        assert p["return_probability"] == pytest.approx(1 - p["churn_probability"], abs=1e-4)


@pytest.mark.parametrize("bad", [
    {"recency_days": -1},                       # negative
    {"frequency": 0},                           # below minimum
    {"customer_region": "Mars"},                # not in enum
    {"avg_review": 7},                          # out of range
    {"days_since_first": 10, "recency_days": 45},  # inconsistent
])
def test_predict_churn_invalid_inputs_422(bad):
    r = client.post("/api/predict-churn", json={"customers": [{**CHURN_EXAMPLE, **bad}]})
    assert r.status_code == 422


def test_predict_churn_empty_batch_422():
    assert client.post("/api/predict-churn", json={"customers": []}).status_code == 422


def test_forecast_revenue_default_best():
    body = client.post("/api/forecast-revenue", json={"horizon_days": 30}).json()
    assert body["model"] == body["best_model"]
    assert len(body["forecast"]) == 30
    for p in body["forecast"]:
        assert p["lower_95"] <= p["predicted"] <= p["upper_95"]


def test_forecast_revenue_specific_model_and_history():
    body = client.post("/api/forecast-revenue", json={"horizon_days": 7, "model": "sarima",
                                                      "include_history_days": 14}).json()
    assert body["model"] == "sarima" and len(body["forecast"]) == 7 and len(body["history"]) == 14


@pytest.mark.parametrize("payload", [{"horizon_days": 0}, {"horizon_days": 31}, {"model": "prophet"}])
def test_forecast_revenue_invalid_422(payload):
    assert client.post("/api/forecast-revenue", json=payload).status_code == 422


def test_forecast_demand_valid_and_case_insensitive():
    cat = svc.metrics("demand_forecasting")["categories"][0]
    body = client.post("/api/forecast-demand", json={"category": cat.replace("_", " ").upper(), "horizon_weeks": 3}).json()
    assert body["category"] == cat and len(body["forecast"]) == 3


def test_forecast_demand_unknown_category_404():
    r = client.post("/api/forecast-demand", json={"category": "spaceships"})
    assert r.status_code == 404 and "Available" in r.json()["detail"]


def test_detect_anomaly_normal_and_extreme():
    normal = client.post("/api/detect-anomaly", json={"date": "2018-08-20", "revenue": 40000, "orders": 260,
                                                      "late_rate": 0.06, "avg_review": 4.1, "cancel_rate": 0.003}).json()
    extreme = client.post("/api/detect-anomaly", json={"date": "2018-08-20", "revenue": 400000, "orders": 2600,
                                                       "late_rate": 0.06, "avg_review": 4.1, "cancel_rate": 0.003}).json()
    assert normal["is_anomaly"] is False
    assert extreme["is_anomaly"] is True and extreme["direction"] == "spike"


def test_detect_anomaly_invalid_422():
    assert client.post("/api/detect-anomaly", json={"date": "2018-08-20", "revenue": 100, "orders": 0}).status_code == 422
    assert client.post("/api/detect-anomaly", json={"date": "not-a-date", "revenue": 1, "orders": 1}).status_code == 422
    assert client.post("/api/detect-anomaly", json={"date": "2018-08-20", "revenue": -5, "orders": 1}).status_code == 422


def test_model_metrics_unknown_module_404():
    assert client.get("/api/model-metrics/foo").status_code == 404


def test_missing_artifact_returns_503(monkeypatch):
    def boom(*a, **k):
        raise svc.ResourceUnavailable("model missing")
    monkeypatch.setattr(svc, "predict_churn", boom)
    r = client.post("/api/predict-churn", json={"customers": [CHURN_EXAMPLE]})
    assert r.status_code == 503 and "missing" in r.json()["detail"]
