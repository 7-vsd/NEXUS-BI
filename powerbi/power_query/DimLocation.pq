// DimLocation – CSV import (parameter DataFolder)
// Zip-prefix geography with lat/lng and macro-region.
let
    Source = Csv.Document(File.Contents(DataFolder & "\dim_location.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected = Table.SelectColumns(Promoted, {"location_key", "zip_code_prefix", "city", "state", "region", "latitude", "longitude", "has_coordinates"}),
    Typed = Table.TransformColumnTypes(Selected, {{"location_key", Int64.Type}, {"zip_code_prefix", type number}, {"city", type text}, {"state", type text}, {"region", type text}, {"latitude", type number}, {"longitude", type number}, {"has_coordinates", type logical}}, "en-US")
in
    Typed
