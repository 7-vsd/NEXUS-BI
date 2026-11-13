// Anomalies – CSV import (parameter DataFolder)
// ML: daily KPI anomaly scores and flags.
let
    Source = Csv.Document(File.Contents(DataFolder & "\anomalies.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected = Table.SelectColumns(Promoted, {"metric_date", "revenue", "orders", "aov", "late_rate", "avg_review", "iforest_score", "iforest_flag", "rolling_z", "rolling_flag", "global_z", "zscore_flag", "votes", "is_anomaly", "severity", "direction"}),
    Typed = Table.TransformColumnTypes(Selected, {{"metric_date", type date}, {"revenue", Currency.Type}, {"orders", Int64.Type}, {"aov", Currency.Type}, {"late_rate", type number}, {"avg_review", type number}, {"iforest_score", type number}, {"iforest_flag", type logical}, {"rolling_z", type number}, {"rolling_flag", type logical}, {"global_z", type number}, {"zscore_flag", type logical}, {"votes", Int64.Type}, {"is_anomaly", type logical}, {"severity", type text}, {"direction", type text}}, "en-US")
in
    Typed
