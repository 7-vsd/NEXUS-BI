// FactReviews – CSV import (parameter DataFolder)
// Grain: one row per (review_id, order_id).
let
    Source = Csv.Document(File.Contents(DataFolder & "\fact_reviews.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected = Table.SelectColumns(Promoted, {"review_id", "order_id", "customer_key", "purchase_date_key", "review_date_key", "answer_date_key", "review_score", "has_comment", "has_title", "response_hours", "is_latest_for_order"}),
    Typed = Table.TransformColumnTypes(Selected, {{"review_id", type text}, {"order_id", type text}, {"customer_key", Int64.Type}, {"purchase_date_key", Int64.Type}, {"review_date_key", Int64.Type}, {"answer_date_key", Int64.Type}, {"review_score", Int64.Type}, {"has_comment", type logical}, {"has_title", type logical}, {"response_hours", type number}, {"is_latest_for_order", type logical}}, "en-US")
in
    Typed
