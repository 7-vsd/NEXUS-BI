// CustomerSegments – DirectQuery/Import from PostgreSQL (parameters PgServer, PgDatabase)
let
    Source = PostgreSQL.Database(PgServer, PgDatabase),
    Data = Source{[Schema = "nexus_ml", Item = "customer_segments"]}[Data]
in
    Data
