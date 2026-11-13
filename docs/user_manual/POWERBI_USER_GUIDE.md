# Power BI User Guide – NEXUS BI

## What is delivered (and what is not)

| Item | Status |
|---|---|
| Power BI Project `powerbi/NexusBI.pbip` (TMDL semantic model + PBIR report) | **Generated** by `powerbi/build_pbip.py` |
| Static validation (JSON, TMDL indentation, relationships, visual fields, DAX references, RLS, cardinality) | **PASS** – `python powerbi/validate_pbip.py` |
| DAX logic re-computed in pandas on the same extracts vs reconciled SQL/Python KPIs | **PASS** (8 KPIs) |
| Opened, refreshed and rendered in Power BI Desktop | **NOT DONE** – Power BI Desktop is Windows-only and was not available in the build environment |
| `.pbix` file | **Not generated** – save it yourself from Desktop (steps below). No fake PBIX is shipped. |

## Model overview
* 17 import tables from `data/processed/powerbi/*.csv` (warehouse + ML extracts) + `_Measures` (80 measures),
  `KPI Selector` (dynamic measure slicer), `Metric Selector` (field parameter).
* 20 relationships (single direction, dimension → fact). `FactOrders[delivered_date_key] → DimDate` is **inactive**
  and used by `[Deliveries by Delivery Date]` via `USERELATIONSHIP`.
* `DimDate` is marked as the date table (`dataCategory: Time`, key `full_date`).
* Parameters: `DataFolder` (CSV folder), `RangeStart` / `RangeEnd` (incremental refresh on `FactOrders`).
* RLS roles: `Regional Manager (Dynamic)` (USERPRINCIPALNAME → `SecurityUserRegion`), `Region Sudeste|Sul|Nordeste|Centro-Oeste|Norte`, `Executive (All Data)`.
* Theme: `powerbi/NexusBI_Theme.json` (navy / teal enterprise palette).
* Alternative sources: `powerbi/power_query/*.pq` (CSV) and `powerbi/power_query/postgresql/*.pq` (PostgreSQL / DirectQuery).

## Pages (interactive design, v2)
Dark navy canvas, white panels with coloured accents, and vivid KPI tiles (all tile colours ≥ 4.5:1 contrast with white
text). Every visible page has a **built-in page navigator**, **4 slicers** (dropdowns plus a date-range slider) and
**6 KPI tiles**, and every chart **cross-filters** the others when clicked.

| Page | Visuals |
|---|---|
| **Executive Command Center** | Area chart revenue vs prior year with **drill-down year › quarter › month** · donut by payment method · **gauge** on-time vs 90% target · **treemap** of categories (click to filter) · state columns with **heat colours** · **ribbon chart** of regional ranking by quarter |
| **Customer Intelligence** | Donut of ML segments · **scatter/bubble** of states (value per customer × repeat rate, bubble = customers) · RFM bars (colour per segment) · **cohort matrix heat-map** · 100% stacked segment mix by region |
| **Operations Intelligence** | Combo chart delivery days + on-time % (drillable) · review distribution **red → green** · gauge average review vs 4.0 · late-delivery rate by state with **traffic-light colours** · seller bubble chart · seller scorecard with conditional colours (right-click → Drill through) |
| **Predictive Intelligence** | Revenue actual vs forecast with 95% band (model slicer) · churn risk donut · **stacked-area** demand forecast by category · anomaly days per month · anomaly alert table |
| **Seller Detail** (drill-through) | Seller KPIs, monthly area chart, category donut, customer-state bars |
| **Category Tooltip** | Report-page tooltip |

**Interactions to try:** click a treemap tile, a donut slice or a bar to filter the page (Ctrl+click for several);
use the drill arrows on the revenue area chart; hover for tooltips; right-click a seller → *Drill through › Seller Detail*.

**Measure fixes in v2** (found by reviewing DAX filter propagation, which static validation cannot test):
`[Unique Customers]` / `[Active Customers]` now filter through the fact **table**, because a column predicate on
FactOrders does not restrict DimCustomer. Seller-level review and on-time rates use new `[Seller Avg Review]` /
`[Seller On-Time %]` (TREATAS from items to orders). Without these fixes the customer count would have shown 96,097 and
every seller would have shown the overall average.

