# Streamlit Application – User Guide

Start the API first (`.\scripts\nexus.ps1 api`), then the app (`.\scripts\nexus.ps1 app`) → http://localhost:8501.
If the API is down, pages show a warning and KPI cards fall back to local computation with identical rules;
prediction widgets require the API.

## Global controls (sidebar)
* **Dark theme** toggle (dark navy ⇄ light).
* **Purchase date** range, **Region**, **State (UF)**, **Product category** – applied to pages 1–5.

## Pages
| Page | For | Highlights |
|---|---|---|
| Executive Overview | CEO/CFO | KPI cards (from `/api/business-kpis`), growth vs prior period, monthly revenue & orders, region, categories, state table, KPI scorecard vs targets |
| Revenue Intelligence | CFO | Daily/weekly/monthly revenue + rolling mean, MoM growth, YoY by month, weekday × hour heatmap |
| Sales Analytics | Sales | Category treemap, Pareto, price vs freight burden, seller quality/volume quadrant, top sellers, payment mix, installments vs AOV |
| Customer Intelligence | Marketing | ML segments with strategies (API), RFM segments, recency–monetary scatter, cohort retention heatmap, value deciles, customer lookup |
| Operations Analytics | Operations | Delivery distribution, monthly on-time %, late rate by state, review vs delay, status mix |
| Predictive Analytics | All | Revenue forecast (model selector, 95% band, backtest), category demand forecast, churn distribution, what-if churn scoring form |
| Anomaly Monitoring | Ops/Data | Revenue timeline with alerts, alert log with drivers, score-a-new-day form |
| Data Quality | Data team | Inventory, check results, issues, cleaning log, SQL↔Python reconciliation, embedded HTML DQ report |
| System Monitoring | Data team | API/DB health, models loaded, pipeline step history, model registry & artifact age |

Screenshots: `docs/user_manual/screenshots/`.
