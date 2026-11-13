// ChurnScores – DirectQuery/Import from PostgreSQL (parameters PgServer, PgDatabase)
let
    Source = PostgreSQL.Database(PgServer, PgDatabase),
    Data = Source{[Schema = "nexus_ml", Item = "churn_scores"]}[Data]
in
    Data
