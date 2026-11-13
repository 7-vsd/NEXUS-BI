# PROJECT STATUS – NEXUS BI

**Current stage:** 13/13 complete – delivered to `C:\Users\91705\Nexus_bi\NEXUS-BI` (2026-11-12).

| Stage | Status |
|---|---|
| 1–3 Structure, ingestion, DQ, ETL | ✅ complete, tested |
| 4–5 PostgreSQL warehouse, 47 SQL queries, reconciliation | ✅ complete, tested (build environment) |
| 6 EDA notebooks & reports | ✅ complete, executed |
| 7 Power BI PBIP | ✅ generated + statically validated · ⏳ open/validate/save PBIX in Power BI Desktop (manual) |
| 8 ML modules | ✅ complete, evaluated |
| 9–10 FastAPI, Streamlit | ✅ complete, tested (live servers) |
| 11 Airflow DAG | ✅ `airflow dags test` success · ⏳ scheduler deployment (WSL2/Docker) |
| 12 Testing | ✅ 106 pass / 0 fail / 1 not run (+ Airflow venv 1 pass, Python 3.10 79 pass) |
| 13 Docs & deployment files | ✅ complete · ⏳ Docker image build and Azure deploy not executed |

## Remaining tasks (on your PC)
1. Install PostgreSQL 16 (or Docker Desktop) and Power BI Desktop (neither found on this PC).
2. Run the commands below; then follow `docs/user_manual/POWERBI_USER_GUIDE.md` §"Open, validate and save as PBIX".
3. Optional: GitHub repository, Azure deployment (`docs/deployment/DEPLOYMENT_GUIDE.md`).

## Exact next commands
```powershell
cd C:\Users\91705\Nexus_bi\NEXUS-BI
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\nexus.ps1 setup
.\scripts\nexus.ps1 train            # rebuild model files for your Python/library versions (no DB needed)
.\scripts\nexus.ps1 api              # terminal 1
.\scripts\nexus.ps1 app              # terminal 2
# after installing PostgreSQL + creating role/db + editing .env:
.\scripts\nexus.ps1 init-db
.\scripts\nexus.ps1 pipeline
.\scripts\nexus.ps1 test
```
