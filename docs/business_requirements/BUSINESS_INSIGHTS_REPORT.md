# NEXUS BI – Business Insights & Decision Support Report

_Generated 2026-11-12 15:16 UTC from SQL results (`reports/sql_results`), EDA findings and ML metrics. Metrics are computed; recommendations are analyst judgement._

**Scope:** Olist marketplace, 98,207 revenue orders, R$ 15,735,527 revenue (BRL), Sep-2016 → Aug-2018.

> **Correlation vs causation.** All findings are observational associations from historical data. Where an action is recommended, the expected effect should be validated with a controlled experiment (A/B test or holdout) before scaling.

## Executive summary

1. **Retention is almost non-existent** – Repeat-customer rate 3.04%; repeat buyers = 5.7% of revenue; average month-1 cohort retention 0.48%.
2. **Late deliveries destroy satisfaction** – Avg review on/before estimate 4.29 vs 1.73 for 16+ days late (69% one-star); Mann-Whitney H1 rejected, rank-biserial r = 0.638.
3. **Growth has plateaued in 2018** – Jan–Aug YoY growth 140.4% is carried by 2017's ramp-up: in 2018 monthly revenue moved only between R$ 0.98M and R$ 1.16M, and Jul-2018 was -5.6% vs Jan-2018. 30-day forecast (ensemble_mean) ≈ R$ 1,106,436.
4. **Freight burden on low-priced categories** – Highest freight/price ratio: Electronics at 29.5%; on 3.7% of items freight exceeds the item price.
5. **Seller base is concentrated and uneven in quality** – Top 5% of sellers = 53.3% of GMV; 'volume at risk' quadrant: 171 sellers, R$ 4,371,314 GMV, avg review 3.89.
6. **Regional imbalance in revenue and service** – Sudeste: R$ 10.16M, 10.8 d, on-time 93.9%; Sul: R$ 2.28M, 14.0 d, on-time 94.1%; Nordeste: R$ 1.87M, 20.0 d, on-time 87.3%; Centro-Oeste: R$ 1.01M, 15.0 d, on-time 93.5%; Norte: R$ 0.41M, 22.6 d, on-time 91.4%.
7. **Installment plans enable high-ticket purchases** – 1 (single): AOV R$ 101 (25,335 orders); 2-3: AOV R$ 135 (22,792 orders); 4-6: AOV R$ 181 (16,205 orders); 7-10: AOV R$ 332 (11,832 orders); 11+: AOV R$ 355 (341 orders).
8. **Demand spikes are predictable but stress operations** – 7 consensus anomalies; Black Friday 2017 flagged High severity; late rate in Nov-2017 = 12.4%.
9. **Churn can be ranked, not predicted precisely** – Best churn model random_forest: test ROC-AUC 0.582, top-decile return lift 2.0×.

## 1. Retention is almost non-existent

| Aspect | Detail |
|---|---|
| Business problem | Growth depends entirely on acquiring new customers; almost nobody buys twice. |
| Supporting metric | Repeat-customer rate 3.04%; repeat buyers = 5.7% of revenue; average month-1 cohort retention 0.48% (SQL Q11, Q42). |
| Relevant segment / region | All regions/categories; 'Recent One-Time Buyers' ML segment (≈25% of customers). |
| Possible explanation | Marketplace model (customer relationship sits with Olist, not the seller), long delivery lead times, no loyalty programme visible in the data. Correlational – the data has no marketing-touch history. |
| Recommended investigation | Survey/interview one-time buyers; analyse whether first-order experience (late delivery, low review) predicts non-return (H1 shows late orders score 2 points lower). |
| Suggested business action | Launch a second-purchase programme for the 'Recent One-Time Buyers' segment: post-delivery cross-sell within 30–60 days, review-request + voucher, A/B tested against a holdout. |
| KPI to monitor | Repeat-customer rate, month-1/month-3 cohort retention, 90-day second-order rate. |

## 2. Late deliveries destroy satisfaction

| Aspect | Detail |
|---|---|
| Business problem | Late orders are rated far worse than on-time orders. |
| Supporting metric | Avg review on/before estimate 4.29 vs 1.73 for 16+ days late (69% one-star) (SQL Q40); Mann-Whitney H1 rejected, rank-biserial r = 0.638. |
| Relevant segment / region | Highest late rates: MA, CE, BA (17.4%, 13.8%, 12.2%) (SQL Q33). |
| Possible explanation | Long cross-country routes from São Paulo sellers; carrier capacity limits in demand peaks (late rate peaked in 2018-03). |
| Recommended investigation | Carrier-level SLA analysis (carrier not in dataset – requires logistics data); peak-season capacity review. |
| Suggested business action | Region-specific delivery promises, regional fulfilment/seller recruitment in the Northeast, proactive delay notifications with compensation vouchers. |
| KPI to monitor | On-time rate by state, % orders > 5 days late, average review of late orders. |

## 3. Growth has plateaued in 2018

| Aspect | Detail |
|---|---|
| Business problem | After strong 2017 growth, monthly revenue has been flat since January 2018. |
| Supporting metric | Jan–Aug YoY growth 140.4% (SQL Q05) is carried by 2017's ramp-up: in 2018 monthly revenue moved only between R$ 0.98M and R$ 1.16M, and Jul-2018 was -5.6% vs Jan-2018 (SQL Q02; Aug excluded – capture truncated). 30-day forecast (ensemble_mean) ≈ R$ 1,106,436. |
| Relevant segment / region | Platform-wide; strongest in Sudeste. |
| Possible explanation | Saturation in the core SP/RJ/MG market combined with weak retention (insight 1). |
| Recommended investigation | Category-level growth decomposition (SQL Q20) and new-vs-returning revenue split by month. |
| Suggested business action | Prioritise growth categories from Q20 and under-penetrated regions; pair acquisition spend with retention (insight 1). |
| KPI to monitor | Monthly revenue growth, new-customer acquisition, revenue per customer. |

