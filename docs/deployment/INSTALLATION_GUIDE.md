# Installation Guide (Windows 10/11)

## 1. Prerequisites
| Tool | Version | Notes |
|---|---|---|
| Python | 3.10 – 3.13 (64-bit) | `py -0` lists installed versions. Tested: 3.13 (full suite incl. PostgreSQL) and 3.10 + pandas 2.3 (pipeline + 79 tests). Python 3.9 is **not** supported. Docker image uses 3.11. |
| PostgreSQL | 14+ (16 tested) | Installer from postgresql.org **or** Docker Desktop: `docker compose up -d db` |
| Power BI Desktop | current | For the PBIP (optional) |
| Git | any | optional |
| Docker Desktop | optional | containerised run |
| Airflow | optional | Not supported natively on Windows – use WSL2 or Docker |

## 2. Get the project and data
```powershell
cd C:\Users\<you>\Nexus_bi\NEXUS-BI
# The 9 Olist CSVs must be in data\raw\ (already there in the delivered copy)
```

## 3. Install (one command)
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass   # allow the local script in this session
.\scripts\nexus.ps1 setup
```
Creates `.venv`, installs `requirements.txt`, copies `.env.example` → `.env`.

## 4. Database (once)
With a local PostgreSQL, in **psql** as the `postgres` superuser:
```sql
CREATE ROLE nexus LOGIN PASSWORD '<choose-a-password>';
CREATE DATABASE nexus_bi OWNER nexus;
```
Edit `.env`: `NEXUS_DB_HOST=localhost`, `NEXUS_DB_PASSWORD=<choose-a-password>`. Then:
```powershell
.\scripts\nexus.ps1 init-db          # creates nexus_raw, nexus_staging, nexus_dw, nexus_ml objects
```
*Docker alternative:* set `NEXUS_DB_PASSWORD` in `.env`, run `docker compose up -d db` (creates role + database).

## 5. Run
```powershell
.\scripts\nexus.ps1 pipeline         # ≈ 2–3 min: extract → validate → transform → load → SQL → ML → publish
.\scripts\nexus.ps1 api              # terminal 1 → http://localhost:8000/docs
.\scripts\nexus.ps1 app              # terminal 2 → http://localhost:8501
.\scripts\nexus.ps1 test             # full test suite
```
Without PostgreSQL: `.\scripts\nexus.ps1 pipeline-no-db` (API + app work; SQL analytics, warehouse tests and Power BI
extracts are skipped).

## 6. Power BI
```powershell
.\scripts\nexus.ps1 powerbi          # regenerates the PBIP with this machine's data path
start .\powerbi\NexusBI.pbip
```
Then follow `docs/user_manual/POWERBI_USER_GUIDE.md`.

## Troubleshooting
| Symptom | Fix |
|---|---|
| `psycopg.OperationalError: connection refused` | PostgreSQL not running / wrong `NEXUS_DB_HOST` or port in `.env` |
| `password authentication failed` | `.env` password ≠ role password |
| API returns 503 | Run `.\scripts\nexus.ps1 pipeline` (marts/models missing) |
| Streamlit "API unreachable" banner | Start the API; check `NEXUS_API_URL` |
| Unpickling warnings for models | Library versions changed – retrain: `.\scripts\nexus.ps1 train` |
| Power BI "file not found" on refresh | `DataFolder` parameter must point to `...\data\processed\powerbi` |
