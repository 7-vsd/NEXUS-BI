"""Python analytical marts built from the cleaned (staging) datasets.

These marts feed machine learning, the API and Streamlit. They are an
independent implementation of the same business rules used by the SQL
warehouse (``sql/procedures``) – the reconciliation module compares both.

KPI rules (see docs/business_requirements/KPI_DEFINITIONS.md):
* Revenue      = SUM(item price + item freight) for orders whose status is not
                 'canceled' or 'unavailable'. Currency: BRL.
* Orders       = COUNT(DISTINCT order_id) with the same status filter.
* Customers    = COUNT(DISTINCT customer_unique_id) with the same filter.
* AOV          = Revenue / Orders.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def build_items_enriched(t: dict[str, pd.DataFrame]) -> pd.DataFrame:
    items = t["order_items"].merge(
        t["products"][["product_id", "product_category_name", "product_category_name_english"]],
        on="product_id", how="left")
    items = items.merge(t["sellers"][["seller_id", "seller_state", "seller_city"]], on="seller_id", how="left")
    items = items.merge(t["orders"][["order_id", "order_purchase_timestamp", "order_purchase_date",
                                     "order_status", "is_revenue_order", "customer_id"]], on="order_id", how="left")
    items = items.merge(t["customers"][["customer_id", "customer_unique_id", "customer_state"]],
                        on="customer_id", how="left")
    items["product_category_name_english"] = items.product_category_name_english.fillna("unknown")
    return items


def build_order_mart(t: dict[str, pd.DataFrame], items: pd.DataFrame) -> pd.DataFrame:
    o = t["orders"].merge(t["customers"], on="customer_id", how="left")
    item_agg = items.groupby("order_id").agg(
        items_count=("order_item_id", "size"),
        distinct_products=("product_id", "nunique"),
        distinct_sellers=("seller_id", "nunique"),
        items_price=("price", "sum"),
        freight_value=("freight_value", "sum"),
    ).reset_index()
    # Dominant category = category of the highest-value line
    top_cat = (items.sort_values(["order_id", "price"], ascending=[True, False])
                    .drop_duplicates("order_id")[["order_id", "product_category_name_english", "seller_state"]]
                    .rename(columns={"product_category_name_english": "main_category",
                                     "seller_state": "main_seller_state"}))
    pays = t["payments"]
    pay_agg = pays.groupby("order_id").agg(payment_value=("payment_value", "sum"),
                                           payment_count=("payment_sequential", "size"),
                                           max_installments=("payment_installments", "max")).reset_index()
    main_pay = (pays.sort_values(["order_id", "payment_value"], ascending=[True, False])
                    .drop_duplicates("order_id")[["order_id", "payment_type"]]
                    .rename(columns={"payment_type": "main_payment_type"}))
    rev = t["reviews"]
    rev = rev[rev.is_latest_for_order][["order_id", "review_score"]]
    m = (o.merge(item_agg, on="order_id", how="left").merge(top_cat, on="order_id", how="left")
          .merge(pay_agg, on="order_id", how="left").merge(main_pay, on="order_id", how="left")
          .merge(rev, on="order_id", how="left"))
    for c in ("items_count", "distinct_products", "distinct_sellers"):
        m[c] = m[c].fillna(0).astype(int)
    for c in ("items_price", "freight_value", "payment_value"):
        m[c] = m[c].fillna(0.0).round(2)
    m["order_value"] = (m.items_price + m.freight_value).round(2)
    m["revenue"] = np.where(m.is_revenue_order, m.order_value, 0.0)
    m["purchase_month"] = m.order_purchase_timestamp.dt.to_period("M").dt.to_timestamp()
    return m


def build_customer_mart(order_mart: pd.DataFrame) -> pd.DataFrame:
    rev = order_mart[order_mart.is_revenue_order & (order_mart.items_count > 0)]
    g = rev.sort_values("order_purchase_timestamp").groupby("customer_unique_id")
    cm = g.agg(first_order=("order_purchase_timestamp", "min"),
               last_order=("order_purchase_timestamp", "max"),
               orders=("order_id", "nunique"),
               revenue=("revenue", "sum"),
               avg_order_value=("revenue", "mean"),
               avg_review=("review_score", "mean"),
               avg_delivery_days=("delivery_days", "mean"),
               late_orders=("is_late", lambda s: int(s.fillna(False).sum())),
               customer_state=("customer_state", "last"),
               customer_city=("customer_city", "last")).reset_index()
    cm["is_repeat"] = cm.orders > 1
    cm["tenure_days"] = (cm.last_order - cm.first_order).dt.days
    return cm


def build_daily_kpis(order_mart: pd.DataFrame) -> pd.DataFrame:
    om = order_mart.copy()
    om["date"] = om.order_purchase_date
    rev = om[om.is_revenue_order]
    daily = rev.groupby("date").agg(revenue=("revenue", "sum"), orders=("order_id", "nunique"),
                                    customers=("customer_unique_id", "nunique"),
                                    items=("items_count", "sum"),
                                    avg_review=("review_score", "mean")).reset_index()
    # explicit int flags: keeps aggregates numeric under both pandas 2.x and 3.x
    om["_canceled_int"] = om.is_canceled.fillna(False).astype(bool).astype(int)
    om["_late_int"] = om.is_late.fillna(False).astype(bool).astype(int)
    canc = om.groupby("date").agg(all_orders=("order_id", "nunique"), canceled=("_canceled_int", "sum")).reset_index()
    dl = om[om.is_delivered.astype(bool)].groupby("date").agg(delivered=("order_id", "size"),
                                                 late=("_late_int", "sum"),
                                                 avg_delivery_days=("delivery_days", "mean")).reset_index()
    out = daily.merge(canc, on="date", how="outer").merge(dl, on="date", how="left")
    full = pd.DataFrame({"date": pd.date_range(out.date.min(), out.date.max(), freq="D")})
    out = full.merge(out, on="date", how="left")
    for c in ("revenue", "orders", "customers", "items", "all_orders", "canceled", "delivered", "late"):
        out[c] = pd.to_numeric(out[c], errors="coerce").astype("float64").fillna(0.0)
    out["aov"] = np.where(out.orders > 0, out.revenue / out.orders.replace(0, np.nan), np.nan)
    out["late_rate"] = np.where(out.delivered > 0, out.late / out.delivered.replace(0, np.nan), np.nan)
    out["cancel_rate"] = np.where(out.all_orders > 0, out.canceled / out.all_orders.replace(0, np.nan), np.nan)
    return out


def build_category_weekly(items: pd.DataFrame) -> pd.DataFrame:
    it = items[items.is_revenue_order].copy()
    it["week"] = it.order_purchase_date.dt.to_period("W-SUN").dt.start_time
    return (it.groupby(["product_category_name_english", "week"])
              .agg(units=("order_item_id", "size"), revenue=("price", "sum"), orders=("order_id", "nunique"))
              .reset_index().rename(columns={"product_category_name_english": "category"}))


def headline_kpis(order_mart: pd.DataFrame) -> dict[str, float]:
    rev = order_mart[order_mart.is_revenue_order]
    revenue = float(rev.revenue.sum())
    orders = int(rev.order_id.nunique())
    delivered = order_mart[order_mart.is_delivered]
    return {
        "total_revenue": round(revenue, 2),
        "product_revenue": round(float(rev.items_price.sum()), 2),
        "freight_revenue": round(float(rev.freight_value.sum()), 2),
        "total_orders": orders,
        "all_orders": int(order_mart.order_id.nunique()),
        "unique_customers": int(rev.customer_unique_id.nunique()),
        "average_order_value": round(revenue / orders, 2) if orders else 0.0,
        "total_payment_value": round(float(order_mart.payment_value.sum()), 2),
        "cancellation_rate": round(float(order_mart.is_canceled.mean()), 6),
        "on_time_delivery_rate": round(float(delivered.is_on_time.astype(float).mean()), 6),
        "avg_delivery_days": round(float(delivered.delivery_days.mean()), 4),
        "avg_review_score": round(float(order_mart.review_score.mean()), 4),
        "items_sold": int(rev.items_count.sum()),
    }