## Open, validate and save as PBIX (Windows)

1. **Prerequisites:** Power BI Desktop (current version). *File › Options › Preview features*: enable
   **Power BI Project (.pbip) save option**, **Store semantic model using TMDL format** and
   **Store reports using enhanced metadata format (PBIR)** (names may differ slightly by version; restart Desktop).
2. **Generate data:** run the pipeline so `data\processed\powerbi\*.csv` exists (`.\scripts\nexus.ps1 pipeline`).
3. **Point the model at your folder:** `.\scripts\nexus.ps1 powerbi` (rewrites `DataFolder` to this machine's path), or
   after opening: *Transform data › Edit parameters › DataFolder*.
4. **Open** `powerbi\NexusBI.pbip` → *Refresh*. Expect ≈ 0.7 M rows in total.
5. **Validate** (compare with `reports/sql_results/_reconciliation.csv`):

   | Measure (no filters) | Expected |
   |---|---|
   | Total Revenue | 15,735,527.03 |
   | Total Orders | 98,207 |
   | Unique Customers | 94,990 |
   | Average Order Value | 160.23 |
   | On-Time Delivery % | 93.2% (0.932269) |
   | Cancellation Rate | 0.63% (0.006285) |
   | Avg Review Score | 4.09 (4.0864) |
   | Items Sold | 112,101 |

   Also check *Model view* (20 relationships, one inactive), *Modeling › Manage roles › View as* "Region Sul" (revenue
   should drop to the Sul share, R$ ≈ 2.28 M), and the field-parameter slicer on page 1.
6. **Manual finishing steps** (not expressible reliably in generated files):
   * Seller Detail page: *Drill through* well ← `DimSeller[seller_id]`.
   * Category Tooltip page: *Page information › Allow use as tooltip* = On; assign it to the Executive category chart.
   * Predictive page: add a visual-level filter `Anomalies[is_anomaly] = True` on the anomaly table.
   * Incremental refresh: right-click `FactOrders` › *Incremental refresh* → archive 3 years, refresh last 10 days
     (parameters and the M filter are already in place). Takes effect after publishing to the Service.
7. **Save as PBIX:** *File › Save as* → `NexusBI.pbix` (keep the PBIP as the source-controlled version).

## If the report fails to open
The semantic model is the core asset; PBIR schema versions evolve with Desktop releases. If Desktop rejects the report
definition: delete `powerbi\NexusBI.Report\definition\pages\*`, open the project (an empty report bound to the full
model opens), and rebuild the pages from the `DASHBOARD_SPEC.md` files – every measure already exists.
Report the exact error text so the generator can be adjusted (`powerbi/build_pbip.py`, constants `VC`, `PAGE`).

## Accessibility (WCAG 2.1 / EN 301 549)
Audited with the *Power BI Accessibility (PBIP/PBIR)* tool (2026-11-13): 116 issues found on 58 visuals
(58 missing alt texts, 58 missing tab orders, 0 anomalies). Fixed **in the generator** (`apply_accessibility()` in
`powerbi/build_pbip.py`), so a rebuild keeps them. A re-scan of the regenerated report: **0 issues on all 6 pages**.
* **Alt text** (English) on every visual, e.g. "KPI card showing Total Revenue.", "Line chart showing monthly revenue
  vs prior year.", "Slicer to filter the page by year." The seller table also explains the drill-through.
* **Tab order**: top-to-bottom, left-to-right reading order (page title → slicers → KPI cards → charts → tables).
* Guarded by `tests/integration/test_powerbi_and_app.py::test_report_accessibility_metadata`.
* Audit workbook: `reports/accessibility/accessibilita_NexusBI_*.xlsx`.
* Still to check by a person in Power BI Desktop: colour contrast of the theme, keyboard focus on each page
  (Ctrl+F6 / Tab), and a screen-reader pass (Narrator or NVDA).

## Performance notes
Star schema, integer surrogate keys, hidden key columns, `discourageImplicitMeasures`, measures instead of calculated
columns, only one calculated column (`DimCustomer[first_order_month]`, computed in Power Query), no bi-directional filters.
