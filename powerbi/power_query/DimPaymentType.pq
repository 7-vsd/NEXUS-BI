// DimPaymentType – CSV import (parameter DataFolder)
// Payment method dimension.
let
    Source = Csv.Document(File.Contents(DataFolder & "\dim_payment_type.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected = Table.SelectColumns(Promoted, {"payment_type_key", "payment_type", "payment_type_label", "is_card"}),
    Typed = Table.TransformColumnTypes(Selected, {{"payment_type_key", Int64.Type}, {"payment_type", type text}, {"payment_type_label", type text}, {"is_card", type logical}}, "en-US")
in
    Typed
