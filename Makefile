# NEXUS BI – developer shortcuts (GNU make; on Windows use scripts\nexus.ps1 instead)
PY ?= python

.PHONY: install init-db etl train analytics publish pipeline api app test test-fast notebooks reports powerbi validate-powerbi docker-up clean

install:            ## install Python dependencies
	$(PY) -m pip install -r requirements.txt

init-db:            ## create schemas/tables/procedures (idempotent)
	$(PY) -m src.database.init_db

etl:                ## extract -> validate -> transform -> load warehouse
	$(PY) -m src.pipeline --stage extract
	$(PY) -m src.pipeline --stage validate
	$(PY) -m src.pipeline --stage transform
	$(PY) -m src.pipeline --stage load

train:              ## train all ML models + evaluation report
	$(PY) -m src.pipeline --stage predict

analytics:          ## run 47 SQL queries + SQL/Python reconciliation
	$(PY) -m src.pipeline --stage analytics

publish:            ## ML outputs -> nexus_ml, Power BI CSV extracts
	$(PY) -m src.pipeline --stage publish

pipeline:           ## everything, in order
	$(PY) -m src.pipeline --stage all

api:
	uvicorn api.main:app --host 0.0.0.0 --port 8000

app:
	streamlit run app/streamlit_app.py

test:
	$(PY) -m pytest

test-fast:          ## unit tests only
	$(PY) -m pytest tests/unit

notebooks:
	$(PY) scripts/build_notebooks.py --execute

reports:
	$(PY) scripts/generate_reports.py

powerbi:            ## regenerate PBIP (set DATA_FOLDER to the Windows path of data/processed/powerbi)
	$(PY) powerbi/build_pbip.py --data-folder "$(DATA_FOLDER)"

validate-powerbi:
	$(PY) powerbi/validate_pbip.py

docker-up:
	docker compose up -d db && docker compose run --rm pipeline && docker compose up -d api app

clean:
	rm -rf data/staging data/processed logs/*.log .pytest_cache
