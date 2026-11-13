-- =====================================================================
-- DATABASE SECURITY: read-only BI role + row-level security example.
-- Power BI RLS is defined separately in the semantic model (roles/*.tmdl);
-- this provides the equivalent control for direct SQL consumers.
-- No passwords here: roles are created NOLOGIN; grant LOGIN + password
-- out-of-band (see docs/deployment/DEPLOYMENT_GUIDE.md).
--
-- Works with a least-privilege owner: if the connecting user may not create
-- roles (no CREATEROLE), role creation is SKIPPED with a NOTICE and the rest of
-- the warehouse is unaffected. To enable it later run, as the postgres superuser:
--     ALTER ROLE nexus CREATEROLE;      then:  python -m src.database.init_db
-- =====================================================================

-- Mapping of database users to the customer regions they may see (always created)
CREATE TABLE IF NOT EXISTS nexus_dw.security_user_region (
    db_user TEXT NOT NULL,
    region  VARCHAR(12) NOT NULL,
    PRIMARY KEY (db_user, region)
);

DO $$
DECLARE
    can_create BOOLEAN := (SELECT rolsuper OR rolcreaterole FROM pg_roles WHERE rolname = current_user);
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nexus_bi_reader') AND can_create THEN
        EXECUTE 'CREATE ROLE nexus_bi_reader NOLOGIN';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nexus_regional_analyst') AND can_create THEN
        EXECUTE 'CREATE ROLE nexus_regional_analyst NOLOGIN';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nexus_bi_reader')
       OR NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nexus_regional_analyst') THEN
        RAISE NOTICE 'Security roles not created: user % lacks CREATEROLE. Warehouse is fine; '
                     'see sql/warehouse/02_security_rls.sql to enable read-only/RLS roles.', current_user;
        RETURN;
    END IF;

    EXECUTE 'GRANT USAGE ON SCHEMA nexus_dw, nexus_ml TO nexus_bi_reader, nexus_regional_analyst';
    EXECUTE 'GRANT SELECT ON ALL TABLES IN SCHEMA nexus_dw, nexus_ml TO nexus_bi_reader, nexus_regional_analyst';
    EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA nexus_dw GRANT SELECT ON TABLES TO nexus_bi_reader, nexus_regional_analyst';
    EXECUTE 'GRANT SELECT ON nexus_dw.security_user_region TO nexus_regional_analyst';

    -- Row-level security on dim_customer: regional analysts only see their regions.
    EXECUTE 'ALTER TABLE nexus_dw.dim_customer ENABLE ROW LEVEL SECURITY';
    EXECUTE 'DROP POLICY IF EXISTS p_customer_region ON nexus_dw.dim_customer';
    EXECUTE 'CREATE POLICY p_customer_region ON nexus_dw.dim_customer FOR SELECT TO nexus_regional_analyst
             USING (region IN (SELECT region FROM nexus_dw.security_user_region WHERE db_user = current_user))';
    EXECUTE 'DROP POLICY IF EXISTS p_customer_all ON nexus_dw.dim_customer';
    EXECUTE 'CREATE POLICY p_customer_all ON nexus_dw.dim_customer FOR ALL TO PUBLIC
             USING (NOT pg_has_role(current_user, ''nexus_regional_analyst'', ''MEMBER''))';
END $$;
