# API Documentation – NEXUS BI (FastAPI)

* Start: `uvicorn api.main:app --host 0.0.0.0 --port 8000` (Windows: `.\scripts\nexus.ps1 api`)
* Interactive docs: **http://localhost:8000/docs** (Swagger UI) · http://localhost:8000/redoc · OpenAPI JSON: `docs/architecture/openapi.json`
* Data source: processed marts + trained artifacts (no database needed). `GET /health?check_db=true` also probes PostgreSQL.
* All money values are BRL.

## Error model

| Status | When |
|---|---|
| 200 | Success |
| 404 | No data for the filters / unknown customer / unknown category / unknown model |
| 422 | Pydantic validation failure (types, ranges, enums, cross-field rules) |
| 503 | Model or dataset not produced yet (`detail` says which command to run) |
| 500 | Unhandled error (logged with stack trace; generic message returned) |

## Examples

```bash
curl "http://localhost:8000/api/business-kpis?start_date=2018-01-01&end_date=2018-03-31&state=SP"

curl -X POST http://localhost:8000/api/predict-churn -H "Content-Type: application/json" -d '{
  "customers": [{"customer_id": "demo-1", "recency_days": 45, "frequency": 1, "monetary": 189.9,
                 "avg_order_value": 189.9, "days_since_first": 45, "avg_review": 5, "pct_late": 0,
                 "max_installments": 3, "customer_region": "Sudeste", "last_payment_type": "credit_card"}]}'

curl -X POST http://localhost:8000/api/forecast-revenue -H "Content-Type: application/json" \
     -d '{"horizon_days": 30, "model": "best", "include_history_days": 60}'

curl -X POST http://localhost:8000/api/forecast-demand -H "Content-Type: application/json" \
     -d '{"category": "health_beauty", "horizon_weeks": 4}'

curl -X POST http://localhost:8000/api/detect-anomaly -H "Content-Type: application/json" \
     -d '{"date": "2018-08-20", "revenue": 400000, "orders": 2600, "late_rate": 0.06, "avg_review": 4.1}'
```

PowerShell: `Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/forecast-revenue -ContentType 'application/json' -Body '{"horizon_days":7}'`

## Endpoint notes
* **GET /api/business-kpis** – optional `start_date`, `end_date` (inclusive), `state` (UF), `category`.
  `revenue_growth_pct` compares with the preceding period of equal length and is `null` if that period starts before 2017.
* **GET /api/customer-segments** – cluster summaries, RFM segments; `customer_unique_id` (32 chars) returns one customer.
* **POST /api/predict-churn** – 1–1000 customers per call; returns churn and return probability, decision at the
  validation-tuned threshold and a risk band. Carries a disclaimer about modest discrimination.
* **POST /api/forecast-revenue** – `horizon_days` 1–30, `model` ∈ best | ensemble_mean | seasonal_naive | sarima | xgboost.
* **POST /api/forecast-demand** – `category` (case/space-insensitive) of the 10 forecast categories, `horizon_weeks` 1–4.
* **POST /api/detect-anomaly** – scores one day with the saved detectors; optional `recent_revenue`/`recent_orders`
  (14–90 values) to supply your own trailing context.
* Helpers for the app: `GET /api/anomalies`, `GET /api/model-metrics/{module}`.

Tests: `tests/api/test_api.py` (26 tests – endpoints, invalid inputs, 404/422/503 paths).

## Endpoint reference
<!-- ENDPOINTS -->

_Generated from the live OpenAPI schema (`docs/architecture/openapi.json`)._

| Method | Path | Tag | Summary | Status codes |
|---|---|---|---|---|
| GET | `/health` | System | Health | 200, 422, 503 |
| GET | `/api/business-kpis` | Business KPIs | Business Kpis | 200, 422, 503 |
| GET | `/api/customer-segments` | Customer Intelligence | Customer Segments | 200, 422, 503 |
| POST | `/api/predict-churn` | Predictive Analytics | Predict Churn | 200, 422, 503 |
| POST | `/api/forecast-revenue` | Predictive Analytics | Forecast Revenue | 200, 422, 503 |
| POST | `/api/forecast-demand` | Predictive Analytics | Forecast Demand | 200, 422, 503 |
| POST | `/api/detect-anomaly` | Predictive Analytics | Detect Anomaly | 200, 422, 503 |
| GET | `/api/anomalies` | Predictive Analytics | List Anomalies | 200, 422, 503 |
| GET | `/api/model-metrics/{module}` | System | Model Metrics | 200, 422, 503 |
