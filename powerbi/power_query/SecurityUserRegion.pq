// SecurityUserRegion – CSV import (parameter DataFolder)
// RLS mapping of user e-mail (UPN) to allowed customer regions.
let
    Source = Csv.Document(File.Contents(DataFolder & "\security_user_region.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected = Table.SelectColumns(Promoted, {"user_email", "region"}),
    Typed = Table.TransformColumnTypes(Selected, {{"user_email", type text}, {"region", type text}}, "en-US")
in
    Typed
