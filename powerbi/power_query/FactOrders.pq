// FactOrders – CSV import (parameter DataFolder)
// Grain: one row per order.
let
    Source = Csv.Document(File.Contents(DataFolder & "\fact_orders.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Selected = Table.SelectColumns(Promoted, {"order_id", "customer_key", "customer_location_key", "purchase_date_key", "approved_date_key", "delivered_date_key", "estimated_date_key", "main_payment_type_key", "order_status", "purchase_timestamp", "is_revenue_order", "is_canceled", "is_delivered", "is_on_time", "is_late", "items_count", "distinct_sellers", "items_price", "freight_value", "order_value", "revenue", "payment_value", "payment_count", "approval_hours", "delivery_days", "estimated_delivery_days", "delivery_delay_days", "review_score"}),
    Typed = Table.TransformColumnTypes(Selected, {{"order_id", type text}, {"customer_key", Int64.Type}, {"customer_location_key", Int64.Type}, {"purchase_date_key", Int64.Type}, {"approved_date_key", Int64.Type}, {"delivered_date_key", Int64.Type}, {"estimated_date_key", Int64.Type}, {"main_payment_type_key", Int64.Type}, {"order_status", type text}, {"purchase_timestamp", type datetime}, {"is_revenue_order", type logical}, {"is_canceled", type logical}, {"is_delivered", type logical}, {"is_on_time", type logical}, {"is_late", type logical}, {"items_count", Int64.Type}, {"distinct_sellers", Int64.Type}, {"items_price", Currency.Type}, {"freight_value", Currency.Type}, {"order_value", Currency.Type}, {"revenue", Currency.Type}, {"payment_value", Currency.Type}, {"payment_count", Int64.Type}, {"approval_hours", type number}, {"delivery_days", type number}, {"estimated_delivery_days", type number}, {"delivery_delay_days", Int64.Type}, {"review_score", Int64.Type}}, "en-US"),
    Incremental = Table.SelectRows(Typed, each [purchase_timestamp] >= RangeStart and [purchase_timestamp] < RangeEnd)
in
    Incremental
