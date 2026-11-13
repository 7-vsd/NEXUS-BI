-- =====================================================================
-- NEXUS BI · Database layers
-- nexus_raw      : byte-faithful copies of the source CSVs (all TEXT)
-- nexus_staging  : typed + cleaned data produced by the Python ETL
-- nexus_dw       : dimensional star schema (facts + dimensions)
-- nexus_ml       : model outputs (segments, churn scores, forecasts, anomalies)
-- Idempotent: safe to run repeatedly.
-- =====================================================================
CREATE SCHEMA IF NOT EXISTS nexus_raw;
CREATE SCHEMA IF NOT EXISTS nexus_staging;
CREATE SCHEMA IF NOT EXISTS nexus_dw;
CREATE SCHEMA IF NOT EXISTS nexus_ml;

COMMENT ON SCHEMA nexus_raw     IS 'Raw landing layer - untyped copies of source files';
COMMENT ON SCHEMA nexus_staging IS 'Cleaned, typed staging layer loaded by the Python ETL';
COMMENT ON SCHEMA nexus_dw      IS 'Star-schema data warehouse';
COMMENT ON SCHEMA nexus_ml      IS 'Machine-learning prediction tables';

-- ETL audit + watermark tables (used for incremental loads and monitoring)
CREATE TABLE IF NOT EXISTS nexus_dw.etl_audit_log (
    audit_id      BIGSERIAL PRIMARY KEY,
    process_name  TEXT        NOT NULL,
    status        TEXT        NOT NULL CHECK (status IN ('STARTED','SUCCESS','FAILED')),
    rows_affected BIGINT,
    message       TEXT,
    logged_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS nexus_dw.etl_watermark (
    table_name     TEXT PRIMARY KEY,
    watermark_ts   TIMESTAMP,
    last_loaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    rows_loaded    BIGINT
);
