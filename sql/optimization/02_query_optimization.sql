-- @query Q46_optimization_explain_revenue_filter
-- @category Optimization
-- @description EXPLAIN (ANALYZE) of a monthly revenue query that can use the partial index ix_fo_revenue_only.
-- @output QUERY PLAN text
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT d.month_start, sum(f.revenue)
FROM nexus_dw.fact_orders f JOIN nexus_dw.dim_date d ON d.date_key = f.purchase_date_key
WHERE f.is_revenue_order AND f.purchase_date_key BETWEEN 20180101 AND 20180331
GROUP BY d.month_start;

-- @query Q47_optimization_mv_vs_base
-- @category Optimization
-- @description EXPLAIN (ANALYZE) reading daily KPIs from the materialized view instead of re-aggregating facts.
-- @output QUERY PLAN text
EXPLAIN (ANALYZE, FORMAT TEXT)
SELECT full_date, revenue FROM nexus_dw.mv_daily_kpis WHERE full_date BETWEEN '2018-01-01' AND '2018-03-31';
