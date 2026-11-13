# NEXUS BI – application image (API + Streamlit + pipeline). Python 3.11 per project standard.
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

# libgomp for XGBoost; no compilers needed (binary wheels)
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src ./src
COPY ml ./ml
COPY api ./api
COPY app ./app
COPY sql ./sql
COPY orchestration ./orchestration
COPY powerbi ./powerbi
COPY scripts ./scripts
COPY .streamlit ./.streamlit
RUN mkdir -p data/raw data/staging data/processed data/synthetic data/sample logs reports ml/artifacts

# Non-root user
RUN useradd --create-home --uid 10001 nexus && chown -R nexus:nexus /app
USER nexus

EXPOSE 8000 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD curl -fs http://localhost:8000/health || exit 1

# Default: API. docker-compose overrides the command for Streamlit / pipeline.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
