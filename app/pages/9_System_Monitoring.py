"""System Monitoring – service health, pipeline runs, model registry."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from app.components import api_client
from app.components.data import ROOT
from app.components.ui import kpi_row, note, page_header, section

page_header("System Monitoring", "API & database health, pipeline execution history and model registry.")

ok, h = api_client.health()
runs_path = ROOT / "logs" / "pipeline_runs.jsonl"
runs = pd.DataFrame([json.loads(l) for l in runs_path.read_text().splitlines() if l.strip()]) if runs_path.exists() else pd.DataFrame()
status_path = ROOT / "logs" / "last_pipeline_status.json"
last = json.loads(status_path.read_text()) if status_path.exists() else {}

kpi_row([
    dict(label="API", value="Online" if ok else "Offline", delta_label=h.get("status", "") if ok else "", accent=True),
    dict(label="Database", value={True: "Online", False: "Offline", None: "Unknown"}[h.get("database_available") if ok else None]),
    dict(label="Models loaded", value=f"{sum(h['models_loaded'].values())}/{len(h['models_loaded'])}" if ok else "–"),
    dict(label="Last pipeline run", value=last.get("status", "–"), delta_label=last.get("finished_at", "")[:19]),
])
if not ok:
    note(f"⚠️ {h}")

section("Pipeline step history (latest 50)")
if runs.empty:
    st.info("No pipeline runs recorded yet.")
else:
    cols = [c for c in ["started_at", "step", "status", "duration_s", "rows", "error"] if c in runs.columns]
    st.dataframe(runs[cols].sort_values("started_at", ascending=False).head(50), hide_index=True, width="stretch")
    fails = runs[runs.status == "FAILED"]
    if len(fails):
        st.caption(f"{len(fails)} failed step executions recorded historically (see logs/nexus_bi.log).")

section("Model registry")
rows = []
for meta in sorted((ROOT / "ml" / "artifacts").glob("*/metadata.json")):
    m = json.loads(meta.read_text())
    trained = datetime.fromisoformat(m["trained_at"])
    rows.append({"module": m["module"], "best_model": m.get("best_model", m.get("algorithm", "")),
                 "trained_at": trained.strftime("%Y-%m-%d %H:%M UTC"),
                 "age_hours": round((datetime.now(timezone.utc) - trained).total_seconds() / 3600, 1),
                 "sklearn": m.get("sklearn"), "python": m.get("python")})
st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

section("Artifact sizes")
art = [{"file": str(p.relative_to(ROOT)), "size_mb": round(p.stat().st_size / 1e6, 2),
        "modified": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")}
       for p in sorted((ROOT / "ml" / "artifacts").glob("*/*.joblib"))]
st.dataframe(pd.DataFrame(art), hide_index=True, width="stretch")
