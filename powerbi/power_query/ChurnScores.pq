// ChurnScores – CSV import (parameter DataFolder)
// ML: churn probability per active customer at the scoring cutoff.
let
    Source = Csv.Document(File.Contents(DataFolder & "\churn_scores.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected = Table.SelectColumns(Promoted, {"customer_unique_id", "cutoff_date", "churn_probability", "risk_band", "model_name", "actual_churn"}),
    Typed = Table.TransformColumnTypes(Selected, {{"customer_unique_id", type text}, {"cutoff_date", type date}, {"churn_probability", type number}, {"risk_band", type text}, {"model_name", type text}, {"actual_churn", type text}}, "en-US")
in
    Typed
