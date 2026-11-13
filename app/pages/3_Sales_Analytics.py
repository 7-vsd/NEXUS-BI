"""Sales Analytics – categories, sellers, payments."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from app.components.data import filtered_items, filtered_orders, pretty
from app.components.theme import PALETTE
from app.components.ui import brl, chart, empty_state, insight, kpi_row, num, page_header, section

page_header("Sales Analytics", "Category mix, price points, seller performance and payment behaviour.")
it = filtered_items()
it = it[it.is_revenue_order]
om = filtered_orders()
if it.empty:
    empty_state(); st.stop()

kpi_row([dict(label="Items sold", value=num(len(it)), accent=True),
         dict(label="Active sellers", value=num(it.seller_id.nunique())),
         dict(label="Products sold", value=num(it.product_id.nunique())),
         dict(label="Avg item price", value=brl(it.price.mean(), 2))])

tab1, tab2, tab3 = st.tabs(["Categories", "Sellers", "Payments"])
with tab1:
    cat = (it.groupby("product_category_name_english")
             .agg(revenue=("price", "sum"), units=("order_item_id", "size"), avg_price=("price", "mean"),
                  freight=("freight_value", "sum")).reset_index())
    cat["category"] = cat.product_category_name_english.map(pretty)
    cat["freight_ratio"] = cat.freight / cat.revenue
    c1, c2 = st.columns([1.3, 1])
    with c1:
        section("Category revenue treemap")
        fig = px.treemap(cat.nlargest(30, "revenue"), path=["category"], values="revenue",
                         color="avg_price", color_continuous_scale=["#13294B", "#3B6EA8", "#14B8A6"],
                         labels={"avg_price": "Avg price (BRL)"})
        chart(fig, 430)
    with c2:
        section("Pareto: cumulative revenue share")
        c = cat.sort_values("revenue", ascending=False).reset_index(drop=True)
        c["cum_share"] = c.revenue.cumsum() / c.revenue.sum() * 100
        fig = px.line(c, x=c.index + 1, y="cum_share", markers=False,
                      labels={"x": "Number of categories (ranked)", "cum_share": "Cumulative revenue share (%)"})
        fig.add_hline(y=80, line_dash="dot", line_color=PALETTE["amber"])
        chart(fig, 430)
        n80 = int((c.cum_share < 80).sum() + 1)
        insight(f"<b>{n80}</b> of {len(c)} categories generate 80% of item revenue.")
    section("Price vs freight burden (bubble = units sold)")
    fig = px.scatter(cat[cat.units >= 200], x="avg_price", y="freight_ratio", size="units", hover_name="category",
                     log_x=True, labels={"avg_price": "Average item price (BRL, log scale)",
                                         "freight_ratio": "Freight as share of item revenue"})
    fig.update_yaxes(tickformat=".0%")
    chart(fig, 380)
    insight("Low-priced categories carry the heaviest freight burden relative to price – candidates for "
            "free-shipping thresholds or bundle offers.")

with tab2:
    s = it.groupby(["seller_id", "seller_state"]).agg(gmv=("price", "sum"), items=("order_item_id", "size"),
                                                       orders=("order_id", "nunique")).reset_index()
    rv = om[["order_id", "review_score", "is_late"]]
    so = it[["seller_id", "order_id"]].drop_duplicates().merge(rv, on="order_id")
    q = so.groupby("seller_id").agg(avg_review=("review_score", "mean"),
                                    late_rate=("is_late", lambda x: x.astype(float).mean())).reset_index()
    s = s.merge(q, on="seller_id", how="left")
    c1, c2 = st.columns([1.2, 1])
    with c1:
        section("Seller quality vs volume (sellers with ≥ 30 orders)")
        big = s[s.orders >= 30]
        fig = px.scatter(big, x="orders", y="avg_review", size="gmv", color="late_rate", log_x=True,
                         hover_data={"seller_id": True, "seller_state": True},
                         color_continuous_scale=["#14B8A6", "#F59E0B", "#DC2626"],
                         labels={"orders": "Orders (log)", "avg_review": "Average review", "late_rate": "Late rate"})
        if len(big):
            fig.add_hline(y=big.avg_review.median(), line_dash="dot", line_color=PALETTE["grey"])
            fig.add_vline(x=big.orders.median(), line_dash="dot", line_color=PALETTE["grey"])
        chart(fig, 420)
    with c2:
        section("Top 15 sellers by GMV")
        st.dataframe(s.nlargest(15, "gmv"), hide_index=True, width="stretch", height=420,
                     column_config={"gmv": st.column_config.NumberColumn("GMV (BRL)", format="localized"),
                                    "avg_review": st.column_config.NumberColumn("Avg review", format="%.2f"),
                                    "late_rate": st.column_config.NumberColumn("Late rate", format="percent"),
                                    "seller_id": st.column_config.TextColumn("Seller", width="small")})
    total = s.gmv.sum()
    top10 = s.nlargest(max(1, int(len(s) * .1)), "gmv").gmv.sum()
    insight(f"Top 10% of sellers generate <b>{100 * top10 / total:.1f}%</b> of GMV – key-account management "
            "and quality monitoring should focus on this group.")

with tab3:
    pays = om[om.is_revenue_order]
    c1, c2 = st.columns(2)
    with c1:
        section("Main payment method (orders)")
        pm = pays.main_payment_type.fillna("unknown").value_counts()
        fig = px.pie(values=pm.values, names=[pretty(x) for x in pm.index], hole=.55)
        chart(fig, 340)
    with c2:
        section("Installments vs average order value")
        b = pd.cut(pays.max_installments.fillna(1), [0, 1, 3, 6, 10, 30], labels=["1", "2-3", "4-6", "7-10", "11+"])
        ib = pays.groupby(b, observed=True).agg(aov=("revenue", "mean"), orders=("order_id", "size")).reset_index()
        fig = px.bar(ib, x="max_installments", y="aov", text="orders",
                     labels={"max_installments": "Installments", "aov": "Average order value (BRL)"})
        fig.update_traces(marker_color=PALETTE["blue"], texttemplate="%{text:,} orders", textposition="outside", cliponaxis=False)
        chart(fig, 340)
    insight("Order value rises steeply with the number of installments: credit-card instalment plans enable "
            "high-ticket purchases (association, not proven causation).")
