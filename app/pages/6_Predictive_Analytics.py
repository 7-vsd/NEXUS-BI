"""Predictive Analytics – revenue & demand forecasts, churn scoring (via the API)."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.components import api_client
from app.components.data import load, pretty
from app.components.theme import PALETTE
from app.components.ui import brl, chart, insight, kpi_row, note, page_header, section

page_header("Predictive Analytics", "30-day revenue forecast, weekly category demand and customer churn risk.")

tab1, tab2, tab3 = st.tabs(["Revenue forecast", "Demand forecast", "Churn risk"])

with tab1:
    model = st.selectbox("Model", ["best", "ensemble_mean", "seasonal_naive", "sarima", "xgboost"], index=0)
    horizon = st.slider("Horizon (days)", 7, 30, 30)
    try:
        with st.spinner("Requesting forecast from API…"):
            fc = api_client.cached_post("/api/forecast-revenue", (("horizon_days", horizon), ("model", model),
                                                                  ("include_history_days", 120)))
        f = pd.DataFrame(fc["forecast"]); h = pd.DataFrame(fc["history"])
        kpi_row([dict(label=f"Forecast revenue – next {horizon} days", value=brl(fc["total_predicted"]), accent=True),
                 dict(label="Model", value=fc["model"], delta_label=f"best by backtest: {fc['best_model']}"),
                 dict(label="Backtest MAE (daily)", value=brl(fc["backtest_mae"])),
                 dict(label="Backtest MAPE", value=f"{fc['backtest_mape_pct']:.1f}%")])
        fig = go.Figure()
        fig.add_scatter(x=h.date, y=h.actual, name="Actual", line=dict(color=PALETTE["blue"], width=1.4))
        fig.add_scatter(x=f.date, y=f.upper_95, line=dict(width=0), showlegend=False, hoverinfo="skip")
        fig.add_scatter(x=f.date, y=f.lower_95, fill="tonexty", fillcolor="rgba(20,184,166,.18)", line=dict(width=0),
                        name="95% interval")
        fig.add_scatter(x=f.date, y=f.predicted, name="Forecast", line=dict(color=PALETTE["teal"], width=2.6))
        fig.update_layout(yaxis_title="Daily revenue (BRL)")
        chart(fig, 420)
        st.caption(f"Trained on data until {fc['trained_until']} (last reliable capture day).")
        bt = load("revenue_backtest")
        section("Actual vs predicted – rolling-origin backtest (4 × 30 days)")
        fig = px.line(bt[bt.model.isin(["seasonal_naive", "sarima", "xgboost", "ensemble_mean"])], x="date",
                      y="predicted", color="model", labels={"predicted": "Revenue (BRL)", "date": ""})
        act = bt.drop_duplicates("date")
        fig.add_scatter(x=act.date, y=act.actual, name="actual", line=dict(color="#E6EDF5" if st.session_state.get(
            "theme_mode", "dark") == "dark" else "#13294B", width=2))
        chart(fig, 360)
    except api_client.ApiError as exc:
        note(f"⚠️ {exc}")

with tab2:
    try:
        meta = api_client.cached_get("/api/model-metrics/demand_forecasting")
        c1, c2, c3 = st.columns([2, 1, 1])
        cat = c1.selectbox("Category", meta["categories"], format_func=pretty)
        dmodel = c2.selectbox("Model ", ["best", "naive", "moving_avg_4w", "seasonal_naive_52w", "xgboost"])
        weeks = c3.slider("Weeks", 1, 4, 4)
        dfc = api_client.cached_post("/api/forecast-demand", (("category", cat), ("horizon_weeks", weeks), ("model", dmodel)))
        hist = load("demand_panel")
        hist = hist[hist.category == cat].tail(40)
        f = pd.DataFrame(dfc["forecast"])
        fig = go.Figure()
        fig.add_scatter(x=hist.week, y=hist.units, name="Actual units", line=dict(color=PALETTE["blue"]))
        fig.add_scatter(x=f.date, y=f.upper_95, line=dict(width=0), showlegend=False, hoverinfo="skip")
        fig.add_scatter(x=f.date, y=f.lower_95, fill="tonexty", fillcolor="rgba(20,184,166,.18)", line=dict(width=0),
                        name="95% interval")
        fig.add_scatter(x=f.date, y=f.predicted, name="Forecast", mode="lines+markers", line=dict(color=PALETTE["teal"], width=2.5))
        fig.update_layout(yaxis_title="Units per week", title=f"{pretty(cat)} – weekly demand")
        chart(fig, 400)
        st.caption(f"Model: {dfc['model']} (best by backtest WAPE: {dfc['best_model']}) · backtest WAPE {dfc['backtest_wape_pct']:.1f}%")
        section("Model comparison (backtest, all categories)")
        comp = pd.DataFrame(meta["backtest_overall"]).T[["wape_pct", "mae", "rmse"]].sort_values("wape_pct")
        st.dataframe(comp.style.format("{:.1f}"), width="stretch")
        insight("Simple baselines beat XGBoost at a 4-week horizon on ~85 weeks of history – the naive forecast "
                "is the recommended default until more seasonal cycles are available.")
    except api_client.ApiError as exc:
        note(f"⚠️ {exc}")

with tab3:
    scores = load("churn_scores")
    kpi_row([dict(label="Customers scored", value=f"{len(scores):,}", accent=True),
             dict(label="Mean churn probability", value=f"{scores.churn_probability.mean():.1%}"),
             dict(label="Very-high risk", value=f"{(scores.risk_band == 'Very High').mean():.1%}")])
    c1, c2 = st.columns(2)
    with c1:
        section("Churn probability distribution")
        fig = px.histogram(scores, x="churn_probability", nbins=50, labels={"churn_probability": "P(no purchase in 180 days)"})
        fig.update_traces(marker_color=PALETTE["blue"]); fig.update_layout(yaxis_title="Customers")
        chart(fig, 320)
    with c2:
        section("Top 20 customers most likely to return")
        st.dataframe(scores.nsmallest(20, "churn_probability")[["customer_unique_id", "churn_probability", "frequency",
                                                                  "monetary", "recency_days"]],
                     hide_index=True, width="stretch", height=320)
    note("The churn model has modest discrimination (test ROC-AUC ≈ 0.58; ~2× lift in the top decile). "
         "Use it to prioritise retention budgets, not for individual decisions.")
    section("What-if: score a customer profile (POST /api/predict-churn)")
    with st.form("churn_form"):
        a, b, c, d = st.columns(4)
        rec = a.number_input("Days since last purchase", 0, 1000, 60)
        freq = b.number_input("Orders", 1, 50, 1)
        mon = c.number_input("Lifetime revenue (BRL)", 0.0, 50000.0, 150.0)
        rev_ = d.slider("Avg review", 1.0, 5.0, 4.5)
        e, g, h_, i = st.columns(4)
        late = e.slider("Share of late deliveries", 0.0, 1.0, 0.0)
        inst = g.number_input("Max installments", 1, 24, 2)
        region = h_.selectbox("Region", ["Sudeste", "Sul", "Nordeste", "Centro-Oeste", "Norte"])
        pay = i.selectbox("Payment", ["credit_card", "boleto", "voucher", "debit_card"])
        ok = st.form_submit_button("Score customer", type="primary")
    if ok:
        payload = {"customers": [{"recency_days": rec, "frequency": int(freq), "monetary": mon,
                                  "avg_order_value": mon / freq, "tenure_days": 0 if freq == 1 else max(rec, 30),
                                  "avg_items": 1, "avg_review": rev_, "last_review": rev_, "pct_late": late,
                                  "avg_delivery_days": 12, "avg_freight_ratio": 0.2, "max_installments": inst,
                                  "n_categories": 1, "days_since_first": rec if freq == 1 else rec + 60,
                                  "customer_region": region, "last_payment_type": pay}]}
        try:
            res = api_client.post("/api/predict-churn", payload)
            p = res["predictions"][0]
            st.success(f"Churn probability **{p['churn_probability']:.1%}** · return probability "
                       f"**{p['return_probability']:.2%}** · risk band **{p['risk_band']}** (model: {res['model_name']})")
        except api_client.ApiError as exc:
            st.error(str(exc))
