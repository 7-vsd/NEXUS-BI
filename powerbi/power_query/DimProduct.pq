// DimProduct – CSV import (parameter DataFolder)
// Product dimension (SCD1) with English category names.
let
    Source = Csv.Document(File.Contents(DataFolder & "\dim_product.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected = Table.SelectColumns(Promoted, {"product_key", "product_id", "category_name_pt", "category_name_en", "category_display_name", "product_name_length", "product_description_length", "product_photos_qty", "product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm", "product_volume_cm3", "weight_band"}),
    Typed = Table.TransformColumnTypes(Selected, {{"product_key", Int64.Type}, {"product_id", type text}, {"category_name_pt", type text}, {"category_name_en", type text}, {"category_display_name", type text}, {"product_name_length", Int64.Type}, {"product_description_length", Int64.Type}, {"product_photos_qty", Int64.Type}, {"product_weight_g", type number}, {"product_length_cm", type number}, {"product_height_cm", type number}, {"product_width_cm", type number}, {"product_volume_cm3", type number}, {"weight_band", type text}}, "en-US")
in
    Typed
