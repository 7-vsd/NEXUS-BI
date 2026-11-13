// FactOrders – DirectQuery/Import from PostgreSQL (parameters PgServer, PgDatabase)
let
    Source = PostgreSQL.Database(PgServer, PgDatabase),
    Data = Source{[Schema = "nexus_dw", Item = "fact_orders"]}[Data],
    Incremental = Table.SelectRows(Data, each [purchase_timestamp] >= RangeStart and [purchase_timestamp] < RangeEnd)
in
    Incremental
