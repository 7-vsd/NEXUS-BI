"""Executive Overview – CEO / CFO command centre."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from api.services import compute_kpis
from app.components import api_client
from app.components.data import REGION_OF, filtered_items, filtered_orders, filters, pretty
from app.components.theme import PALETTE
from app.components.ui import brl, chart, empty_state, insight, kpi_row, note, num, page_header, pct, section

page_header("Executive Overview", "Headline performance, growth and where revenue comes from.")

f = filters()
om = filtered_orders()
if om.empty:
    empty_state()
    st.stop()

# KPI source: API when the filter combination is expressible as API parameters, else local marts (same logic).
simple = not f.get("regions") and len(f.get("states") or []) <= 1 and len(f.get("categories") or []) <= 1
k, source = None, "local marts"
if simple:
    try:
        params = (("start_date", str(f["start"])), ("end_date", str(f["end"])),
                  ("state", (f.get("states") or [None])[0]), ("category", (f.get("categories") or [None])[0]))
        k = api_client.cached_get("/api/business-kpis", tuple((a, b) for a, b in params if b))
        source = "FastAPI /api/business-kpis"
    except api_client.ApiError as exc:
        note(f"⚠️ {exc} — KPI cards computed locally with identical business rules.")
if k is None:
    k = compute_kpis(om)
    span = (pd.Timestamp(f["end"]) - pd.Timestamp(f["start"])).days + 1
    from app.components.data import load
    allom = load("order_mart")
    prev = allom[(allom.order_purchase_timestamp >= pd.Timestamp(f["start"]) - pd.Timedelta(days=span)) &
                 (allom.order_purchase_timestamp < pd.Timestamp(f["start"]))]
    if f.get("states"):
        prev = prev[prev.customer_state.isin(f["states"])]
    if f.get("regions"):
        prev = prev[prev.customer_state.map(REGION_OF).isin(f["regions"])]
    if f.get("categories"):
        prev = prev[prev.main_category.isin(f["categories"])]
    pr = prev[prev.is_revenue_order].revenue.sum()
    reliable = pd.Timestamp(f["start"]) - pd.Timedelta(days=span) >= pd.Timestamp("2017-01-01")
    k["revenue_growth_pct"] = round(100 * (k["total_revenue"] / pr - 1), 2) if pr > 0 and reliable else None

g = k.get("revenue_growth_pct")
kpi_row([
    dict(label="Total revenue", value=brl(k["total_revenue"]), delta=g,
         delta_label="vs prior period" if g is not None else "growth n/a: prior period before 2017", accent=True),
    dict(label="Orders", value=num(k["total_orders"])),
    dict(label="Unique customers", value=num(k["unique_customers"])),
    dict(label="Average order value", value=brl(k["average_order_value"], 2)),
    dict(label="On-time delivery", value=pct(k["on_time_delivery_rate"])),
    dict(label="Avg review score", value=f"{k['avg_review_score']:.2f} / 5" if k["avg_review_score"] else "–"),
])
st.caption(f"KPI source: {source} · Revenue = item price + freight for orders not canceled/unavailable (BRL).")

c1, c2 = st.columns([1.6, 1])
with c1:
    section("Monthly revenue trend")
    rev = om[om.is_revenue_order]
    m = rev.groupby("purchase_month").agg(revenue=("revenue", "sum"), orders=("order_id", "nunique")).reset_index()
    fig = go.Figure()
    fig.add_bar(x=m.purchase_month, y=m.revenue, name="Revenue (BRL)", marker_color=PALETTE["blue"])
    fig.add_scatter(x=m.purchase_month, y=m.orders, name="Orders", yaxis="y2", mode="lines+markers",
                    line=dict(color=PALETTE["teal"], width=2))
    fig.update_layout(yaxis=dict(title="Revenue (BRL)"), yaxis2=dict(title="Orders", overlaying="y", side="right",
                                                                     showgrid=False), xaxis_title="Month")
    chart(fig, 360)
with c2:
    section("Revenue by region")
    rr = rev.assign(region=rev.customer_state.map(REGION_OF)).groupby("region").revenue.sum().sort_values()
    fig = px.bar(rr, orientation="h", labels={"value": "Revenue (BRL)", "region": ""})
    fig.update_traces(marker_color=PALETTE["teal"]); fig.update_layout(showlegend=False)
    chart(fig, 360)

c3, c4 = st.columns(2)
with c3:
    section("Top 10 categories by item revenue")
    it = filtered_items()
    it = it[it.is_revenue_order]
    cat = it.groupby("product_category_name_english").price.sum().nlargest(10).sort_values()
    fig = px.bar(x=cat.values, y=[pretty(c) for c in cat.index], orientation="h",
                 labels={"x": "Item revenue (BRL)", "y": ""})
    fig.update_traces(marker_color=PALETTE["blue"])
    chart(fig, 380)
with c4:
    section("Top 10 states")
    st_rev = rev.groupby("customer_state").agg(revenue=("revenue", "sum"), orders=("order_id", "nunique"),
                                               customers=("customer_unique_id", "nunique")).nlargest(10, "revenue")
    st_rev["share"] = st_rev.revenue / rev.revenue.sum()
    st_rev["aov"] = st_rev.revenue / st_rev.orders
    st.dataframe(st_rev.reset_index().rename(columns={"customer_state": "State"}), hide_index=True,
                 width="stretch", height=380,
                 column_config={"revenue": st.column_config.NumberColumn("Revenue (BRL)", format="localized"),
                                "share": st.column_config.ProgressColumn("Share", format="percent", min_value=0, max_value=1),
                                "aov": st.column_config.NumberColumn("AOV", format="R$ %.2f"),
                                "orders": "Orders", "customers": "Customers"})

section("Business KPI scorecard")
sc = pd.DataFrame([
    ["Revenue growth vs prior period", f"{g:+.1f}%" if g is not None else "–", "> 0%",
     "🟢" if (g or 0) > 0 else "🔴"],
    ["On-time delivery rate", pct(k["on_time_delivery_rate"]), "≥ 90%", "🟢" if (k["on_time_delivery_rate"] or 0) >= .9 else "🔴"],
    ["Cancellation rate", pct(k["cancellation_rate"], 2), "≤ 1%", "🟢" if k["cancellation_rate"] <= .01 else "🔴"],
    ["Average review score", f"{k['avg_review_score']:.2f}" if k["avg_review_score"] else "–", "≥ 4.0",
     "🟢" if (k["avg_review_score"] or 0) >= 4 else "🔴"],
    ["Repeat-customer rate", pct(k["repeat_customer_rate"], 2), "≥ 5%", "🟢" if k["repeat_customer_rate"] >= .05 else "🔴"],
], columns=["KPI", "Actual", "Target", "Status"])
st.dataframe(sc, hide_index=True, width="stretch")
insight("Targets are illustrative management thresholds (configurable), not values from the dataset. "
        "The repeat-customer rate is the weakest KPI: almost all Olist customers buy only once.")
