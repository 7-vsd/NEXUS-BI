// FactOrderItems – CSV import (parameter DataFolder)
// Grain: one row per order line.
let
    Source = Csv.Document(File.Contents(DataFolder & "\fact_order_items.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected = Table.SelectColumns(Promoted, {"order_id", "order_item_id", "product_key", "seller_key", "customer_key", "purchase_date_key", "shipping_limit_date_key", "order_status", "is_revenue_order", "price", "freight_value", "line_total"}),
    Typed = Table.TransformColumnTypes(Selected, {{"order_id", type text}, {"order_item_id", Int64.Type}, {"product_key", Int64.Type}, {"seller_key", Int64.Type}, {"customer_key", Int64.Type}, {"purchase_date_key", Int64.Type}, {"shipping_limit_date_key", Int64.Type}, {"order_status", type text}, {"is_revenue_order", type logical}, {"price", Currency.Type}, {"freight_value", Currency.Type}, {"line_total", Currency.Type}}, "en-US")
in
    Typed
