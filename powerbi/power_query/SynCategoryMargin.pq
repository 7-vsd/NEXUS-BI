// SynCategoryMargin – CSV import (parameter DataFolder)
// SIMULATED category margin – synthetic costs, not real data.
let
    Source = Csv.Document(File.Contents(DataFolder & "\vw_syn_category_margin.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected = Table.SelectColumns(Promoted, {"category_name_en", "revenue", "simulated_cogs", "simulated_gross_margin", "simulated_margin_pct", "is_synthetic"}),
    Typed = Table.TransformColumnTypes(Selected, {{"category_name_en", type text}, {"revenue", Currency.Type}, {"simulated_cogs", Currency.Type}, {"simulated_gross_margin", Currency.Type}, {"simulated_margin_pct", Currency.Type}, {"is_synthetic", type logical}}, "en-US")
in
    Typed
