// SynInventoryWeekly – CSV import (parameter DataFolder)
// SIMULATED weekly inventory – synthetic, not real data.
let
    Source = Csv.Document(File.Contents(DataFolder & "\syn_inventory_weekly.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected = Table.SelectColumns(Promoted, {"category", "week_start", "opening_stock", "received_units", "demand_units", "fulfilled_units", "lost_sales_units", "closing_stock", "reorder_point", "is_stockout", "is_synthetic"}),
    Typed = Table.TransformColumnTypes(Selected, {{"category", type text}, {"week_start", type date}, {"opening_stock", Int64.Type}, {"received_units", Int64.Type}, {"demand_units", Int64.Type}, {"fulfilled_units", Int64.Type}, {"lost_sales_units", Int64.Type}, {"closing_stock", Int64.Type}, {"reorder_point", Int64.Type}, {"is_stockout", type logical}, {"is_synthetic", type logical}}, "en-US")
in
    Typed
