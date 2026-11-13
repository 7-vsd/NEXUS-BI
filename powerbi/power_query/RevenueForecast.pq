// RevenueForecast – CSV import (parameter DataFolder)
// ML: daily revenue backtest + 30-day forecast per model.
let
    Source = Csv.Document(File.Contents(DataFolder & "\revenue_forecast.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected = Table.SelectColumns(Promoted, {"forecast_date", "model_name", "kind", "actual", "predicted", "lower_95", "upper_95"}),
    Typed = Table.TransformColumnTypes(Selected, {{"forecast_date", type date}, {"model_name", type text}, {"kind", type text}, {"actual", Currency.Type}, {"predicted", Currency.Type}, {"lower_95", Currency.Type}, {"upper_95", Currency.Type}}, "en-US")
in
    Typed
