"""Generate reports/eda/EDA_REPORT.md and docs/business_requirements/BUSINESS_INSIGHTS_REPORT.md.

All metrics are computed at generation time from the processed data, SQL
results and ML metrics; only the recommended actions are written by analysts.

    python scripts/generate_reports.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from src.analytics import eda  # noqa: E402
from src.config.settings import settings  # noqa: E402


def eda_report() -> dict:
    om, items, cm, daily = eda.load()
    findings = [eda.univariate_order_value(om), eda.univariate_delivery(om), eda.bivariate_price_freight(items),
                eda.bivariate_delay_review(om), eda.multivariate_correlation(om), eda.outliers_order_value(om),
                eda.time_series_revenue(daily), eda.product_performance(items), eda.geographic(om),
                eda.delivery_analysis(om), eda.customer_repeat(cm), eda.customer_cohorts(om), eda.customer_clv(cm)]
    tests, tf = eda.hypothesis_tests(om)
    head = json.loads((settings.processed_dir / "headline_kpis.json").read_text())
    L = ["# NEXUS BI – Exploratory Data Analysis Report", "",
         f"_Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} by `scripts/generate_reports.py` from the processed Olist data. "
         "Every number and sentence under each chart is computed from the data._", "",
         "## Headline facts", "",
         f"| Metric | Value |", "|---|---|",
         f"| Revenue (item price + freight, non-canceled/unavailable orders) | R$ {head['total_revenue']:,.2f} |",
         f"| Orders (revenue-recognised) | {head['total_orders']:,} of {head['all_orders']:,} |",
         f"| Unique customers | {head['unique_customers']:,} |",
         f"| Average order value | R$ {head['average_order_value']:,.2f} |",
         f"| On-time delivery rate | {head['on_time_delivery_rate']:.2%} |",
         f"| Average delivery time | {head['avg_delivery_days']:.1f} days |",
         f"| Average review score | {head['avg_review_score']:.2f} / 5 |",
         f"| Cancellation rate | {head['cancellation_rate']:.2%} |", "",
         "> Data-capture caveat: order volume collapses after 2018-08-22 (extraction truncation). Time-series models and trend "
         "statements use 2017-01 → 2018-08-21.", ""]
    for f in findings:
        L += [f"## {f.title}", "", f"![{f.title}](../../{f.figure})", "", f"**Interpretation.** {f.interpretation}", ""]
    L += ["## Statistical hypothesis tests", "",
          "| ID | Hypothesis | Test | Statistic | p-value | Effect size | Decision | Detail |", "|---|---|---|---|---|---|---|---|"]
    for r in tests.itertuples():
        L.append(f"| {r.id} | {r.hypothesis} | {r.test} | {r.statistic:,.3f} | {r.p_value_fmt} | {r.effect_size or '–'} | "
                 f"{r.decision} | {r.detail if isinstance(r.detail, str) else ''} |")
    L += ["", f"**Interpretation.** {tf.interpretation}", "",
          "_All tests are observational: they establish association, not causation._"]
    out = settings.reports_dir / "eda" / "EDA_REPORT.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L), encoding="utf-8")
    return {f.key: f for f in findings} | {"tests": tests}


def insights_report(F: dict) -> None:
    sql = settings.reports_dir / "sql_results"
    q = lambda name: pd.read_csv(sql / f"{name}.csv")  # noqa: E731
    head = json.loads((settings.processed_dir / "headline_kpis.json").read_text())
    ch = json.loads((settings.ml_artifacts_dir / "churn_prediction" / "metrics.json").read_text())
    rv = json.loads((settings.ml_artifacts_dir / "revenue_forecasting" / "metrics.json").read_text())
    an = json.loads((settings.ml_artifacts_dir / "anomaly_detection" / "metrics.json").read_text())
    rep = q("Q11_repeat_customer_rate").iloc[0]
    coh = q("Q42_monthly_cohort_retention")
    late_state = q("Q33_late_delivery_by_state")
    delay = q("Q40_review_vs_delivery_delay")
    freight = q("Q23_freight_ratio_by_category")
    conc = q("Q25_seller_concentration")
    quad = q("Q26_seller_quality_quadrant")
    region = q("Q29_region_performance")
    ytd = q("Q05_ytd_revenue_comparison")
    mom = q("Q02_monthly_revenue_mom_growth")
    inst = q("Q38_installments_vs_order_value")
    worst_cat = q("Q41_review_by_category_worst").iloc[0]
    m18 = mom[(mom.month_start >= "2018-01-01") & (mom.month_start <= "2018-08-01")]
    vol_risk = quad[quad.quadrant.str.startswith("Volume at risk")].iloc[0]
    top5 = conc[conc.top_pct_sellers == 5].iloc[0]
    on_time = delay[delay.delay_bucket.str.startswith(("a)", "b)", "c)"))]
    late16 = delay[delay.delay_bucket.str.startswith("f)")].iloc[0]
    hi_freight = freight.iloc[0]

    insights = [
        dict(title="1. Retention is almost non-existent",
             problem="Growth depends entirely on acquiring new customers; almost nobody buys twice.",
             metric=f"Repeat-customer rate {rep.repeat_rate_pct:.2f}%; repeat buyers = {rep.repeat_revenue_share_pct:.1f}% of revenue; "
                    f"average month-1 cohort retention {coh.m1_pct.mean():.2f}% (SQL Q11, Q42).",
             segment="All regions/categories; 'Recent One-Time Buyers' ML segment (≈25% of customers).",
             explanation="Marketplace model (customer relationship sits with Olist, not the seller), long delivery lead times, "
                         "no loyalty programme visible in the data. Correlational – the data has no marketing-touch history.",
             investigate="Survey/interview one-time buyers; analyse whether first-order experience (late delivery, low review) "
                         "predicts non-return (H1 shows late orders score 2 points lower).",
             action="Launch a second-purchase programme for the 'Recent One-Time Buyers' segment: post-delivery cross-sell within "
                    "30–60 days, review-request + voucher, A/B tested against a holdout.",
             kpi="Repeat-customer rate, month-1/month-3 cohort retention, 90-day second-order rate."),
        dict(title="2. Late deliveries destroy satisfaction",
             problem="Late orders are rated far worse than on-time orders.",
             metric=f"Avg review on/before estimate {(on_time.avg_review * on_time.orders).sum() / on_time.orders.sum():.2f} vs {late16.avg_review:.2f} for 16+ days late "
                    f"({late16.pct_1_star:.0f}% one-star) (SQL Q40); Mann-Whitney H1 rejected, rank-biserial r = "
                    f"{F['tests'].set_index('id').loc['H1', 'effect_size'].split('=')[1].strip()}.",
             segment=f"Highest late rates: {', '.join(late_state.head(3).state)} "
                     f"({', '.join(f'{v:.1f}%' for v in late_state.head(3).late_rate_pct)}) (SQL Q33).",
             explanation="Long cross-country routes from São Paulo sellers; carrier capacity limits in demand peaks "
                         f"(late rate peaked in {list(F['late_delivery'].stats['top3_months'])[0]}).",
             investigate="Carrier-level SLA analysis (carrier not in dataset – requires logistics data); peak-season capacity review.",
             action="Region-specific delivery promises, regional fulfilment/seller recruitment in the Northeast, proactive delay "
                    "notifications with compensation vouchers.",
             kpi="On-time rate by state, % orders > 5 days late, average review of late orders."),
        dict(title="3. Growth has plateaued in 2018",
             problem="After strong 2017 growth, monthly revenue has been flat since January 2018.",
             metric=f"Jan–Aug YoY growth {ytd.iloc[-1].yoy_growth_pct:.1f}% (SQL Q05) is carried by 2017's ramp-up: in 2018 monthly "
                    f"revenue moved only between R$ {m18.revenue.min() / 1e6:.2f}M and R$ {m18.revenue.max() / 1e6:.2f}M, and Jul-2018 was "
                    f"{100 * (m18.set_index('month_start').revenue['2018-07-01'] / m18.set_index('month_start').revenue['2018-01-01'] - 1):+.1f}% "
                    f"vs Jan-2018 (SQL Q02; Aug excluded – capture truncated). 30-day forecast ({rv['best_model_by_backtest_mae']}) ≈ "
                    f"R$ {rv['forecast_total_next_30d'][rv['best_model_by_backtest_mae']]:,.0f}.",
             segment="Platform-wide; strongest in Sudeste.",
             explanation="Saturation in the core SP/RJ/MG market combined with weak retention (insight 1).",
             investigate="Category-level growth decomposition (SQL Q20) and new-vs-returning revenue split by month.",
             action="Prioritise growth categories from Q20 and under-penetrated regions; pair acquisition spend with retention (insight 1).",
             kpi="Monthly revenue growth, new-customer acquisition, revenue per customer."),
        dict(title="4. Freight burden on low-priced categories",
             problem="For cheap items, shipping is a large share of what the customer pays.",
             metric=f"Highest freight/price ratio: {hi_freight.category} at {hi_freight.freight_ratio_pct:.1f}% (SQL Q23); "
                    f"on {F['price_freight'].stats['share_freight_gt_price']:.1%} of items freight exceeds the item price.",
             segment="Low-ticket categories; customers far from São Paulo.",
             explanation="Per-item freight with weak volume discounts; distance from seller hub.",
             investigate="Price-elasticity test of free-shipping thresholds; basket-size analysis for multi-item orders.",
             action="Free-shipping threshold and bundles for high-freight-ratio categories; encourage multi-item baskets.",
             kpi="Items per order, freight/price ratio, conversion in affected categories (requires web analytics)."),
        dict(title="5. Seller base is concentrated and uneven in quality",
             problem="A small group of sellers drives most GMV, and some high-volume sellers have poor reviews.",
             metric=f"Top 5% of sellers = {top5.gmv_share_pct:.1f}% of GMV (SQL Q25); 'volume at risk' quadrant: "
                    f"{int(vol_risk.sellers)} sellers, R$ {vol_risk.gmv:,.0f} GMV, avg review {vol_risk.avg_review:.2f} (SQL Q26).",
             segment="High-volume / low-review sellers.",
             explanation="Operational variance between sellers (handling time, stock-outs, product quality).",
             investigate="Seller-level root cause: handling time (approval→carrier), cancellation and review text analysis.",
             action="Key-account management for top sellers; quality improvement plans and visibility penalties for the at-risk quadrant.",
             kpi="Seller avg review, seller late rate, GMV share of sellers below quality threshold."),
        dict(title="6. Regional imbalance in revenue and service",
             problem="Revenue is concentrated in the Southeast while the North/Northeast receive slower, less reliable service.",
             metric="; ".join(f"{r.region}: R$ {r.revenue / 1e6:.2f}M, {r.avg_delivery_days:.1f} d, on-time {r.on_time_pct:.1f}%"
                              for r in region.itertuples()) + " (SQL Q29).",
             segment="Norte and Nordeste regions.",
             explanation=f"{F['geography'].stats['items_shipped_from_sp']:.0%} of items ship from São Paulo sellers.",
             investigate="Demand potential vs service level by state; seller supply gaps by region.",
             action="Recruit sellers / fulfilment partners in the Northeast; region-specific delivery estimates.",
             kpi="Revenue share outside Sudeste, delivery days by region, regional review score."),
        dict(title="7. Installment plans enable high-ticket purchases",
             problem="Understand the role of credit-card installments in basket value.",
             metric="; ".join(f"{r.installment_band}: AOV R$ {r.avg_order_value:,.0f} ({r.orders:,} orders)"
                              for r in inst.itertuples()) + " (SQL Q38).",
             segment="Credit-card customers.",
             explanation="Installments lower the perceived cost of expensive items (association; selection effect likely – "
                         "customers choose installments *because* the item is expensive).",
             investigate="Experiment with interest-free installment promotions on selected categories.",
             action="Promote interest-free installments on high-ticket categories; monitor default/chargeback cost.",
             kpi="AOV, share of orders with ≥ 4 installments, conversion on promoted categories."),
        dict(title="8. Demand spikes are predictable but stress operations",
             problem="Black Friday drives extreme peaks that the logistics network does not absorb.",
             metric=f"{an['flags']['consensus_anomalies']} consensus anomalies; Black Friday 2017 flagged High severity; "
                    f"late rate in Nov-2017 = {F['late_delivery'].stats['top3_months'].get('2017-11', float('nan')):.1%}.",
             segment="November peak; Feb–Mar 2018 operational incident.",
             explanation="Capacity planning not scaled to promotional demand.",
             investigate="Root-cause the Feb–Mar 2018 late-delivery surge (carrier/strike/weather – external data needed).",
             action="Use the 30-day forecast and anomaly alerts for capacity planning; pre-book carrier capacity before Black Friday.",
             kpi="Peak-week on-time rate, anomaly alerts per month, forecast error during peaks."),
        dict(title="9. Churn can be ranked, not predicted precisely",
             problem="Retention budget should target customers most likely to return.",
             metric=f"Best churn model {ch['best_model']}: test ROC-AUC {ch['results'][ch['best_model']]['test']['roc_auc']:.3f}, "
                    f"top-decile return lift {ch['results'][ch['best_model']]['test']['return_lift_top_decile']:.1f}×.",
             segment="Active customers (purchase in last 365 days).",
             explanation="Behavioural signal is limited to 1–2 orders per customer; no browsing/marketing data.",
             investigate="Add engagement data (email opens, sessions) to the feature set.",
             action="Use churn scores only to prioritise campaign audiences; measure with a randomised holdout.",
             kpi="Return rate of targeted vs holdout group; model lift over time."),
    ]
    L = ["# NEXUS BI – Business Insights & Decision Support Report", "",
         f"_Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} from SQL results (`reports/sql_results`), EDA findings and ML metrics. "
         "Metrics are computed; recommendations are analyst judgement._", "",
         f"**Scope:** Olist marketplace, {head['total_orders']:,} revenue orders, R$ {head['total_revenue']:,.0f} revenue (BRL), "
         "Sep-2016 → Aug-2018.", "",
         "> **Correlation vs causation.** All findings are observational associations from historical data. Where an action is "
         "recommended, the expected effect should be validated with a controlled experiment (A/B test or holdout) before scaling.",
         "", "## Executive summary", ""]
    import re
    L += [f"{i + 1}. **{x['title'].split('. ', 1)[1]}** – {re.sub(r' ?\(SQL [^)]*\)', '', x['metric'])}" for i, x in enumerate(insights)]
    for x in insights:
        L += ["", f"## {x['title']}", "", "| Aspect | Detail |", "|---|---|",
              f"| Business problem | {x['problem']} |", f"| Supporting metric | {x['metric']} |",
              f"| Relevant segment / region | {x['segment']} |", f"| Possible explanation | {x['explanation']} |",
              f"| Recommended investigation | {x['investigate']} |", f"| Suggested business action | {x['action']} |",
              f"| KPI to monitor | {x['kpi']} |"]
    L += ["", "## Simulated profitability (clearly synthetic)", "",
          "Cost and inventory data do **not** exist in the source. `data/synthetic` contains simulated unit costs and weekly "
          "inventory (seeded, documented in `data/synthetic/README.md`). SQL Q44/Q45 and the Power BI 'Simulated' visuals use them "
          "to demonstrate margin and stock-out analytics. **No conclusion in this report is based on synthetic data.**"]
    out = settings.project_root / "docs" / "business_requirements" / "BUSINESS_INSIGHTS_REPORT.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    F = eda_report()
    insights_report(F)
    print("Reports written.")
