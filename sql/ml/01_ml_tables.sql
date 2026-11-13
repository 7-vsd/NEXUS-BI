-- =====================================================================
-- ML OUTPUT TABLES (nexus_ml) – written by ml/* modules via src/database/loader.py
-- =====================================================================
CREATE TABLE IF NOT EXISTS nexus_ml.customer_segments (
    customer_unique_id VARCHAR(32) PRIMARY KEY,
    recency_days INTEGER, frequency INTEGER, monetary NUMERIC(14,2),
    r_score SMALLINT, f_score SMALLINT, m_score SMALLINT, rfm_segment TEXT,
    cluster SMALLINT, cluster_name TEXT, recommended_strategy TEXT,
    scored_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS nexus_ml.churn_scores (
    customer_unique_id VARCHAR(32) NOT NULL, cutoff_date DATE NOT NULL,
    churn_probability NUMERIC(6,4), risk_band TEXT, model_name TEXT,
    actual_churn BOOLEAN, PRIMARY KEY (customer_unique_id, cutoff_date)
);
CREATE TABLE IF NOT EXISTS nexus_ml.revenue_forecast (
    forecast_date DATE NOT NULL, model_name TEXT NOT NULL, kind TEXT NOT NULL,  -- backtest | future
    actual NUMERIC(14,2), predicted NUMERIC(14,2), lower_95 NUMERIC(14,2), upper_95 NUMERIC(14,2),
    PRIMARY KEY (forecast_date, model_name, kind)
);
CREATE TABLE IF NOT EXISTS nexus_ml.demand_forecast (
    category TEXT NOT NULL, week_start DATE NOT NULL, model_name TEXT NOT NULL, kind TEXT NOT NULL,
    actual NUMERIC(12,2), predicted NUMERIC(12,2), lower_95 NUMERIC(12,2), upper_95 NUMERIC(12,2),
    PRIMARY KEY (category, week_start, model_name, kind)
);
CREATE TABLE IF NOT EXISTS nexus_ml.anomalies (
    metric_date DATE PRIMARY KEY, revenue NUMERIC(14,2), orders INTEGER, aov NUMERIC(12,2),
    late_rate NUMERIC(6,4), avg_review NUMERIC(6,3),
    iforest_score NUMERIC(10,5), iforest_flag BOOLEAN, rolling_z NUMERIC(10,3), rolling_flag BOOLEAN,
    global_z NUMERIC(10,3), zscore_flag BOOLEAN, votes SMALLINT, is_anomaly BOOLEAN, severity TEXT, direction TEXT
);
