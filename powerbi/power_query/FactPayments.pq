// FactPayments – CSV import (parameter DataFolder)
// Grain: one row per payment transaction.
let
    Source = Csv.Document(File.Contents(DataFolder & "\fact_payments.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected = Table.SelectColumns(Promoted, {"order_id", "payment_sequential", "payment_type_key", "customer_key", "purchase_date_key", "payment_installments", "payment_value", "is_revenue_order"}),
    Typed = Table.TransformColumnTypes(Selected, {{"order_id", type text}, {"payment_sequential", Int64.Type}, {"payment_type_key", Int64.Type}, {"customer_key", Int64.Type}, {"purchase_date_key", Int64.Type}, {"payment_installments", Int64.Type}, {"payment_value", Currency.Type}, {"is_revenue_order", type logical}}, "en-US")
in
    Typed
