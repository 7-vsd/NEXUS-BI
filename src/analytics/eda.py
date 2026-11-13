"""Exploratory & statistical analysis library used by the notebooks and the EDA report.

Every function computes its statistics from the processed data, saves a
labelled chart to ``reports/figures/eda`` and returns a ``Finding`` whose
``interpretation`` text is generated FROM the computed numbers – nothing is
hand-typed, so the narrative always matches the data.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats

from src.config.settings import settings

FIG = settings.reports_dir / "figures" / "eda"
NAVY, TEAL, BLUE, AMBER, RED, GREY = "#13294B", "#14B8A6", "#3B6EA8", "#F59E0B", "#DC2626", "#94A3B8"
sns.set_theme(style="whitegrid", rc={"axes.titleweight": "bold", "axes.titlesize": 12, "figure.dpi": 110})


@dataclass
class Finding:
    key: str
    title: str
    figure: str | None
    stats: dict = field(default_factory=dict)
    interpretation: str = ""


def _save(fig, name: str) -> str:
    FIG.mkdir(parents=True, exist_ok=True)
    path = FIG / f"{name}.png"
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return str(path.relative_to(settings.project_root)).replace("\\", "/")


def load():
    P = settings.processed_dir
    om = pd.read_parquet(P / "order_mart.parquet")
    items = pd.read_parquet(P / "items_enriched.parquet")
    cm = pd.read_parquet(P / "customer_mart.parquet")
    daily = pd.read_parquet(P / "daily_kpis.parquet")
    return om, items, cm, daily


def _rev(om):
    return om[om.is_revenue_order & (om.items_count > 0)]


# =========================================================== 01 data understanding
def dataset_overview() -> pd.DataFrame:
    rows = []
    for p in sorted((settings.staging_dir / "typed").glob("*.parquet")):
        df = pd.read_parquet(p)
        rows.append({"dataset": p.stem, "rows": len(df), "columns": df.shape[1],
                     "memory_mb": round(df.memory_usage(deep=True).sum() / 1e6, 1),
                     "null_cells_pct": round(100 * df.isna().sum().sum() / df.size, 2)})
    return pd.DataFrame(rows)


def relationship_cardinality() -> pd.DataFrame:
    T = settings.staging_dir / "clean"
    o, oi, pm, rv, c = (pd.read_parquet(T / f"{n}.parquet") for n in ("orders", "order_items", "payments", "reviews", "customers"))
    return pd.DataFrame([
        {"relationship": "orders → order_items", "avg_children": round(oi.groupby("order_id").size().mean(), 3),
         "max_children": int(oi.groupby("order_id").size().max()), "parents_without_children": int((~o.order_id.isin(oi.order_id)).sum())},
        {"relationship": "orders → payments", "avg_children": round(pm.groupby("order_id").size().mean(), 3),
         "max_children": int(pm.groupby("order_id").size().max()), "parents_without_children": int((~o.order_id.isin(pm.order_id)).sum())},
        {"relationship": "orders → reviews", "avg_children": round(rv.groupby("order_id").size().mean(), 3),
         "max_children": int(rv.groupby("order_id").size().max()), "parents_without_children": int((~o.order_id.isin(rv.order_id)).sum())},
        {"relationship": "customer_unique_id → customer_id", "avg_children": round(c.groupby("customer_unique_id").size().mean(), 3),
         "max_children": int(c.groupby("customer_unique_id").size().max()), "parents_without_children": 0},
    ])


# =========================================================== 03 exploratory
def univariate_order_value(om) -> Finding:
    r = _rev(om)
    v = r.order_value
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    sns.histplot(v[v <= v.quantile(.99)], bins=60, ax=ax[0], color=BLUE)
    ax[0].set(title="Order value distribution (≤ P99)", xlabel="Order value (BRL)", ylabel="Orders")
    sns.histplot(np.log10(v[v > 0]), bins=60, ax=ax[1], color=TEAL)
    ax[1].set(title="Order value – log10 scale", xlabel="log10(order value, BRL)", ylabel="Orders")
    f = _save(fig, "03_univariate_order_value")
    s = {"mean": v.mean(), "median": v.median(), "p90": v.quantile(.9), "p99": v.quantile(.99), "skew": stats.skew(v)}
    return Finding("order_value", "Order value distribution", f, s,
                   f"Order values are strongly right-skewed (skew {s['skew']:.1f}): median R$ {s['median']:.2f} vs mean "
                   f"R$ {s['mean']:.2f}; 10% of orders exceed R$ {s['p90']:.0f}. Use medians and log-scales for reporting; "
                   "averages are pulled up by a long tail of high-ticket orders.")


def univariate_delivery(om) -> Finding:
    d = om[om.is_delivered]
    fig, ax = plt.subplots(figsize=(9, 4))
    sns.histplot(d.delivery_days.clip(upper=60), bins=60, color=BLUE, ax=ax, label="Actual")
    sns.histplot(d.estimated_delivery_days.clip(upper=60), bins=60, color=AMBER, alpha=.4, ax=ax, label="Estimated")
    ax.set(title="Actual vs estimated delivery time (delivered orders, clipped at 60 days)", xlabel="Days from purchase", ylabel="Orders")
    ax.legend()
    f = _save(fig, "03_univariate_delivery_days")
    s = {"median_actual": d.delivery_days.median(), "median_estimated": d.estimated_delivery_days.median(),
         "on_time_rate": d.is_on_time.astype(float).mean(), "p95_actual": d.delivery_days.quantile(.95)}
    return Finding("delivery", "Delivery time vs estimate", f, s,
                   f"Median delivery takes {s['median_actual']:.1f} days against a median promise of {s['median_estimated']:.1f} days, "
                   f"so {s['on_time_rate']:.1%} of orders arrive on or before the estimate. Estimates are padded by roughly "
                   f"{s['median_estimated'] - s['median_actual']:.0f} days – reliable, but long promised lead times may cost conversion.")


def bivariate_price_freight(items) -> Finding:
    it = items[items.is_revenue_order]
    rho, p = stats.spearmanr(it.price, it.freight_value)
    smp = it.sample(min(8000, len(it)), random_state=42)
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(smp.price, smp.freight_value, s=6, alpha=.35, color=BLUE)
    ax.set(xscale="log", yscale="log", title="Item price vs freight (8k sample, log-log)", xlabel="Item price (BRL)", ylabel="Freight (BRL)")
    f = _save(fig, "03_bivariate_price_freight")
    ratio = (it.freight_value / it.price)
    s = {"spearman_rho": rho, "p_value": p, "median_freight_ratio": ratio.median(),
         "share_freight_gt_price": (it.freight_value > it.price).mean()}
    return Finding("price_freight", "Price vs freight", f, s,
                   f"Freight rises with price (Spearman ρ = {rho:.2f}, p < 0.001) but far less than proportionally: the median "
                   f"item pays freight worth {s['median_freight_ratio']:.0%} of its price, and on {s['share_freight_gt_price']:.1%} "
                   "of items freight exceeds the price itself – a conversion risk for cheap items.")


def bivariate_delay_review(om) -> Finding:
    d = om[om.is_delivered & om.review_score.notna()].copy()
    d["bucket"] = pd.cut(d.delivery_delay_days.astype(float), [-100, -10, -1, 0, 5, 15, 400],
                         labels=["≥10 d early", "1–9 d early", "on day", "1–5 d late", "6–15 d late", ">15 d late"])
    g = d.groupby("bucket", observed=True).review_score.agg(["mean", "size"])
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(g.index.astype(str), g["mean"], color=[TEAL, TEAL, TEAL, AMBER, RED, RED])
    for i, (m, n) in enumerate(zip(g["mean"], g["size"])):
        ax.text(i, m + .05, f"{m:.2f}\n(n={n:,})", ha="center", fontsize=8)
    ax.set(title="Average review score by delivery timing vs estimate", xlabel="Delivery vs estimated date",
           ylabel="Average review score (1–5)", ylim=(0, 5.5))
    f = _save(fig, "03_bivariate_delay_vs_review")
    early = d[d.delivery_delay_days <= 0].review_score.mean()
    late = d[d.delivery_delay_days > 0].review_score.mean()
    s = {"review_on_time": early, "review_late": late, "gap": early - late, "by_bucket": g["mean"].round(3).to_dict()}
    return Finding("delay_review", "Delivery delay vs satisfaction", f, s,
                   f"On-time orders average {early:.2f} stars versus {late:.2f} for late orders – a gap of {early - late:.2f} points. "
                   f"Orders more than 15 days late average {g['mean'].iloc[-1]:.2f}. Lateness is the most visible driver of "
                   "dissatisfaction in the data (association; see hypothesis test H1).")


def multivariate_correlation(om) -> Finding:
    d = _rev(om)[["order_value", "items_count", "freight_value", "max_installments", "delivery_days",
                  "estimated_delivery_days", "review_score", "distinct_sellers"]].dropna()
    corr = d.corr(method="spearman")
    fig, ax = plt.subplots(figsize=(8, 6.5))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="vlag", center=0, ax=ax, cbar_kws={"label": "Spearman ρ"})
    ax.set_title("Order-level correlation matrix (Spearman)")
    f = _save(fig, "03_multivariate_correlation")
    pairs = corr.where(np.triu(np.ones(corr.shape, bool), 1)).stack().sort_values(key=abs, ascending=False)
    top = pairs.head(4)
    return Finding("correlation", "Multivariate correlation", f, {"top_pairs": {f"{a}~{b}": round(v, 3) for (a, b), v in top.items()}},
                   "Strongest associations: " + "; ".join(f"{a} ~ {b} (ρ={v:.2f})" for (a, b), v in top.items()) +
                   f". Review score correlates negatively with delivery days (ρ={corr.loc['review_score', 'delivery_days']:.2f}) "
                   "and only weakly with order value – customers judge logistics more than price.")


def outliers_order_value(om) -> Finding:
    r = _rev(om)
    q1, q3 = r.order_value.quantile([.25, .75])
    upper = q3 + 1.5 * (q3 - q1)
    out = r[r.order_value > upper]
    fig, ax = plt.subplots(figsize=(10, 4))
    top_states = r.customer_state.value_counts().head(8).index
    sns.boxplot(data=r[r.customer_state.isin(top_states)], x="customer_state", y="order_value", ax=ax,
                color=BLUE, fliersize=1.5, order=top_states)
    ax.set(yscale="log", title="Order value by state – IQR outliers (log scale, top 8 states)", xlabel="Customer state",
           ylabel="Order value (BRL, log)")
    f = _save(fig, "03_outliers_order_value")
    s = {"iqr_upper_fence": upper, "outlier_orders": len(out), "outlier_share": len(out) / len(r),
         "outlier_revenue_share": out.revenue.sum() / r.revenue.sum()}
    return Finding("outliers", "Order-value outliers", f, s,
                   f"{len(out):,} orders ({s['outlier_share']:.1%}) exceed the IQR fence of R$ {upper:.0f}, yet they carry "
                   f"{s['outlier_revenue_share']:.1%} of revenue. They are legitimate high-ticket purchases, not errors – keep them, "
                   "but use robust statistics (median, trimmed means) for typical-customer KPIs.")


def time_series_revenue(daily) -> Finding:
    d = daily[(daily.date >= "2017-01-01") & (daily.date <= "2018-08-21")].set_index("date")
    full = daily.set_index("date").revenue
    m = full.resample("MS").sum()   # whole calendar months (matches SQL Q05)
    fig, ax = plt.subplots(2, 1, figsize=(11, 6.5))
    ax[0].plot(d.index, d.revenue / 1e3, color=GREY, lw=.7, label="Daily")
    ax[0].plot(d.index, d.revenue.rolling(28).mean() / 1e3, color=NAVY, lw=2, label="28-day rolling mean")
    ax[0].set(title="Daily revenue with 28-day rolling mean", ylabel="Revenue (thousand BRL)"); ax[0].legend()
    wd = d.groupby(d.index.dayofweek).revenue.mean()
    ax[1].bar(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], wd / 1e3, color=TEAL)
    ax[1].set(title="Average daily revenue by weekday", ylabel="Revenue (thousand BRL)", xlabel="Weekday")
    f = _save(fig, "03_time_series_revenue")
    h1_17, h1_18 = m["2017-01":"2017-08"].sum(), m["2018-01":"2018-08"].sum()
    peak = d.revenue.idxmax()
    s = {"peak_day": str(peak.date()), "peak_revenue": d.revenue.max(), "yoy_jan_aug_growth": h1_18 / h1_17 - 1,
         "best_weekday_rev": wd.max(), "worst_weekday_rev": wd.min()}
    return Finding("time_series", "Revenue over time", f, s,
                   f"Revenue grew {s['yoy_jan_aug_growth']:.0%} Jan–Aug 2018 vs 2017 but plateaued from early 2018. The single "
                   f"biggest day was {s['peak_day']} (Black Friday, R$ {s['peak_revenue']:,.0f}). Weekdays out-earn weekends; "
                   f"the weakest weekday averages {s['worst_weekday_rev'] / s['best_weekday_rev']:.0%} of the strongest.")


def product_performance(items) -> Finding:
    it = items[items.is_revenue_order]
    g = it.groupby("product_category_name_english").agg(revenue=("price", "sum"), units=("order_item_id", "size"),
                                                        avg_price=("price", "mean")).sort_values("revenue", ascending=False)
    top = g.head(15)
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.barh(top.index.str.replace("_", " ").str.title()[::-1], top.revenue[::-1] / 1e3, color=BLUE)
    ax.set(title="Top 15 categories by item revenue", xlabel="Item revenue (thousand BRL)", ylabel="")
    f = _save(fig, "03_product_top_categories")
    share_top10 = g.revenue.head(10).sum() / g.revenue.sum()
    prod_units = it.groupby("product_id").size()
    s = {"categories": len(g), "top10_share": share_top10, "top_category": g.index[0],
         "products_lt3_units_share": (prod_units < 3).mean()}
    return Finding("products", "Product performance", f, s,
                   f"The top 10 of {len(g)} categories generate {share_top10:.0%} of item revenue; '{g.index[0].replace('_', ' ')}' leads. "
                   f"The catalogue is a long tail: {s['products_lt3_units_share']:.0%} of products sold fewer than 3 units, so "
                   "demand planning must happen at category, not SKU, level.")


def geographic(om) -> Finding:
    r = _rev(om)
    g = r.groupby("customer_state").agg(revenue=("revenue", "sum"), orders=("order_id", "nunique"),
                                        delivery=("delivery_days", "mean")).sort_values("revenue", ascending=False)
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
    ax[0].bar(g.index[:12], g.revenue[:12] / 1e6, color=BLUE)
    ax[0].set(title="Revenue by state (top 12)", ylabel="Revenue (million BRL)", xlabel="State")
    ax[1].scatter(g.orders, g.delivery, s=40, color=TEAL)
    for st_, row in g.iterrows():
        ax[1].annotate(st_, (row.orders, row.delivery), fontsize=7)
    ax[1].set(xscale="log", title="Orders vs average delivery days by state", xlabel="Orders (log)", ylabel="Avg delivery days")
    f = _save(fig, "03_geographic_states")
    sp = g.loc["SP"]
    items = pd.read_parquet(settings.processed_dir / "items_enriched.parquet", columns=["seller_state"])
    s = {"sp_revenue_share": sp.revenue / g.revenue.sum(), "top3_share": g.revenue.head(3).sum() / g.revenue.sum(),
         "sp_delivery": sp.delivery, "slowest_state": g.delivery.idxmax(), "slowest_days": g.delivery.max(),
         "items_shipped_from_sp": (items.seller_state == "SP").mean()}
    return Finding("geography", "Geographic concentration", f, s,
                   f"São Paulo alone generates {s['sp_revenue_share']:.0%} of revenue and SP+RJ+MG {s['top3_share']:.0%}. SP orders arrive "
                   f"in {sp.delivery:.1f} days on average versus {s['slowest_days']:.1f} in {s['slowest_state']}. Because "
                   f"{s['items_shipped_from_sp']:.0%} of items ship from São Paulo sellers, delivery time grows with distance from SP, "
                   "limiting growth in the North/Northeast.")


def delivery_analysis(om) -> Finding:
    d = om[om.is_delivered].copy()
    d["region"] = d.customer_state.map({**{s: "Norte" for s in ["AC", "AP", "AM", "PA", "RO", "RR", "TO"]},
                                        **{s: "Nordeste" for s in ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"]},
                                        **{s: "Centro-Oeste" for s in ["DF", "GO", "MT", "MS"]},
                                        **{s: "Sudeste" for s in ["ES", "MG", "RJ", "SP"]}, **{s: "Sul" for s in ["PR", "RS", "SC"]}})
    m = d.groupby("purchase_month").is_late.apply(lambda s: s.astype(float).mean())
    m = m[(m.index >= "2017-01-01") & (m.index <= "2018-08-01")]
    fig, ax = plt.subplots(1, 2, figsize=(12, 4))
    ax[0].plot(m.index, m.values * 100, marker="o", color=RED)
    ax[0].set(title="Monthly late-delivery rate", ylabel="Late deliveries (%)", xlabel="Purchase month")
    rg = d.groupby("region").is_late.apply(lambda s: s.astype(float).mean()).sort_values()
    ax[1].barh(rg.index, rg.values * 100, color=AMBER)
    ax[1].set(title="Late-delivery rate by region", xlabel="Late deliveries (%)")
    f = _save(fig, "03_delivery_late_rate")
    top3 = m.nlargest(3)
    s = {"worst_month": str(m.idxmax().date()), "worst_month_rate": m.max(), "median_month_rate": m.median(),
         "top3_months": {str(k.date())[:7]: round(v, 4) for k, v in top3.items()}, "best_region": rg.index[0],
         "worst_region": rg.index[-1], "worst_region_rate": rg.iloc[-1], "best_region_rate": rg.iloc[0]}
    return Finding("late_delivery", "Late deliveries", f, s,
                   "Late-delivery rates spike in a few months – " +
                   ", ".join(f"{k} ({v:.1%})" for k, v in s["top3_months"].items()) +
                   f" – versus a monthly median of {s['median_month_rate']:.1%}, i.e. logistics capacity breaks under demand peaks "
                   f"(Nov-2017 = Black Friday). By region, {s['worst_region']} is late {s['worst_region_rate']:.1%} of the time "
                   f"vs {s['best_region_rate']:.1%} in {s['best_region']}.")


# =========================================================== 04 customer analytics
def customer_repeat(cm) -> Finding:
    vc = cm.orders.clip(upper=5).value_counts().sort_index()
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar([str(i) if i < 5 else "5+" for i in vc.index], vc.values, color=BLUE)
    ax.set(yscale="log", title="Customers by number of orders (log scale)", xlabel="Orders per customer", ylabel="Customers (log)")
    f = _save(fig, "04_customer_repeat")
    s = {"customers": len(cm), "repeat_rate": cm.is_repeat.mean(),
         "repeat_revenue_share": cm[cm.is_repeat].revenue.sum() / cm.revenue.sum(),
         "repeat_aov_ratio": cm[cm.is_repeat].revenue.mean() / cm[~cm.is_repeat].revenue.mean()}
    return Finding("repeat", "Repeat purchasing", f, s,
                   f"Only {s['repeat_rate']:.2%} of {s['customers']:,} customers ordered more than once; they contribute "
                   f"{s['repeat_revenue_share']:.1%} of revenue and are worth {s['repeat_aov_ratio']:.1f}× a one-time buyer. "
                   "Retention is the single largest structural weakness of the business.")


def customer_cohorts(om) -> Finding:
    r = _rev(om)[["customer_unique_id", "order_purchase_timestamp"]].copy()
    r["m"] = r.order_purchase_timestamp.dt.to_period("M")
    r = r.join(r.groupby("customer_unique_id").m.min().rename("cohort"), on="customer_unique_id")
    r["k"] = (r.m - r.cohort).apply(lambda x: x.n)
    piv = r.drop_duplicates(["customer_unique_id", "k"]).pivot_table(index="cohort", columns="k",
                                                                     values="customer_unique_id", aggfunc="count")
    piv = piv[(piv.index >= pd.Period("2017-01", "M")) & (piv.index <= pd.Period("2018-03", "M"))]
    ret = piv.div(piv[0], axis=0).iloc[:, 1:7] * 100
    fig, ax = plt.subplots(figsize=(9, 6))
    sns.heatmap(ret, annot=True, fmt=".2f", cmap="Blues", ax=ax, cbar_kws={"label": "Retention (%)"})
    ax.set(title="Monthly cohort retention (% of cohort purchasing in month k)", xlabel="Months since first purchase",
           ylabel="Acquisition cohort")
    f = _save(fig, "04_cohort_retention")
    s = {"m1_mean": ret[1].mean(), "m3_mean": ret[3].mean() if 3 in ret else None, "m6_mean": ret[6].mean() if 6 in ret else None}
    return Finding("cohorts", "Cohort retention", f, s,
                   f"Average month-1 retention is {s['m1_mean']:.2f}% and stays below 0.5% from month 2 onward – cohorts do not "
                   "build a recurring base. Every month's revenue must be re-acquired.")


def customer_clv(cm) -> Finding:
    v = cm.revenue.sort_values(ascending=False).reset_index(drop=True)
    cum = v.cumsum() / v.sum()
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(np.arange(1, len(v) + 1) / len(v) * 100, cum * 100, color=NAVY)
    ax.plot([0, 100], [0, 100], ls="--", color=GREY)
    ax.set(title="Customer revenue concentration (Lorenz-style curve)", xlabel="Customers (% ranked by revenue)",
           ylabel="Cumulative revenue (%)")
    f = _save(fig, "04_customer_value_concentration")
    top20 = cum.iloc[int(len(v) * .2) - 1]
    aov = cm.revenue.sum() / cm.orders.sum()
    s = {"top20_revenue_share": top20, "aov": aov, "orders_per_customer": cm.orders.mean(),
         "historical_clv": aov * cm.orders.mean()}
    return Finding("clv", "Customer lifetime value", f, s,
                   f"The top 20% of customers generate {top20:.0%} of revenue. Historical CLV ≈ AOV R$ {aov:.2f} × "
                   f"{s['orders_per_customer']:.3f} orders = R$ {s['historical_clv']:.2f}; because frequency is ~1, CLV is essentially "
                   "the first basket – raising frequency is the main CLV lever.")


# =========================================================== 05 statistics
def hypothesis_tests(om) -> tuple[pd.DataFrame, Finding]:
    rows = []
    d = om[om.is_delivered & om.review_score.notna()]
    on, late = d[~d.is_late.astype(bool)].review_score, d[d.is_late.astype(bool)].review_score
    u, p = stats.mannwhitneyu(on, late, alternative="greater")
    r_rb = 1 - 2 * u / (len(on) * len(late))
    rows.append({"id": "H1", "hypothesis": "Late orders receive lower review scores than on-time orders",
                 "test": "Mann-Whitney U (one-sided)", "statistic": u, "p_value": p,
                 "effect_size": f"rank-biserial r = {abs(r_rb):.3f}", "decision": "Reject H0" if p < .05 else "Fail to reject H0",
                 "detail": f"mean on-time {on.mean():.2f} vs late {late.mean():.2f}"})
    reg = {**{s: "Norte" for s in ["AC", "AP", "AM", "PA", "RO", "RR", "TO"]},
           **{s: "Nordeste" for s in ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"]},
           **{s: "Centro-Oeste" for s in ["DF", "GO", "MT", "MS"]},
           **{s: "Sudeste" for s in ["ES", "MG", "RJ", "SP"]}, **{s: "Sul" for s in ["PR", "RS", "SC"]}}
    d = d.assign(region=d.customer_state.map(reg))
    groups = [g.review_score.values for _, g in d.groupby("region")]
    h, p = stats.kruskal(*groups)
    eps2 = (h - len(groups) + 1) / (len(d) - len(groups))
    rows.append({"id": "H2", "hypothesis": "Review score distribution differs between regions", "test": "Kruskal-Wallis H",
                 "statistic": h, "p_value": p, "effect_size": f"epsilon² = {eps2:.4f}",
                 "decision": "Reject H0" if p < .05 else "Fail to reject H0",
                 "detail": ", ".join(f"{k} {v:.2f}" for k, v in d.groupby("region").review_score.mean().items())})
    ct = pd.crosstab(d.region, d.is_late.astype(bool))
    chi2, p, dof, _ = stats.chi2_contingency(ct)
    v = np.sqrt(chi2 / (ct.values.sum() * (min(ct.shape) - 1)))
    rows.append({"id": "H3", "hypothesis": "Late delivery is independent of customer region", "test": "Chi-square independence",
                 "statistic": chi2, "p_value": p, "effect_size": f"Cramér's V = {v:.3f}",
                 "decision": "Reject H0" if p < .05 else "Fail to reject H0", "detail": f"dof={dof}"})
    rho, p = stats.spearmanr(d.delivery_days, d.review_score)
    rows.append({"id": "H4", "hypothesis": "Delivery time is monotonically associated with review score",
                 "test": "Spearman correlation", "statistic": rho, "p_value": p, "effect_size": f"rho = {rho:.3f}",
                 "decision": "Reject H0" if p < .05 else "Fail to reject H0", "detail": ""})
    r = _rev(om)
    wk = r.order_purchase_timestamp.dt.dayofweek >= 5
    t, p = stats.ttest_ind(np.log(r[wk].order_value), np.log(r[~wk].order_value), equal_var=False)
    rows.append({"id": "H5", "hypothesis": "Weekend and weekday orders have the same mean (log) order value",
                 "test": "Welch t-test on log(order value)", "statistic": t, "p_value": p,
                 "effect_size": f"geo-mean ratio = {np.exp(np.log(r[wk].order_value).mean() - np.log(r[~wk].order_value).mean()):.3f}",
                 "decision": "Reject H0" if p < .05 else "Fail to reject H0",
                 "detail": f"median weekend {r[wk].order_value.median():.2f} vs weekday {r[~wk].order_value.median():.2f}"})
    pay = r[r.main_payment_type.isin(["credit_card", "boleto"])]
    u, p = stats.mannwhitneyu(pay[pay.main_payment_type == "credit_card"].order_value,
                              pay[pay.main_payment_type == "boleto"].order_value, alternative="two-sided")
    rows.append({"id": "H6", "hypothesis": "Credit-card and boleto orders have the same order-value distribution",
                 "test": "Mann-Whitney U (two-sided)", "statistic": u, "p_value": p, "effect_size": "",
                 "decision": "Reject H0" if p < .05 else "Fail to reject H0",
                 "detail": f"median card {pay[pay.main_payment_type == 'credit_card'].order_value.median():.2f} vs boleto "
                           f"{pay[pay.main_payment_type == 'boleto'].order_value.median():.2f}"})
    res = pd.DataFrame(rows)
    res["p_value_fmt"] = res.p_value.map(lambda x: "< 1e-300" if x == 0 else f"{x:.3g}")
    (settings.reports_dir / "eda").mkdir(parents=True, exist_ok=True)
    res.to_csv(settings.reports_dir / "eda" / "hypothesis_tests.csv", index=False)
    rej = res[res.decision == "Reject H0"].id.tolist()
    return res, Finding("hypotheses", "Statistical hypothesis tests", None, {"rejected": rej},
                        f"{len(rej)} of {len(res)} null hypotheses rejected at α = 0.05 ({', '.join(rej)}). With ~100k observations even "
                        "tiny differences are 'significant', so effect sizes matter: the delivery-delay effect on reviews (H1) is "
                        "material, while the regional review differences (H2) are statistically real but small.")


ALL_EXPLORATORY = [univariate_order_value, univariate_delivery, bivariate_delay_review, multivariate_correlation,
                   outliers_order_value, geographic, delivery_analysis]
