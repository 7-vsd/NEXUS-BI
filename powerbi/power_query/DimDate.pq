// DimDate – CSV import (parameter DataFolder)
// Calendar dimension (one row per day). Marked as date table.
let
    Source = Csv.Document(File.Contents(DataFolder & "\dim_date.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected = Table.SelectColumns(Promoted, {"date_key", "full_date", "year", "quarter", "quarter_label", "month", "month_name", "month_short", "year_month", "month_start", "iso_week", "week_start", "day_of_month", "day_of_week", "day_name", "is_weekend", "is_holiday_br", "holiday_name", "is_black_friday"}),
    Typed = Table.TransformColumnTypes(Selected, {{"date_key", Int64.Type}, {"full_date", type date}, {"year", Int64.Type}, {"quarter", Int64.Type}, {"quarter_label", type text}, {"month", Int64.Type}, {"month_name", type text}, {"month_short", type text}, {"year_month", type text}, {"month_start", type date}, {"iso_week", Int64.Type}, {"week_start", type date}, {"day_of_month", Int64.Type}, {"day_of_week", Int64.Type}, {"day_name", type text}, {"is_weekend", type logical}, {"is_holiday_br", type logical}, {"holiday_name", type text}, {"is_black_friday", type logical}}, "en-US")
in
    Typed
