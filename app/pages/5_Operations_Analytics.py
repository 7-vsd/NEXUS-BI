"""Operations Analytics – delivery, cancellations, reviews by geography."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.components.data import REGION_OF, filtered_orders
from app.components.theme import PALETTE
from app.components.ui import chart, empty_state, insight, kpi_row, num, page_header, pct, section

page_header("Operations Analytics", "Delivery speed and reliability, cancellations and their impact on satisfaction.")
om = filtered_orders()
dl = om[om.is_delivered].copy()
if dl.empty:
    empty_state(); st.stop()

kpi_row([dict(label="Delivered orders", value=num(len(dl)), accent=True),
         dict(label="On-time rate", value=pct(dl.is_on_time.astype(float).mean())),
         dict(label="Avg delivery time", value=f"{dl.delivery_days.mean():.1f} days"),
         dict(label="Median delivery time", value=f"{dl.delivery_days.median():.1f} days"),
         dict(label="Cancellation rate", value=pct(om.is_canceled.mean(), 2))])

c1, c2 = st.columns(2)
with c1:
    section("Delivery time distribution")
    fig = px.histogram(dl[dl.delivery_days <= 60], x="delivery_days", nbins=60,
                       labels={"delivery_days": "Days from purchase to delivery"})
    fig.update_traces(marker_color=PALETTE["blue"])
    fig.update_layout(yaxis_title="Orders")
    fig.add_vline(x=dl.delivery_days.median(), line_dash="dot", line_color=PALETTE["teal"],
                  annotation_text="median", annotation_position="top")
    chart(fig, 330)
with c2:
    section("Monthly on-time rate and average delivery days")
    m = dl.groupby("purchase_month").agg(on_time=("is_on_time", lambda s: s.astype(float).mean()),
                                         days=("delivery_days", "mean"), n=("order_id", "size")).reset_index()
    m = m[m.n >= 100]
    fig = go.Figure()
    fig.add_bar(x=m.purchase_month, y=m.days, name="Avg delivery days", marker_color=PALETTE["muted_blue"])
    fig.add_scatter(x=m.purchase_month, y=m.on_time * 100, name="On-time %", yaxis="y2",
                    line=dict(color=PALETTE["teal"], width=2.5))
    fig.update_layout(yaxis_title="Days", yaxis2=dict(title="On-time %", overlaying="y", side="right", showgrid=False,
                                                       tickformat=".0f", ticksuffix="%"))
    chart(fig, 330)

section("Late-delivery rate and delivery time by customer state")
s = dl.groupby("customer_state").agg(orders=("order_id", "size"), late=("is_late", lambda x: x.astype(float).mean()),
                                     days=("delivery_days", "mean"), est=("estimated_delivery_days", "mean"),
                                     review=("review_score", "mean")).reset_index()
s["region"] = s.customer_state.map(REGION_OF)
s = s[s.orders >= 50].sort_values("late", ascending=False)
fig = px.bar(s, x="customer_state", y="late", color="region", hover_data={"orders": True, "days": ":.1f", "review": ":.2f"},
             labels={"customer_state": "State", "late": "Late-delivery rate", "region": "Region"})
fig.update_yaxes(tickformat=".0%")
chart(fig, 360)
worst = s.iloc[0]
insight(f"<b>{worst.customer_state}</b> has the highest late rate ({worst.late:.1%}) with {worst.days:.1f} days average "
        "delivery. North/Northeast states combine long distances with lower reliability.")

c3, c4 = st.columns(2)
with c3:
    section("Review score vs delivery delay")
    b = pd.cut(dl.delivery_delay_days.astype(float), [-100, -10, -1, 0, 5, 15, 400],
               labels=["10+ d early", "1–9 d early", "on day", "1–5 d late", "6–15 d late", "16+ d late"])
    r = dl.groupby(b, observed=True).agg(review=("review_score", "mean"), n=("order_id", "size")).reset_index()
    fig = px.bar(r, x="delivery_delay_days", y="review", text=r.review.round(2),
                 labels={"delivery_delay_days": "Actual vs estimated delivery", "review": "Average review (1–5)"})
    fig.update_traces(marker_color=[PALETTE["green"]] * 3 + [PALETTE["amber"], PALETTE["red"], PALETTE["red"]],
                      textposition="outside", cliponaxis=False)
    fig.update_yaxes(range=[0, 5.4])
    chart(fig, 340)
with c4:
    section("Order status mix")
    st_mix = om.order_status.value_counts().reset_index()
    st_mix.columns = ["status", "orders"]
    fig = px.bar(st_mix[st_mix.status != "delivered"], x="status", y="orders",
                 labels={"status": "Status (excluding delivered)", "orders": "Orders"})
    fig.update_traces(marker_color=PALETTE["grey_dark"])
    chart(fig, 340)
insight("Late orders score ~1.5–2 points lower than early ones. Delivery reliability is the strongest observed driver "
        "of satisfaction in this data (correlational; a controlled test would be needed to quantify causal impact).")
