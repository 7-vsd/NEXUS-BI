"""Revenue Intelligence – trends, growth, seasonality."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.components.data import filtered_orders
from app.components.theme import PALETTE
from app.components.ui import brl, chart, empty_state, insight, kpi_row, page_header, section

page_header("Revenue Intelligence", "Revenue trends, growth rates, rolling averages and seasonality (BRL).")
om = filtered_orders()
rev = om[om.is_revenue_order].copy()
if rev.empty:
    empty_state(); st.stop()

grain = st.segmented_control("Granularity", ["Daily", "Weekly", "Monthly"], default="Weekly")
freq = {"Daily": "D", "Weekly": "W-MON", "Monthly": "MS"}[grain or "Weekly"]
ts = rev.set_index("order_purchase_timestamp").revenue.resample(freq).sum()

total = rev.revenue.sum()
days = max((rev.order_purchase_timestamp.max() - rev.order_purchase_timestamp.min()).days, 1)
kpi_row([dict(label="Revenue (period)", value=brl(total), accent=True),
         dict(label="Avg daily revenue", value=brl(total / days)),
         dict(label="Product revenue", value=brl(rev.items_price.sum())),
         dict(label="Freight revenue", value=brl(rev.freight_value.sum()),
              delta_label=f"{100 * rev.freight_value.sum() / total:.1f}% of revenue")])

section(f"{grain} revenue with rolling average")
win = {"D": 7, "W-MON": 4, "MS": 3}[freq]
fig = go.Figure()
fig.add_scatter(x=ts.index, y=ts.values, name="Revenue", line=dict(color=PALETTE["blue"], width=1.4))
fig.add_scatter(x=ts.index, y=ts.rolling(win).mean(), name=f"{win}-period rolling mean",
                line=dict(color=PALETTE["teal"], width=2.4))
fig.update_layout(yaxis_title="Revenue (BRL)", xaxis_title="")
chart(fig, 380)

c1, c2 = st.columns(2)
with c1:
    section("Month-over-month growth")
    m = rev.set_index("order_purchase_timestamp").revenue.resample("MS").sum()
    mom = (m.pct_change() * 100).dropna()
    mom = mom[mom.index >= "2017-02-01"]
    fig = px.bar(x=mom.index, y=mom.values, labels={"x": "", "y": "MoM growth (%)"})
    fig.update_traces(marker_color=np.where(mom.values >= 0, PALETTE["green"], PALETTE["red"]))
    chart(fig, 320)
with c2:
    section("Year-over-year by month (2017 vs 2018)")
    mm = m.to_frame("revenue").assign(year=m.index.year, month=m.index.month)
    mm = mm[mm.year.isin([2017, 2018])]
    fig = px.line(mm, x="month", y="revenue", color=mm.year.astype(str), markers=True,
                  labels={"month": "Month", "revenue": "Revenue (BRL)", "color": "Year"})
    fig.update_xaxes(tickmode="array", tickvals=list(range(1, 13)),
                     ticktext=["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
    chart(fig, 320)

section("When do customers buy? Revenue by weekday × hour")
h = rev.assign(dow=rev.order_purchase_timestamp.dt.day_name().str[:3], hour=rev.order_purchase_timestamp.dt.hour)
piv = h.pivot_table(index="dow", columns="hour", values="revenue", aggfunc="sum").reindex(
    ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
fig = px.imshow(piv, aspect="auto", color_continuous_scale=["#0B1F3A", "#3B6EA8", "#14B8A6", "#FDE68A"],
                labels={"x": "Hour of day", "y": "", "color": "Revenue (BRL)"})
chart(fig, 320)
insight("Purchases concentrate on weekday working hours (≈10:00–22:00) and fall away on Saturdays – "
        "schedule campaigns and flash sales for Monday–Tuesday daytime.")

ytd17 = rev[(rev.order_purchase_timestamp.dt.year == 2017) & (rev.order_purchase_timestamp.dt.month <= 8)].revenue.sum()
ytd18 = rev[(rev.order_purchase_timestamp.dt.year == 2018) & (rev.order_purchase_timestamp.dt.month <= 8)].revenue.sum()
if ytd17 > 0 and ytd18 > 0:
    insight(f"Jan–Aug revenue grew from {brl(ytd17)} (2017) to {brl(ytd18)} (2018): "
            f"<b>{100 * (ytd18 / ytd17 - 1):+.1f}%</b> year-over-year for the current filter selection.")
