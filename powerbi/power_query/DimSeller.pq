// DimSeller – CSV import (parameter DataFolder)
// Seller dimension (SCD1).
let
    Source = Csv.Document(File.Contents(DataFolder & "\dim_seller.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected = Table.SelectColumns(Promoted, {"seller_key", "seller_id", "zip_code_prefix", "city", "state", "region", "location_key"}),
    Typed = Table.TransformColumnTypes(Selected, {{"seller_key", Int64.Type}, {"seller_id", type text}, {"zip_code_prefix", type number}, {"city", type text}, {"state", type text}, {"region", type text}, {"location_key", Int64.Type}}, "en-US")
in
    Typed
