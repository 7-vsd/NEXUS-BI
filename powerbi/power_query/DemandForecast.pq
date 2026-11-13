// DemandForecast – CSV import (parameter DataFolder)
// ML: weekly category demand backtest + 4-week forecast.
let
    Source = Csv.Document(File.Contents(DataFolder & "\demand_forecast.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected = Table.SelectColumns(Promoted, {"category", "week_start", "model_name", "kind", "actual", "predicted", "lower_95", "upper_95"}),
    Typed = Table.TransformColumnTypes(Selected, {{"category", type text}, {"week_start", type date}, {"model_name", type text}, {"kind", type text}, {"actual", Currency.Type}, {"predicted", Currency.Type}, {"lower_95", Currency.Type}, {"upper_95", Currency.Type}}, "en-US")
in
    Typed
