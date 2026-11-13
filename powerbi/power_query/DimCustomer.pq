// DimCustomer – CSV import (parameter DataFolder)
// Customer dimension – SCD Type 2 on address (one row per customer version).
let
    Source = Csv.Document(File.Contents(DataFolder & "\dim_customer.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected = Table.SelectColumns(Promoted, {"customer_key", "customer_unique_id", "zip_code_prefix", "city", "state", "region", "location_key", "version_number", "valid_from", "valid_to", "is_current", "first_order_date"}),
    Typed = Table.TransformColumnTypes(Selected, {{"customer_key", Int64.Type}, {"customer_unique_id", type text}, {"zip_code_prefix", type number}, {"city", type text}, {"state", type text}, {"region", type text}, {"location_key", Int64.Type}, {"version_number", Int64.Type}, {"valid_from", type datetime}, {"valid_to", type datetime}, {"is_current", type logical}, {"first_order_date", type date}}, "en-US"),
    WithCohort = Table.AddColumn(Typed, "first_order_month", each if [first_order_date] = null then null else Date.StartOfMonth([first_order_date]), type date)
in
    WithCohort
