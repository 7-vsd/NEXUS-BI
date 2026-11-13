"""Customer Intelligence – segments, RFM, cohorts, CLV."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from app.components import api_client
from app.components.data import filtered_orders, load
from app.components.theme import PALETTE
from app.components.ui import brl, chart, empty_state, insight, kpi_row, note, num, page_header, pct, section

page_header("Customer Intelligence", "Who the customers are, how they are segmented and whether they come back.")
om = filtered_orders()
rev = om[om.is_revenue_order & (om.items_count > 0)]
if rev.empty:
    empty_state(); st.stop()

per = rev.groupby("customer_unique_id").agg(orders=("order_id", "nunique"), revenue=("revenue", "sum"))
kpi_row([dict(label="Customers", value=num(len(per)), accent=True),
         dict(label="Repeat-customer rate", value=pct((per.orders > 1).mean(), 2)),
         dict(label="Revenue per customer", value=brl(per.revenue.mean(), 2)),
         dict(label="Orders per customer", value=f"{per.orders.mean():.3f}")])

section("Machine-learning segments (K-Means on RFM)")
try:
    segs = api_client.cached_get("/api/customer-segments")
    cols = st.columns(len(segs["clusters"]))
    for col, c in zip(cols, sorted(segs["clusters"], key=lambda x: -x["revenue_share_pct"])):
        with col:
            st.markdown(f"""<div class="nx-card accent"><div class="lbl">{c['cluster_name']}</div>
<div class="val">{c['customers']:,}</div>
<div class="delta-neu">{c['customer_share_pct']}% of customers · {c['revenue_share_pct']}% of revenue</div>
<div class="delta-neu">Median recency {c['recency_median_days']:.0f} d · median spend R$ {c['monetary_median']:.0f}</div>
<div style="margin-top:6px;font-size:.82rem">🎯 {c['recommended_strategy']}</div></div>""", unsafe_allow_html=True)
    st.caption(f"k = {segs['selected_k']} selected by silhouette ({segs['silhouette']:.3f}). Source: FastAPI /api/customer-segments.")
except api_client.ApiError as exc:
    note(f"⚠️ {exc}")

seg = load("customer_segments")
seg = seg[seg.customer_unique_id.isin(per.index)]
c1, c2 = st.columns(2)
with c1:
    section("Rule-based RFM segments")
    r = seg.groupby("rfm_segment").agg(customers=("customer_unique_id", "size"), revenue=("monetary", "sum")).reset_index()
    fig = px.bar(r.sort_values("revenue"), x="revenue", y="rfm_segment", orientation="h", text="customers",
                 labels={"revenue": "Revenue (BRL)", "rfm_segment": ""})
    fig.update_traces(marker_color=PALETTE["teal"], texttemplate="%{text:,} customers", textposition="inside",
                      insidetextanchor="end", textfont_color="#0B1F3A")
    chart(fig, 360)
with c2:
    section("Recency vs monetary (5k sample)")
    smp = seg.sample(min(5000, len(seg)), random_state=42)
    fig = px.scatter(smp, x="recency_days", y="monetary", color="cluster_name", log_y=True, opacity=.6,
                     color_discrete_sequence=[PALETTE["teal"], PALETTE["amber"], PALETTE["muted_blue"], "#8B5CF6"],
                     labels={"recency_days": "Days since last purchase", "monetary": "Lifetime revenue (BRL, log)",
                             "cluster_name": "Segment"})
    chart(fig, 360)

section("Monthly cohort retention (% of cohort ordering again in month k)")
o = rev[["customer_unique_id", "order_purchase_timestamp"]].copy()
o["m"] = o.order_purchase_timestamp.dt.to_period("M")
first = o.groupby("customer_unique_id").m.min().rename("cohort")
o = o.join(first, on="customer_unique_id")
o["k"] = (o.m - o.cohort).apply(lambda x: x.n)
coh = o.drop_duplicates(["customer_unique_id", "k"]).pivot_table(index="cohort", columns="k", values="customer_unique_id",
                                                                    aggfunc="count")
coh = coh[(coh.index >= pd.Period("2017-01", "M")) & (coh.index <= pd.Period("2018-06", "M"))]
if len(coh):
    ret = coh.div(coh[0], axis=0).iloc[:, 1:7] * 100
    ret.index = ret.index.astype(str)
    fig = px.imshow(ret, text_auto=".2f", aspect="auto", color_continuous_scale=["#0B1F3A", "#14B8A6"],
                    labels={"x": "Months since first purchase", "y": "Acquisition cohort", "color": "Retention %"})
    chart(fig, 460)
    insight(f"Month-1 retention averages <b>{ret[1].mean():.2f}%</b>: the business is almost entirely acquisition-driven. "
            "A second-purchase programme is the largest untapped lever.")

section("Customer value distribution (lifetime revenue deciles)")
dec = per.revenue.sort_values(ascending=False).reset_index(drop=True)
dd = pd.DataFrame({"decile": np.ceil((dec.index + 1) / len(dec) * 10).astype(int), "revenue": dec.values})
dd = dd.groupby("decile").revenue.agg(["sum", "mean"]).reset_index()
dd["share"] = dd["sum"] / dd["sum"].sum() * 100
fig = px.bar(dd, x="decile", y="share", text=dd["mean"].map(lambda v: f"avg R$ {v:,.0f}"),
             labels={"decile": "Customer decile (1 = top 10%)", "share": "Share of revenue (%)"})
fig.update_traces(marker_color=PALETTE["blue"], textposition="outside", cliponaxis=False)
chart(fig, 340)

section("Look up a customer")
cid = st.text_input("customer_unique_id (32 characters)", placeholder="e.g. " + seg.customer_unique_id.iloc[0])
if cid:
    try:
        res = api_client.get("/api/customer-segments", {"customer_unique_id": cid.strip()})
        st.json(res["customer"])
    except api_client.ApiError as exc:
        st.warning(str(exc))
