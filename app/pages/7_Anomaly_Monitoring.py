"""Anomaly Monitoring – flagged business days and on-demand scoring."""
from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.components import api_client
from app.components.data import load
from app.components.theme import PALETTE
from app.components.ui import chart, insight, kpi_row, note, page_header, section

page_header("Anomaly Monitoring", "Days where revenue/operations deviate from expected behaviour (3 detectors, vote ≥ 2).")
a = load("anomalies")
flag = a[a.is_anomaly].sort_values("date", ascending=False)
kpi_row([dict(label="Days monitored", value=f"{len(a):,}", accent=True),
         dict(label="Consensus anomalies", value=str(len(flag))),
         dict(label="High severity", value=str(int((flag.severity == "High").sum()))),
         dict(label="Isolation-Forest flags", value=str(int(a.iforest_flag.sum())))])

section("Daily revenue with anomaly alerts")
fig = go.Figure()
fig.add_scatter(x=a.date, y=a.revenue, name="Revenue", line=dict(color=PALETTE["blue"], width=1.2))
for sev, color in [("Medium", PALETTE["amber"]), ("High", PALETTE["red"])]:
    s = flag[flag.severity == sev]
    fig.add_scatter(x=s.date, y=s.revenue, mode="markers", name=f"{sev} severity",
                    marker=dict(color=color, size=11, line=dict(width=1, color="white")),
                    text=s.top_driver, hovertemplate="%{x|%Y-%m-%d}<br>R$ %{y:,.0f}<br>driver: %{text}<extra></extra>")
fig.update_layout(yaxis_title="Revenue (BRL)")
chart(fig, 400)

section("Alert log")
if flag.empty:
    st.success("No consensus anomalies in the monitored window.")
else:
    st.dataframe(flag[["date", "severity", "direction", "revenue", "orders", "aov", "late_rate", "votes", "top_driver",
                       "rolling_z", "global_z", "iforest_score"]],
                 hide_index=True, width="stretch",
                 column_config={"date": st.column_config.DateColumn("Date"),
                                "revenue": st.column_config.NumberColumn("Revenue", format="localized"),
                                "late_rate": st.column_config.NumberColumn("Late rate", format="percent"),
                                "aov": st.column_config.NumberColumn("AOV", format="R$ %.2f")})
insight("Black Friday 2017 (24-Nov) is the only High-severity alert – an expected, explainable spike. Alerts such as "
        "the late-delivery surge on 2018-02-26 deserve operational root-cause review.")

section("Check a new day (POST /api/detect-anomaly)")
with st.form("anom"):
    c = st.columns(6)
    d = c[0].date_input("Date", date(2018, 8, 20))
    rv = c[1].number_input("Revenue (BRL)", 0.0, 2_000_000.0, 45000.0, step=1000.0)
    od = c[2].number_input("Orders", 0, 10000, 280)
    lr = c[3].number_input("Late rate", 0.0, 1.0, 0.06)
    ar = c[4].number_input("Avg review", 1.0, 5.0, 4.1)
    cr = c[5].number_input("Cancel rate", 0.0, 1.0, 0.004, format="%.3f")
    go_ = st.form_submit_button("Score", type="primary")
if go_:
    try:
        r = api_client.post("/api/detect-anomaly", {"date": str(d), "revenue": rv, "orders": int(od), "late_rate": lr,
                                                    "avg_review": ar, "cancel_rate": cr})
        (st.error if r["is_anomaly"] else st.success)(
            f"{'🚨 ANOMALY' if r['is_anomaly'] else '✅ Normal'} · severity {r['severity']} · {r['direction']} · "
            f"votes {r['votes']}/3 · rolling z {r['rolling_z']:.2f} · global z {r['global_z']:.2f}")
        st.json(r["flags"])
    except api_client.ApiError as exc:
        note(f"⚠️ {exc}")
