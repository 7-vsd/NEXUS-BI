# SYNTHETIC DATA – NOT REAL BUSINESS DATA

The Olist dataset contains **no product cost, inventory or profit data**. The files in this folder are
**simulated** to demonstrate profitability and stock-out analytics. They must never be quoted as findings.

| File | Rows | How it is generated (`src/synthetic/generate.py`, seed = `NEXUS_RANDOM_SEED`, default 42) |
|---|---|---|
| `synthetic_product_costs.csv` | one per sold product | category cost ratio ~ U(0.45, 0.75) + product noise N(0, 0.05), clipped to [0.30, 0.90]; `unit_cost = median real price × ratio` |
| `synthetic_inventory_weekly.csv` | top-30 categories × weeks | demand = **real** weekly units; opening stock 4× mean weekly demand; reorder when closing < 1.5× mean demand; replenishment ≈ 3× mean demand (±20%) after a random 0–2 week delay; lost sales when stock runs out |

Every row has `is_synthetic = True`; warehouse tables `nexus_dw.syn_*` enforce `CHECK (is_synthetic)`; DAX measures
are named `SIMULATED …` and live in the display folder "Z Simulated (not real data)".
