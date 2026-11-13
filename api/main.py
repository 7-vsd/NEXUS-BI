"""NEXUS BI – Prediction & KPI API (FastAPI).

Run:  uvicorn api.main:app --host 0.0.0.0 --port 8000
Docs: http://localhost:8000/docs (Swagger UI) · /redoc
"""
from __future__ import annotations

import time
from datetime import date

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api import services as svc
from api.schemas import (AnomalyRequest, AnomalyResponse, ChurnPrediction, ChurnRequest, ChurnResponse,
                         CustomerSegmentResponse, DemandForecastRequest, DemandForecastResponse, ErrorResponse,
                         ForecastPoint, HealthResponse, KPIResponse, RevenueForecastRequest, RevenueForecastResponse,
                         SegmentSummary)
from src import __version__
from src.logging.logger import get_logger

log = get_logger("api")

app = FastAPI(
    title="NEXUS BI API",
    version=__version__,
    description="Enterprise KPIs and predictive analytics for the Olist e-commerce dataset. "
                "All monetary values are in BRL. Forecasts come from models trained by `ml.train_all`.",
    responses={503: {"model": ErrorResponse, "description": "Model or data not available yet"}},
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])


@app.middleware("http")
async def access_log(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    log.info("%s %s -> %s (%.1f ms)", request.method, request.url.path, response.status_code,
             1000 * (time.perf_counter() - t0))
    return response


@app.exception_handler(svc.ResourceUnavailable)
async def unavailable_handler(_: Request, exc: svc.ResourceUnavailable):
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def unhandled_handler(_: Request, exc: Exception):
    log.exception("Unhandled API error")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# --------------------------------------------------------------------------- health
@app.get("/health", response_model=HealthResponse, tags=["System"])
def health(check_db: bool = Query(False, description="also probe PostgreSQL")):
    models = svc.models_status()
    try:
        svc.order_mart()
        data_ok = True
    except svc.ResourceUnavailable:
        data_ok = False
    db = None
    if check_db:
        from src.database.connection import is_database_available
        db = is_database_available()
    ok = data_ok and all(models.values())
    return HealthResponse(status="ok" if ok else "degraded", version=__version__, models_loaded=models,
                          data_available=data_ok, database_available=db)


# --------------------------------------------------------------------------- KPIs
@app.get("/api/business-kpis", response_model=KPIResponse, tags=["Business KPIs"])
def business_kpis(start_date: date | None = Query(None, description="inclusive, purchase date"),
                  end_date: date | None = Query(None, description="inclusive, purchase date"),
                  state: str | None = Query(None, min_length=2, max_length=2, description="customer state (UF), e.g. SP"),
                  category: str | None = Query(None, description="main order category (English)")):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be <= end_date")
    om = svc.filter_orders(start_date, end_date, state, category)
    if om.empty:
        raise HTTPException(status_code=404, detail="No orders match the given filters")
    k = svc.compute_kpis(om)
    growth = None
    s = pd.Timestamp(start_date) if start_date else om.order_purchase_timestamp.min().normalize()
    e = pd.Timestamp(end_date) if end_date else om.order_purchase_timestamp.max().normalize()
    span = (e - s).days + 1
    prev_start = s - pd.Timedelta(days=span)
    if prev_start >= svc.RELIABLE_START:       # only compare against a fully-captured prior period
        prev = svc.filter_orders(prev_start, s - pd.Timedelta(days=1), state, category)
        prev_rev = float(prev[prev.is_revenue_order].revenue.sum())
        if prev_rev > 0:
            growth = round(100 * (k["total_revenue"] / prev_rev - 1), 2)
    return KPIResponse(period_start=s.date(), period_end=e.date(),
                       filters={"state": state, "category": category}, revenue_growth_pct=growth, **k)


# --------------------------------------------------------------------------- segments
@app.get("/api/customer-segments", response_model=CustomerSegmentResponse, tags=["Customer Intelligence"])
def customer_segments(customer_unique_id: str | None = Query(None, min_length=32, max_length=32)):
    m = svc.metrics("customer_segmentation")
    clusters = [SegmentSummary(cluster=c["cluster"], cluster_name=c["cluster_name"], customers=c["customers"],
                               customer_share_pct=c["customer_share_pct"], revenue_share_pct=c["revenue_share_pct"],
                               recency_median_days=c["recency_median"], frequency_mean=c["frequency_mean"],
                               monetary_median=c["monetary_median"], recommended_strategy=c["recommended_strategy"])
                for c in m["clusters"]]
    customer = None
    if customer_unique_id:
        seg = svc.table("customer_segments")
        row = seg[seg.customer_unique_id == customer_unique_id]
        if row.empty:
            raise HTTPException(status_code=404, detail="customer_unique_id not found")
        customer = row.iloc[0][["customer_unique_id", "recency_days", "frequency", "monetary", "rfm_segment",
                                "cluster", "cluster_name", "recommended_strategy"]].to_dict()
        customer = {k: (v.item() if hasattr(v, "item") else v) for k, v in customer.items()}
    return CustomerSegmentResponse(selected_k=m["selected_k"], silhouette=round(m["silhouette_selected"], 4),
                                   clusters=clusters, rfm_segments=m["rfm_segments"], customer=customer)


# --------------------------------------------------------------------------- churn
@app.post("/api/predict-churn", response_model=ChurnResponse, tags=["Predictive Analytics"])
def predict_churn(req: ChurnRequest):
    rows = [c.model_dump() for c in req.customers]
    bundle, proba = svc.predict_churn(rows)
    thr = float(bundle["threshold"])
    preds = [ChurnPrediction(customer_id=r.get("customer_id"), churn_probability=round(float(p), 4),
                             return_probability=round(1 - float(p), 4), predicted_churn=bool(p >= thr),
                             risk_band=svc.risk_band(float(p))) for r, p in zip(rows, proba)]
    return ChurnResponse(model_name=bundle["model_name"], threshold=thr,
                         horizon_days=svc.metrics("churn_prediction")["horizon_days"], predictions=preds,
                         disclaimer="Modest discrimination (see MODEL_EVALUATION_REPORT). Use for ranking/prioritisation, "
                                    "not individual decisions.")


# --------------------------------------------------------------------------- revenue forecast
@app.post("/api/forecast-revenue", response_model=RevenueForecastResponse, tags=["Predictive Analytics"])
def forecast_revenue(req: RevenueForecastRequest):
    m = svc.metrics("revenue_forecasting")
    best = m["best_model_by_backtest_mae"]
    name = best if req.model == "best" else req.model
    fc = svc.table("revenue_forecast")
    fc = fc[fc.model == name].sort_values("date").head(req.horizon_days)
    if fc.empty:
        raise HTTPException(status_code=404, detail=f"No forecast stored for model '{name}'")
    hist = []
    if req.include_history_days:
        s = svc.table("revenue_series").revenue.tail(req.include_history_days)
        hist = [ForecastPoint(date=d.date(), actual=round(float(v), 2)) for d, v in s.items()]
    bt = m["backtest"][name]["overall"]
    return RevenueForecastResponse(
        model=name, best_model=best, horizon_days=req.horizon_days, trained_until=date.fromisoformat(m["series_end"]),
        total_predicted=round(float(fc.predicted.sum()), 2), backtest_mae=round(bt["mae"], 2),
        backtest_mape_pct=round(bt["mape_pct"], 2),
        forecast=[ForecastPoint(date=r.date.date(), predicted=round(r.predicted, 2), lower_95=round(r.lower_95, 2),
                                upper_95=round(r.upper_95, 2)) for r in fc.itertuples()],
        history=hist)


# --------------------------------------------------------------------------- demand forecast
@app.post("/api/forecast-demand", response_model=DemandForecastResponse, tags=["Predictive Analytics"])
def forecast_demand(req: DemandForecastRequest):
    m = svc.metrics("demand_forecasting")
    cats = m["categories"]
    cat = req.category.strip().lower().replace(" ", "_")
    if cat not in cats:
        raise HTTPException(status_code=404, detail=f"Category '{req.category}' not forecast. Available: {cats}")
    best = m["best_model_by_wape"]
    name = best if req.model == "best" else req.model
    fc = svc.table("demand_forecast")
    fc = fc[(fc.category == cat) & (fc.model == name)].sort_values("week").head(req.horizon_weeks)
    if fc.empty:
        raise HTTPException(status_code=404, detail=f"No forecast stored for model '{name}'")
    return DemandForecastResponse(
        category=cat, model=name, best_model=best, horizon_weeks=req.horizon_weeks,
        backtest_wape_pct=round(m["backtest_overall"][name]["wape_pct"], 2), available_categories=cats,
        forecast=[ForecastPoint(date=r.week.date(), predicted=round(r.predicted, 1), lower_95=round(r.lower_95, 1),
                                upper_95=round(r.upper_95, 1)) for r in fc.itertuples()])


# --------------------------------------------------------------------------- anomaly
@app.post("/api/detect-anomaly", response_model=AnomalyResponse, tags=["Predictive Analytics"])
def detect_anomaly(req: AnomalyRequest):
    from ml.anomaly_detection.anomaly import score_observation

    if req.orders == 0 and req.revenue > 0:
        raise HTTPException(status_code=422, detail="revenue > 0 requires orders > 0")
    res = score_observation(req.model_dump(), svc.model("anomaly_detection", "anomaly_model"))
    return AnomalyResponse(date=req.date, **res)


# --------------------------------------------------------------------------- read-only helpers used by Streamlit
@app.get("/api/anomalies", tags=["Predictive Analytics"])
def list_anomalies(only_flagged: bool = True):
    a = svc.table("anomalies")
    if only_flagged:
        a = a[a.is_anomaly]
    a = a.assign(date=a.date.dt.date.astype(str))
    return a.where(pd.notna(a), None).to_dict(orient="records")


@app.get("/api/model-metrics/{module}", tags=["System"])
def model_metrics(module: str):
    allowed = {"customer_segmentation", "churn_prediction", "revenue_forecasting", "demand_forecasting", "anomaly_detection"}
    if module not in allowed:
        raise HTTPException(status_code=404, detail=f"Unknown module. Use one of {sorted(allowed)}")
    return svc.metrics(module)
