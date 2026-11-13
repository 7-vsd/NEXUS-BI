"""Build the 5 analysis notebooks (then execute them with nbconvert so outputs are real).

    python scripts/build_notebooks.py && python scripts/build_notebooks.py --execute
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / "notebooks"

SETUP = """import sys, pathlib
ROOT = pathlib.Path.cwd().resolve()
while not (ROOT / "src").exists() and ROOT != ROOT.parent:
    ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))
import os; os.chdir(ROOT)
import pandas as pd, numpy as np
from IPython.display import Image, Markdown, display
pd.set_option("display.max_columns", 40); pd.set_option("display.width", 160)
from src.analytics import eda
om, items, cm, daily = eda.load()

def show(f):
    if f.figure: display(Image(filename=str(ROOT / f.figure)))
    display(Markdown(f"**Business interpretation – {f.title}:** {f.interpretation}"))
"""


def md(t):
    return nbf.v4.new_markdown_cell(t)


def code(t):
    return nbf.v4.new_code_cell(t)


def nb(title, intro, cells):
    n = nbf.v4.new_notebook()
    n.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    n.cells = [md(f"# {title}\n\n{intro}\n\n> Data: Olist Brazilian E-Commerce public dataset (BRL). "
                  "All narrative under charts is generated from the computed statistics."), code(SETUP)] + cells
    return n


NOTEBOOKS = {
    "01_data_understanding.ipynb": nb(
        "01 · Data Understanding",
        "Inventory of the 9 source files, schema, grain and relationships between entities.",
        [md("## 1. Source inventory"), code("eda.dataset_overview()"),
         md("## 2. Schemas and declared keys"),
         code("from src.validation.schemas import SCHEMAS\n"
              "pd.DataFrame([{'dataset': n, 'primary_key': ', '.join(s.primary_key) or '(none – many rows per zip)',\n"
              "               'foreign_keys': '; '.join(f'{c} → {p}.{pc}' for c, (p, pc) in s.foreign_keys.items()),\n"
              "               'description': s.description} for n, s in SCHEMAS.items()])"),
         md("## 3. Data dictionary (generated)"),
         code("pd.read_csv('reports/data_quality/data_dictionary.csv').head(50)"),
         md("## 4. Relationship cardinalities"), code("eda.relationship_cardinality()"),
         md("## 5. Grain decisions\n"
            "* `customer_id` is **order-scoped**; the person is `customer_unique_id` → customer analytics use `customer_unique_id`.\n"
            "* `review_id` is **not unique** – grain of reviews is (`review_id`, `order_id`).\n"
            "* Payments can be split (`payment_sequential`) → order payment = sum over sequences.\n"
            "* Geolocation has many points per zip prefix → aggregated to one row per prefix."),
         code("o = pd.read_parquet('data/staging/clean/orders.parquet')\n"
              "print('Purchase range:', o.order_purchase_timestamp.min(), '→', o.order_purchase_timestamp.max())\n"
              "o.order_status.value_counts().to_frame('orders')"),
         code("m = o.set_index('order_purchase_timestamp').resample('MS').order_id.count()\n"
              "m.tail(6).to_frame('orders captured')  # note the collapse after Aug-2018 = extraction truncation")]),

    "02_data_quality.ipynb": nb(
        "02 · Data Quality",
        "Automated quality checks: nulls, duplicates, referential integrity, domain rules, and the cleaning applied.",
        [md("## 1. Check summary"),
         code("chk = pd.read_csv('reports/data_quality/dq_checks.csv')\nchk.status.value_counts().to_frame('checks')"),
         md("## 2. Issues (non-passing checks)"),
         code("chk[chk.status != 'PASS'].sort_values('failed_rows', ascending=False)[['dataset','check','column','failed_rows','failed_pct','status','detail']]"),
         md("## 3. Referential integrity"),
         code("chk[chk.check == 'referential_integrity'][['dataset','column','detail','failed_rows','status']]"),
         md("## 4. Null profile by column"),
         code("import matplotlib.pyplot as plt\nprof = pd.read_csv('reports/data_quality/column_profile.csv')\n"
              "nz = prof[prof.null_pct > 0].sort_values('null_pct')\n"
              "fig, ax = plt.subplots(figsize=(9, 5)); ax.barh(nz.dataset + '.' + nz.column, nz.null_pct, color='#3B6EA8')\n"
              "ax.set(title='Columns with missing values (source data)', xlabel='Missing values (% of rows)', ylabel='dataset.column')\n"
              "display(Image(filename=str(ROOT / eda._save(fig, '02_missing_values'))))"),
         md("## 5. Cleaning log (what the ETL changed)"),
         code("pd.read_csv('reports/data_quality/cleaning_log.csv')"),
         md("## 6. SQL ↔ Python reconciliation"),
         code("p = ROOT / 'reports/sql_results/_reconciliation.csv'\npd.read_csv(p) if p.exists() else 'Run the analytics stage with PostgreSQL first.'"),
         md("**Interpretation.** No primary-key or foreign-key violations exist in the source. The material issues are "
            "business-level: orders without items (mostly canceled/unavailable), shipping limits years in the future, "
            "duplicate geolocation points, untranslated categories and non-unique review ids – each handled explicitly "
            "in the cleaning log rather than silently dropped.")]),

    "03_exploratory_analysis.ipynb": nb(
        "03 · Exploratory Analysis",
        "Univariate, bivariate and multivariate analysis, outliers, time series, products, geography and delivery.",
        [md("## Univariate"), code("show(eda.univariate_order_value(om))"), code("show(eda.univariate_delivery(om))"),
         md("## Bivariate"), code("show(eda.bivariate_price_freight(items))"), code("show(eda.bivariate_delay_review(om))"),
         md("## Multivariate"), code("show(eda.multivariate_correlation(om))"),
         md("## Outliers"), code("show(eda.outliers_order_value(om))"),
         md("## Time series"), code("show(eda.time_series_revenue(daily))"),
         md("## Product performance"), code("show(eda.product_performance(items))"),
         md("## Geography"), code("show(eda.geographic(om))"),
         md("## Delivery"), code("show(eda.delivery_analysis(om))")]),

    "04_customer_analytics.ipynb": nb(
        "04 · Customer Analytics",
        "Repeat purchasing, cohorts, value concentration, RFM and ML segments.",
        [md("## Repeat purchasing"), code("show(eda.customer_repeat(cm))"),
         md("## Cohort retention"), code("show(eda.customer_cohorts(om))"),
         md("## Customer value / CLV"), code("show(eda.customer_clv(cm))"),
         md("## RFM & K-Means segments (from `ml/customer_segmentation`)"),
         code("pd.read_csv('reports/ml/segmentation_cluster_profile.csv')[['cluster_name','customers','customer_share_pct','revenue_share_pct','recency_median','frequency_mean','monetary_median','recommended_strategy']]"),
         code("pd.read_csv('reports/ml/segmentation_rfm_profile.csv')"),
         code("display(Image(filename=str(ROOT / 'reports/figures/ml/segmentation_elbow_silhouette.png')))")]),

    "05_statistical_analysis.ipynb": nb(
        "05 · Statistical Analysis",
        "Formal hypothesis tests with effect sizes. Non-parametric tests are used because review scores are ordinal "
        "and monetary values are heavily skewed.",
        [code("res, f = eda.hypothesis_tests(om)\nres[['id','hypothesis','test','statistic','p_value_fmt','effect_size','decision','detail']]"),
         code("display(Markdown(f'**Interpretation:** {f.interpretation}'))"),
         md("### Notes on inference\n* These are **observational** associations; none of the tests establishes causation.\n"
            "* With n ≈ 100k, p-values are near zero for trivial effects – read the effect-size column.\n"
            "* H1 (late → lower reviews) is consistent with a causal story but would require an experiment "
            "(e.g. randomised delivery-promise buffers) to quantify the causal impact.")]),
}


def build():
    NB.mkdir(exist_ok=True)
    for name, n in NOTEBOOKS.items():
        nbf.write(n, NB / name)
        print("wrote", name)


def execute():
    from nbconvert.preprocessors import ExecutePreprocessor
    ok = True
    for name in NOTEBOOKS:
        path = NB / name
        n = nbf.read(path, as_version=4)
        try:
            ExecutePreprocessor(timeout=900, kernel_name="python3").preprocess(n, {"metadata": {"path": str(NB)}})
            nbf.write(n, path)
            print("executed", name)
        except Exception as exc:  # noqa: BLE001
            ok = False
            print("FAILED", name, str(exc)[:2000])
    return ok


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--execute", action="store_true")
    args = a.parse_args()
    build()
    if args.execute:
        sys.exit(0 if execute() else 1)
