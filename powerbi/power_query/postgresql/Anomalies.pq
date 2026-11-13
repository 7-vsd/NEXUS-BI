// Anomalies – DirectQuery/Import from PostgreSQL (parameters PgServer, PgDatabase)
let
    Source = PostgreSQL.Database(PgServer, PgDatabase),
    Data = Source{[Schema = "nexus_ml", Item = "anomalies"]}[Data]
in
    Data
