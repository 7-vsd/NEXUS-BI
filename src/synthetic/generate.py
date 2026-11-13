"""SYNTHETIC data generation – clearly separated from the real source data.

The Olist dataset has no product cost, inventory or profit information. To
demonstrate profitability and stock-out analytics we generate *simulated*
datasets with a fixed random seed. Every synthetic table carries
``is_synthetic = True`` and lives only in ``data/synthetic`` and in the
``nexus_dw.syn_*`` tables. Results derived from them must never be reported
as real business findings.

Assumptions (documented in data/synthetic/README.md):
* unit cost ratio per category ~ Uniform(0.45, 0.75) of the median item price,
  plus per-product noise N(0, 0.05), clipped to [0.30, 0.90];
* weekly inventory for the top 30 categories: opening stock starts at
  4 x mean weekly demand; a replenishment of ~3 x mean weekly demand arrives
  when the closing stock falls below a reorder point of 1.5 x mean weekly
  demand (with a random 0-2 week supplier delay). Demand = REAL weekly units.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.config.settings import settings


def product_costs(items: pd.DataFrame, seed: int | None = None) -> pd.DataFrame:
    rng = np.random.default_rng(seed if seed is not None else settings.random_seed)
    prod = (items.groupby(["product_id", "product_category_name_english"])
                 .agg(median_price=("price", "median")).reset_index())
    cats = prod.product_category_name_english.unique()
    cat_ratio = dict(zip(cats, rng.uniform(0.45, 0.75, len(cats))))
    ratio = prod.product_category_name_english.map(cat_ratio) + rng.normal(0, 0.05, len(prod))
    prod["cost_ratio"] = np.clip(ratio, 0.30, 0.90).round(4)
    prod["unit_cost_brl"] = (prod.median_price * prod.cost_ratio).round(2)
    prod["is_synthetic"] = True
    return prod[["product_id", "product_category_name_english", "median_price", "cost_ratio", "unit_cost_brl", "is_synthetic"]]


def weekly_inventory(category_weekly: pd.DataFrame, top_n: int = 30, seed: int | None = None) -> pd.DataFrame:
    rng = np.random.default_rng((seed if seed is not None else settings.random_seed) + 1)
    top = (category_weekly.groupby("category").units.sum().nlargest(top_n).index)
    rows = []
    for cat in top:
        d = category_weekly[category_weekly.category == cat].set_index("week").units
        weeks = pd.date_range(d.index.min(), d.index.max(), freq="W-MON")
        d = d.reindex(weeks, fill_value=0)
        mean_d = max(d.mean(), 1.0)
        stock = 4 * mean_d
        reorder_point = 1.5 * mean_d
        pending: list[tuple[int, float]] = []
        for i, (wk, demand) in enumerate(d.items()):
            arrived = sum(q for due, q in pending if due == i)
            pending = [(due, q) for due, q in pending if due != i]
            opening = stock + arrived
            fulfilled = min(opening, demand)
            lost = demand - fulfilled
            closing = opening - fulfilled
            if closing < reorder_point and not pending:
                pending.append((i + 1 + int(rng.integers(0, 3)), round(3 * mean_d * rng.uniform(0.8, 1.2))))
            rows.append({"category": cat, "week": wk, "opening_stock": round(opening), "received_units": round(arrived),
                         "demand_units": int(demand), "fulfilled_units": round(fulfilled),
                         "lost_sales_units": round(lost), "closing_stock": round(closing),
                         "reorder_point": round(reorder_point), "is_stockout": bool(lost > 0),
                         "is_synthetic": True})
            stock = closing
    return pd.DataFrame(rows)
