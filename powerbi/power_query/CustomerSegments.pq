// CustomerSegments – CSV import (parameter DataFolder)
// ML: RFM + K-Means segment per customer_unique_id.
let
    Source = Csv.Document(File.Contents(DataFolder & "\customer_segments.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected = Table.SelectColumns(Promoted, {"customer_unique_id", "recency_days", "frequency", "monetary", "r_score", "f_score", "m_score", "rfm_segment", "cluster", "cluster_name", "recommended_strategy", "scored_at"}),
    Typed = Table.TransformColumnTypes(Selected, {{"customer_unique_id", type text}, {"recency_days", Int64.Type}, {"frequency", Int64.Type}, {"monetary", Currency.Type}, {"r_score", Int64.Type}, {"f_score", Int64.Type}, {"m_score", Int64.Type}, {"rfm_segment", type text}, {"cluster", Int64.Type}, {"cluster_name", type text}, {"recommended_strategy", type text}, {"scored_at", type text}}, "en-US")
in
    Typed