## 4. Freight burden on low-priced categories

| Aspect | Detail |
|---|---|
| Business problem | For cheap items, shipping is a large share of what the customer pays. |
| Supporting metric | Highest freight/price ratio: Electronics at 29.5% (SQL Q23); on 3.7% of items freight exceeds the item price. |
| Relevant segment / region | Low-ticket categories; customers far from São Paulo. |
| Possible explanation | Per-item freight with weak volume discounts; distance from seller hub. |
| Recommended investigation | Price-elasticity test of free-shipping thresholds; basket-size analysis for multi-item orders. |
| Suggested business action | Free-shipping threshold and bundles for high-freight-ratio categories; encourage multi-item baskets. |
| KPI to monitor | Items per order, freight/price ratio, conversion in affected categories (requires web analytics). |

## 5. Seller base is concentrated and uneven in quality

| Aspect | Detail |
|---|---|
| Business problem | A small group of sellers drives most GMV, and some high-volume sellers have poor reviews. |
| Supporting metric | Top 5% of sellers = 53.3% of GMV (SQL Q25); 'volume at risk' quadrant: 171 sellers, R$ 4,371,314 GMV, avg review 3.89 (SQL Q26). |
| Relevant segment / region | High-volume / low-review sellers. |
| Possible explanation | Operational variance between sellers (handling time, stock-outs, product quality). |
| Recommended investigation | Seller-level root cause: handling time (approval→carrier), cancellation and review text analysis. |
| Suggested business action | Key-account management for top sellers; quality improvement plans and visibility penalties for the at-risk quadrant. |
| KPI to monitor | Seller avg review, seller late rate, GMV share of sellers below quality threshold. |

## 6. Regional imbalance in revenue and service

| Aspect | Detail |
|---|---|
| Business problem | Revenue is concentrated in the Southeast while the North/Northeast receive slower, less reliable service. |
| Supporting metric | Sudeste: R$ 10.16M, 10.8 d, on-time 93.9%; Sul: R$ 2.28M, 14.0 d, on-time 94.1%; Nordeste: R$ 1.87M, 20.0 d, on-time 87.3%; Centro-Oeste: R$ 1.01M, 15.0 d, on-time 93.5%; Norte: R$ 0.41M, 22.6 d, on-time 91.4% (SQL Q29). |
| Relevant segment / region | Norte and Nordeste regions. |
| Possible explanation | 71% of items ship from São Paulo sellers. |
| Recommended investigation | Demand potential vs service level by state; seller supply gaps by region. |
| Suggested business action | Recruit sellers / fulfilment partners in the Northeast; region-specific delivery estimates. |
| KPI to monitor | Revenue share outside Sudeste, delivery days by region, regional review score. |

## 7. Installment plans enable high-ticket purchases

| Aspect | Detail |
|---|---|
| Business problem | Understand the role of credit-card installments in basket value. |
| Supporting metric | 1 (single): AOV R$ 101 (25,335 orders); 2-3: AOV R$ 135 (22,792 orders); 4-6: AOV R$ 181 (16,205 orders); 7-10: AOV R$ 332 (11,832 orders); 11+: AOV R$ 355 (341 orders) (SQL Q38). |
| Relevant segment / region | Credit-card customers. |
| Possible explanation | Installments lower the perceived cost of expensive items (association; selection effect likely – customers choose installments *because* the item is expensive). |
| Recommended investigation | Experiment with interest-free installment promotions on selected categories. |
| Suggested business action | Promote interest-free installments on high-ticket categories; monitor default/chargeback cost. |
| KPI to monitor | AOV, share of orders with ≥ 4 installments, conversion on promoted categories. |

## 8. Demand spikes are predictable but stress operations

| Aspect | Detail |
|---|---|
| Business problem | Black Friday drives extreme peaks that the logistics network does not absorb. |
| Supporting metric | 7 consensus anomalies; Black Friday 2017 flagged High severity; late rate in Nov-2017 = 12.4%. |
| Relevant segment / region | November peak; Feb–Mar 2018 operational incident. |
| Possible explanation | Capacity planning not scaled to promotional demand. |
| Recommended investigation | Root-cause the Feb–Mar 2018 late-delivery surge (carrier/strike/weather – external data needed). |
| Suggested business action | Use the 30-day forecast and anomaly alerts for capacity planning; pre-book carrier capacity before Black Friday. |
| KPI to monitor | Peak-week on-time rate, anomaly alerts per month, forecast error during peaks. |

## 9. Churn can be ranked, not predicted precisely

| Aspect | Detail |
|---|---|
| Business problem | Retention budget should target customers most likely to return. |
| Supporting metric | Best churn model random_forest: test ROC-AUC 0.582, top-decile return lift 2.0×. |
| Relevant segment / region | Active customers (purchase in last 365 days). |
| Possible explanation | Behavioural signal is limited to 1–2 orders per customer; no browsing/marketing data. |
| Recommended investigation | Add engagement data (email opens, sessions) to the feature set. |
| Suggested business action | Use churn scores only to prioritise campaign audiences; measure with a randomised holdout. |
| KPI to monitor | Return rate of targeted vs holdout group; model lift over time. |

## Simulated profitability (clearly synthetic)

Cost and inventory data do **not** exist in the source. `data/synthetic` contains simulated unit costs and weekly inventory (seeded, documented in `data/synthetic/README.md`). SQL Q44/Q45 and the Power BI 'Simulated' visuals use them to demonstrate margin and stock-out analytics. **No conclusion in this report is based on synthetic data.**