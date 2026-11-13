"""Pydantic request/response models for the NEXUS BI API."""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

REGIONS = Literal["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul", "Unknown"]
PAYMENT_TYPES = Literal["credit_card", "boleto", "voucher", "debit_card", "not_defined", "unknown"]
REVENUE_MODELS = Literal["best", "seasonal_naive", "sarima", "xgboost", "ensemble_mean"]
DEMAND_MODELS = Literal["best", "naive", "moving_avg_4w", "seasonal_naive_52w", "xgboost"]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    models_loaded: dict[str, bool]
    data_available: bool
    database_available: bool | None = None


class KPIResponse(BaseModel):
    period_start: date | None
    period_end: date | None
    filters: dict[str, str | None]
    currency: str = "BRL"
    total_revenue: float
    product_revenue: float
    freight_revenue: float
    total_orders: int
    unique_customers: int
    average_order_value: float
    revenue_growth_pct: float | None = Field(None, description="vs. the immediately preceding period of equal length; null when that period starts before 2017-01-01 (sparse 2016 data)")
    cancellation_rate: float
    on_time_delivery_rate: float | None
    avg_delivery_days: float | None
    avg_review_score: float | None
    repeat_customer_rate: float


class SegmentSummary(BaseModel):
    cluster: int
    cluster_name: str
    customers: int
    customer_share_pct: float
    revenue_share_pct: float
    recency_median_days: float
    frequency_mean: float
    monetary_median: float
    recommended_strategy: str


class CustomerSegmentResponse(BaseModel):
    selected_k: int
    silhouette: float
    clusters: list[SegmentSummary]
    rfm_segments: list[dict]
    customer: dict | None = None


class ChurnFeatures(BaseModel):
    """Behavioural features of ONE customer as of the scoring date (history only)."""

    model_config = ConfigDict(json_schema_extra={"example": {
        "recency_days": 45, "frequency": 1, "monetary": 189.9, "avg_order_value": 189.9, "tenure_days": 0,
        "avg_items": 1, "avg_review": 5, "last_review": 5, "pct_late": 0, "avg_delivery_days": 9.5,
        "avg_freight_ratio": 0.18, "max_installments": 3, "n_categories": 1, "days_since_first": 45,
        "customer_region": "Sudeste", "last_payment_type": "credit_card"}})

    customer_id: str | None = Field(None, max_length=64)
    recency_days: float = Field(..., ge=0, le=3650)
    frequency: int = Field(..., ge=1, le=1000)
    monetary: float = Field(..., ge=0)
    avg_order_value: float = Field(..., ge=0)
    tenure_days: float = Field(0, ge=0, le=3650)
    avg_items: float = Field(1, ge=0, le=100)
    avg_review: float | None = Field(None, ge=1, le=5)
    last_review: float | None = Field(None, ge=1, le=5)
    pct_late: float | None = Field(None, ge=0, le=1)
    avg_delivery_days: float | None = Field(None, ge=0, le=365)
    avg_freight_ratio: float | None = Field(None, ge=0, le=50)
    max_installments: float = Field(1, ge=1, le=36)
    n_categories: int = Field(1, ge=0, le=100)
    days_since_first: float = Field(..., ge=0, le=3650)
    customer_region: REGIONS = "Sudeste"
    last_payment_type: PAYMENT_TYPES = "credit_card"

    @field_validator("days_since_first")
    @classmethod
    def _first_after_recency(cls, v, info):
        r = info.data.get("recency_days")
        if r is not None and v < r:
            raise ValueError("days_since_first must be >= recency_days")
        return v


class ChurnRequest(BaseModel):
    customers: list[ChurnFeatures] = Field(..., min_length=1, max_length=1000)


class ChurnPrediction(BaseModel):
    customer_id: str | None
    churn_probability: float
    return_probability: float
    predicted_churn: bool
    risk_band: str


class ChurnResponse(BaseModel):
    model_name: str
    threshold: float
    horizon_days: int
    predictions: list[ChurnPrediction]
    disclaimer: str


class RevenueForecastRequest(BaseModel):
    horizon_days: int = Field(30, ge=1, le=30)
    model: REVENUE_MODELS = "best"
    include_history_days: int = Field(0, ge=0, le=365)


class ForecastPoint(BaseModel):
    date: date
    predicted: float | None = None
    lower_95: float | None = None
    upper_95: float | None = None
    actual: float | None = None


class RevenueForecastResponse(BaseModel):
    model: str
    best_model: str
    horizon_days: int
    currency: str = "BRL"
    trained_until: date
    total_predicted: float
    backtest_mae: float
    backtest_mape_pct: float
    forecast: list[ForecastPoint]
    history: list[ForecastPoint] = []


class DemandForecastRequest(BaseModel):
    category: str = Field(..., min_length=2, max_length=80)
    horizon_weeks: int = Field(4, ge=1, le=4)
    model: DEMAND_MODELS = "best"


class DemandForecastResponse(BaseModel):
    category: str
    model: str
    best_model: str
    horizon_weeks: int
    unit: str = "order lines (units) per week"
    backtest_wape_pct: float
    forecast: list[ForecastPoint]
    available_categories: list[str]


class AnomalyRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {
        "date": "2018-08-20", "revenue": 95000, "orders": 600, "late_rate": 0.05, "avg_review": 4.1, "cancel_rate": 0.004}})

    date: date
    revenue: float = Field(..., ge=0)
    orders: int = Field(..., ge=0)
    late_rate: float = Field(0.0, ge=0, le=1)
    avg_review: float = Field(4.1, ge=1, le=5)
    cancel_rate: float = Field(0.0, ge=0, le=1)
    recent_revenue: list[float] | None = Field(None, min_length=14, max_length=90,
                                               description="Optional trailing daily revenue (oldest->newest). Defaults to the last 28 training days.")
    recent_orders: list[float] | None = Field(None, min_length=14, max_length=90)


class AnomalyResponse(BaseModel):
    date: date
    is_anomaly: bool
    severity: str
    direction: str
    votes: int
    flags: dict[str, bool]
    iforest_score: float
    rolling_z: float
    global_z: float


class ErrorResponse(BaseModel):
    detail: str
