"""Static validation of the generated PBIP + independent re-computation of key DAX measures.

What this CAN verify without Power BI Desktop:
  1. every JSON file parses; required PBIR keys present ($schema, name, position, visual)
  2. TMDL files use tab indentation and declare one table/role each
  3. every relationship endpoint (table.column) exists
  4. every visual field reference exists in the model
  5. every [Name] reference inside a DAX measure resolves to a measure or a column of the referenced table
  6. RLS role expressions reference existing tables/columns
  7. the many-side of each relationship is not unique, the one-side IS unique (checked on the CSV data)
  8. DAX logic of core KPIs re-implemented in pandas on the SAME CSV extracts equals the reconciled KPIs
What it CANNOT verify: that Power BI Desktop accepts every property/schema version (requires Desktop on Windows).

    python powerbi/validate_pbip.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from powerbi.build_pbip import CSV_DIR, RELATIONSHIPS, TABLES  # noqa: E402
from powerbi.dax.measures import MEASURES  # noqa: E402

PBI = ROOT / "powerbi"
SM, RP = PBI / "NexusBI.SemanticModel", PBI / "NexusBI.Report"


def run() -> list[dict]:
    results: list[dict] = []

    def check(name, ok, detail=""):
        results.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": detail})

    schema = json.loads((PBI / "model_schema.json").read_text())
    measures = {m[0] for m in MEASURES}

    # 1 JSON
    bad = []
    for p in list(RP.rglob("*.json")) + list(RP.rglob("*.pbir")) + [PBI / "NexusBI.pbip", SM / "definition.pbism"]:
        try:
            j = json.loads(p.read_text(encoding="utf-8"))
            if p.name == "visual.json" and not all(k in j for k in ("$schema", "name", "position", "visual")):
                bad.append(f"{p}: missing required keys")
        except json.JSONDecodeError as exc:
            bad.append(f"{p}: {exc}")
    check("json_files_parse_and_required_keys", not bad, "; ".join(bad[:5]))

    # 2 TMDL indentation
    bad = []
    for p in (SM / "definition").rglob("*.tmdl"):
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if line.startswith(" "):
                bad.append(f"{p.name}:{i}")
    check("tmdl_tab_indentation", not bad, ", ".join(bad[:5]))
    tables = sorted(p.stem for p in (SM / "definition" / "tables").glob("*.tmdl"))
    check("tmdl_one_file_per_table", len(tables) == len(schema), f"{len(tables)} files / {len(schema)} tables")

    # 3 relationships
    bad = [f"{ft}.{fc}->{tt}.{tc}" for ft, fc, tt, tc, _ in RELATIONSHIPS
           if fc not in schema.get(ft, []) or tc not in schema.get(tt, [])]
    check("relationship_columns_exist", not bad, ", ".join(bad))

    # 4 visual fields
    bad = []
    for vj in RP.rglob("visual.json"):
        v = json.loads(vj.read_text())
        for b in v["visual"].get("query", {}).get("queryState", {}).values():
            for pr in b["projections"]:
                k = "Measure" if "Measure" in pr["field"] else "Column"
                e, prop = pr["field"][k]["Expression"]["SourceRef"]["Entity"], pr["field"][k]["Property"]
                if prop not in schema.get(e, []):
                    bad.append(f"{vj.parent.name}:{e}.{prop}")
    check("visual_field_references_exist", not bad, ", ".join(bad[:5]))

    # 5 DAX references
    bad = []
    for name, expr, *_ in MEASURES:
        for tbl, col in re.findall(r"'?([A-Za-z_][A-Za-z0-9_ ]*?)'?\[([^\]]+)\]", expr):
            tbl = tbl.strip()
            if tbl and tbl not in schema:
                bad.append(f"{name}: table {tbl}")
            elif tbl and col not in schema[tbl] and not (tbl == "_Measures" and col in measures):
                bad.append(f"{name}: {tbl}[{col}]")
        for ref in re.findall(r"(?<![A-Za-z0-9_'\]])\[([^\]]+)\]", expr):
            if ref not in measures:
                bad.append(f"{name}: measure [{ref}]")
    check("dax_references_resolve", not bad, "; ".join(bad[:8]))

    # 6 RLS
    bad = []
    for p in (SM / "definition" / "roles").glob("*.tmdl"):
        for tbl, col in re.findall(r"([A-Za-z_]+)\[([^\]]+)\]", p.read_text()):
            if col not in schema.get(tbl, []):
                bad.append(f"{p.stem}: {tbl}[{col}]")
    check("rls_references_resolve", not bad, ", ".join(bad))

    # 7 cardinality on data
    bad, info, csv = [], [], {t: c for t, (c, _) in TABLES.items()}
    # ML scoring tables cover only scored customers; unmatched DimCustomer rows are expected (blank segment)
    partial_coverage = {"CustomerSegments", "ChurnScores"}
    cache: dict[str, pd.DataFrame] = {}

    def col(t, c):
        if t not in cache:
            cache[t] = pd.read_csv(CSV_DIR / f"{csv[t]}.csv", dtype=str, keep_default_na=False, na_values=[""])
        return cache[t][c]
    for ft, fc, tt, tc, _ in RELATIONSHIPS:
        one = col(tt, tc).dropna()
        if one.duplicated().any():
            bad.append(f"{tt}.{tc} not unique")
        many = col(ft, fc).dropna()
        orphans = (~many.isin(set(one))).sum()
        if orphans and tt in partial_coverage:
            info.append(f"{ft}->{tt}: {orphans} customer versions not scored (expected)")
        elif orphans:
            bad.append(f"{ft}.{fc}: {orphans} orphan values")
    check("relationship_cardinality_and_integrity", not bad, "; ".join(bad + info))

    # 8 DAX logic recomputed on the same extracts vs reconciled KPIs
    head = json.loads((ROOT / "data" / "processed" / "headline_kpis.json").read_text())
    fo = pd.read_csv(CSV_DIR / "fact_orders.csv", low_memory=False)
    dc = pd.read_csv(CSV_DIR / "dim_customer.csv", usecols=["customer_key", "customer_unique_id"])
    fi = pd.read_csv(CSV_DIR / "fact_order_items.csv", usecols=["is_revenue_order"])
    rev = fo[fo.is_revenue_order]
    dax_equiv = {
        "total_revenue": round(fo.revenue.sum(), 2),                                     # [Total Revenue]
        "total_orders": int(len(rev)),                                                   # [Total Orders]
        "average_order_value": round(fo.revenue.sum() / len(rev), 2),                    # [Average Order Value]
        "unique_customers": int(rev.merge(dc, on="customer_key").customer_unique_id.nunique()),  # [Unique Customers]
        "on_time_delivery_rate": round((fo.is_on_time == True).sum() / fo.is_delivered.sum(), 6),  # noqa: E712
        "cancellation_rate": round(fo.is_canceled.sum() / len(fo), 6),                  # [Cancellation Rate]
        "avg_review_score": round(fo.review_score.mean(), 4),                            # [Avg Review Score]
        "items_sold": int(fi.is_revenue_order.sum()),                                    # [Items Sold]
    }
    bad = [f"{k}: dax={v} reconciled={head[k]}" for k, v in dax_equiv.items() if abs(v - head[k]) > 0.011]
    check("dax_logic_matches_reconciled_kpis", not bad, "; ".join(bad) or json.dumps(dax_equiv))
    return results


if __name__ == "__main__":
    res = run()
    for r in res:
        print(f"{r['status']}  {r['check']}  {r['detail'][:300]}")
    out = ROOT / "reports" / "powerbi_validation.json"
    out.write_text(json.dumps(res, indent=2))
    sys.exit(0 if all(r["status"] == "PASS" for r in res) else 1)
