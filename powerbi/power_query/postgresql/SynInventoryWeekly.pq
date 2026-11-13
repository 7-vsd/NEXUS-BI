// SynInventoryWeekly – DirectQuery/Import from PostgreSQL (parameters PgServer, PgDatabase)
let
    Source = PostgreSQL.Database(PgServer, PgDatabase),
    Data = Source{[Schema = "nexus_dw", Item = "syn_inventory_weekly"]}[Data]
in
    Data
