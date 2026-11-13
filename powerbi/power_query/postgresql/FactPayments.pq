// FactPayments – DirectQuery/Import from PostgreSQL (parameters PgServer, PgDatabase)
let
    Source = PostgreSQL.Database(PgServer, PgDatabase),
    Data = Source{[Schema = "nexus_dw", Item = "fact_payments"]}[Data]
in
    Data
