"""Generate the NEXUS BI Power BI Project (PBIP): TMDL semantic model + PBIR report.

The model schema is derived from the actual CSV extracts in
``data/processed/powerbi`` (produced by the publish stage), so every column,
relationship and visual field exists. Re-run after any schema change:

    python powerbi/build_pbip.py [--data-folder "C:\\path\\to\\NEXUS-BI\\data\\processed\\powerbi"]

Output: powerbi/NexusBI.pbip, powerbi/NexusBI.SemanticModel/, powerbi/NexusBI.Report/
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import uuid
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from powerbi.dax.measures import MEASURES  # noqa: E402

PBI = ROOT / "powerbi"
CSV_DIR = ROOT / "data" / "processed" / "powerbi"
SM = PBI / "NexusBI.SemanticModel"
RP = PBI / "NexusBI.Report"
NS = uuid.UUID("6f1c3a1e-0b8e-4b7a-9c1d-5e2f0a9b7c31")
T = "\t"

# table name -> (csv file, description)
TABLES = {
    "DimDate": ("dim_date", "Calendar dimension (one row per day). Marked as date table."),
    "DimCustomer": ("dim_customer", "Customer dimension – SCD Type 2 on address (one row per customer version)."),
    "DimProduct": ("dim_product", "Product dimension (SCD1) with English category names."),
    "DimSeller": ("dim_seller", "Seller dimension (SCD1)."),
    "DimLocation": ("dim_location", "Zip-prefix geography with lat/lng and macro-region."),
    "DimPaymentType": ("dim_payment_type", "Payment method dimension."),
    "FactOrders": ("fact_orders", "Grain: one row per order."),
    "FactOrderItems": ("fact_order_items", "Grain: one row per order line."),
    "FactPayments": ("fact_payments", "Grain: one row per payment transaction."),
    "FactReviews": ("fact_reviews", "Grain: one row per (review_id, order_id)."),
    "CustomerSegments": ("customer_segments", "ML: RFM + K-Means segment per customer_unique_id."),
    "ChurnScores": ("churn_scores", "ML: churn probability per active customer at the scoring cutoff."),
    "RevenueForecast": ("revenue_forecast", "ML: daily revenue backtest + 30-day forecast per model."),
    "DemandForecast": ("demand_forecast", "ML: weekly category demand backtest + 4-week forecast."),
    "Anomalies": ("anomalies", "ML: daily KPI anomaly scores and flags."),
    "SynInventoryWeekly": ("syn_inventory_weekly", "SIMULATED weekly inventory – synthetic, not real data."),
    "SynCategoryMargin": ("vw_syn_category_margin", "SIMULATED category margin – synthetic costs, not real data."),
    "SecurityUserRegion": ("security_user_region", "RLS mapping of user e-mail (UPN) to allowed customer regions."),
}
DROP_COLS = {"loaded_at", "updated_at"}
MONEY = re.compile(r"(price|freight|revenue|value|monetary|payment_value|line_total|cogs|margin|predicted|lower_95|upper_95|actual|aov|median_price|unit_cost)")
HIDDEN_KEYS = re.compile(r"(_key$)")

# (from_table, from_col, to_table, to_col, active, cross_filter)
RELATIONSHIPS = [
    ("FactOrders", "purchase_date_key", "DimDate", "date_key", True),
    ("FactOrders", "delivered_date_key", "DimDate", "date_key", False),
    ("FactOrders", "customer_key", "DimCustomer", "customer_key", True),
    ("FactOrders", "customer_location_key", "DimLocation", "location_key", True),
    ("FactOrders", "main_payment_type_key", "DimPaymentType", "payment_type_key", True),
    ("FactOrderItems", "purchase_date_key", "DimDate", "date_key", True),
    ("FactOrderItems", "product_key", "DimProduct", "product_key", True),
    ("FactOrderItems", "seller_key", "DimSeller", "seller_key", True),
    ("FactOrderItems", "customer_key", "DimCustomer", "customer_key", True),
    ("FactPayments", "purchase_date_key", "DimDate", "date_key", True),
    ("FactPayments", "payment_type_key", "DimPaymentType", "payment_type_key", True),
    ("FactPayments", "customer_key", "DimCustomer", "customer_key", True),
    ("FactReviews", "purchase_date_key", "DimDate", "date_key", True),
    ("FactReviews", "customer_key", "DimCustomer", "customer_key", True),
    ("DimCustomer", "customer_unique_id", "CustomerSegments", "customer_unique_id", True),
    ("DimCustomer", "customer_unique_id", "ChurnScores", "customer_unique_id", True),
    ("RevenueForecast", "forecast_date", "DimDate", "full_date", True),
    ("DemandForecast", "week_start", "DimDate", "full_date", True),
    ("Anomalies", "metric_date", "DimDate", "full_date", True),
    ("SynInventoryWeekly", "week_start", "DimDate", "full_date", True),
]


def tag(*parts: str) -> str:
    return str(uuid.uuid5(NS, "|".join(parts)))


def q(name: str) -> str:
    """Quote a TMDL object name when needed."""
    return name if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) else "'" + name.replace("'", "''") + "'"


def infer_type(s: pd.Series, col: str) -> tuple[str, str, str | None]:
    """Return (tmdl dataType, M type, formatString)."""
    v = s.dropna().astype(str)
    if col.endswith("_key") or col in ("year", "quarter", "month", "iso_week", "day_of_month", "day_of_week",
                                        "items_count", "distinct_sellers", "payment_count", "order_item_id",
                                        "payment_sequential", "payment_installments", "review_score", "frequency",
                                        "recency_days", "r_score", "f_score", "m_score", "cluster", "votes", "orders",
                                        "delivery_delay_days", "version_number", "product_name_length",
                                        "product_description_length", "product_photos_qty", "horizon", "opening_stock",
                                        "received_units", "demand_units", "fulfilled_units", "lost_sales_units",
                                        "closing_stock", "reorder_point"):
        if v.empty or v.str.fullmatch(r"-?\d+").all():
            return "int64", "Int64.Type", "0"
    if not v.empty and v.isin(["true", "false"]).all():
        return "boolean", "type logical", None
    if not v.empty and v.str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
        return "dateTime", "type date", "yyyy-mm-dd"
    if not v.empty and v.str.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(\.\d+)?").all():
        return "dateTime", "type datetime", "yyyy-mm-dd hh:nn:ss"
    if not v.empty and v.str.fullmatch(r"-?\d+(\.\d+)?([eE][-+]?\d+)?").all():
        if MONEY.search(col):
            return "decimal", "Currency.Type", "#,0.00"
        return "double", "type number", "0.00"
    return "string", "type text", None


def m_query(table: str, csv: str, cols: list[tuple[str, str]]) -> str:
    typed = ", ".join(f'{{"{c}", {m}}}' for c, m in cols)
    keep = ", ".join(f'"{c}"' for c, _ in cols)
    lines = [
        "let",
        f'    Source = Csv.Document(File.Contents(DataFolder & "\\{csv}.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),',
        "    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),",
        f"    Selected = Table.SelectColumns(Promoted, {{{keep}}}),",
        f'    Typed = Table.TransformColumnTypes(Selected, {{{typed}}}, "en-US")',
    ]
    last = "Typed"
    if table == "FactOrders":   # incremental-refresh filter (RangeStart/RangeEnd parameters)
        lines[-1] += ","
        lines.append("    Incremental = Table.SelectRows(Typed, each [purchase_timestamp] >= RangeStart and [purchase_timestamp] < RangeEnd)")
        last = "Incremental"
    if table == "DimCustomer":
        lines[-1] += ","
        lines.append('    WithCohort = Table.AddColumn(Typed, "first_order_month", each if [first_order_date] = null then null '
                     'else Date.StartOfMonth([first_order_date]), type date)')
        last = "WithCohort"
    lines += ["in", f"    {last}"]
    return "\n".join(lines)


def column_tmdl(table: str, col: str, dtype: str, fmt: str | None, extra: list[str] | None = None) -> list[str]:
    hidden = bool(HIDDEN_KEYS.search(col)) and table != "DimDate"
    numeric = dtype in ("int64", "double", "decimal")
    summarize = "sum" if numeric and not hidden and not col.endswith(("_key", "score", "_days", "year", "month", "quarter",
                                                                        "cluster", "_id")) else "none"
    out = [f"{T}column {q(col)}", f"{T*2}dataType: {dtype}"]
    if fmt:
        out.append(f"{T*2}formatString: {fmt}")
    if hidden:
        out.append(f"{T*2}isHidden")
    out += [f"{T*2}lineageTag: {tag(table, col)}", f"{T*2}summarizeBy: {summarize}", f"{T*2}sourceColumn: {col}"]
    out += extra or []
    out += ["", f"{T*2}annotation SummarizationSetBy = Automatic", ""]
    return out


def table_tmdl(table: str, csv: str, desc: str) -> tuple[str, list[tuple[str, str]]]:
    df = pd.read_csv(CSV_DIR / f"{csv}.csv", nrows=20000, dtype=str, keep_default_na=False, na_values=[""])
    cols, body = [], []
    for c in df.columns:
        if c in DROP_COLS:
            continue
        dtype, mtype, fmt = infer_type(df[c], c)
        cols.append((c, mtype))
        extra = []
        if table == "DimDate" and c == "full_date":
            extra.append(f"{T*2}isKey")
        if table == "DimDate" and c in ("month_name", "month_short"):
            extra.append(f"{T*2}sortByColumn: month")
        if table == "DimDate" and c == "day_name":
            extra.append(f"{T*2}sortByColumn: day_of_week")
        if c in ("state", "customer_state", "seller_state"):
            extra.append(f"{T*2}dataCategory: StateOrProvince")
        if c == "city":
            extra.append(f"{T*2}dataCategory: City")
        if c == "latitude":
            extra.append(f"{T*2}dataCategory: Latitude")
        if c == "longitude":
            extra.append(f"{T*2}dataCategory: Longitude")
        if c == "zip_code_prefix":
            extra.append(f"{T*2}dataCategory: PostalCode")
        body += column_tmdl(table, c, dtype, fmt, extra)
    if table == "DimCustomer":
        body += column_tmdl(table, "first_order_month", "dateTime", "yyyy-mm")
    head = [f"/// {desc}", f"table {table}"]
    if table == "DimDate":
        head.append(f"{T}dataCategory: Time")
    head += [f"{T}lineageTag: {tag(table)}", ""]
    src = m_query(table, csv, cols)
    pq = PBI / "power_query"
    pq.mkdir(exist_ok=True)
    (pq / f"{table}.pq").write_text(f"// {table} – CSV import (parameter DataFolder)\n// {desc}\n{src}\n", encoding="utf-8")
    schema_name = "nexus_ml" if csv in ("customer_segments", "churn_scores", "revenue_forecast", "demand_forecast", "anomalies") \
        else "nexus_dw"
    if csv != "security_user_region":
        (pq / "postgresql").mkdir(exist_ok=True)
        (pq / "postgresql" / f"{table}.pq").write_text("\n".join([
            f"// {table} – DirectQuery/Import from PostgreSQL (parameters PgServer, PgDatabase)",
            "let",
            "    Source = PostgreSQL.Database(PgServer, PgDatabase),",
            f'    Data = Source{{[Schema = "{schema_name}", Item = "{csv}"]}}[Data]' + ("," if table == "FactOrders" else ""),
            *(["    Incremental = Table.SelectRows(Data, each [purchase_timestamp] >= RangeStart and [purchase_timestamp] < RangeEnd)"]
              if table == "FactOrders" else []),
            "in",
            f"    {'Incremental' if table == 'FactOrders' else 'Data'}", ""]), encoding="utf-8")
    part = [f"{T}partition {table} = m", f"{T*2}mode: import", f"{T*2}source ="] + [f"{T*4}{l}" for l in src.splitlines()]
    tail = ["", f"{T}annotation PBI_ResultType = Table", ""]
    return "\n".join(head + body + part + tail), cols


def measures_tmdl() -> str:
    out = ["/// Home table for all business measures (no data).", "table _Measures", f"{T}lineageTag: {tag('_Measures')}", ""]
    for name, expr, fmt, folder, desc in MEASURES:
        out.append(f"{T}/// {desc}")
        if "\n" in expr:
            out.append(f"{T}measure {q(name)} =")
            out += [f"{T*3}{l}" for l in expr.splitlines()]
        else:
            out.append(f"{T}measure {q(name)} = {expr}")
        if fmt:
            out.append(f"{T*2}formatString: {fmt}")
        out += [f"{T*2}displayFolder: {folder}", f"{T*2}lineageTag: {tag('_Measures', name)}", ""]
    out += [f"{T}column Placeholder", f"{T*2}dataType: string", f"{T*2}isHidden", f"{T*2}lineageTag: {tag('_Measures', 'col')}",
            f"{T*2}summarizeBy: none", f"{T*2}sourceColumn: [Placeholder]", "", f"{T*2}annotation SummarizationSetBy = Automatic", "",
            f"{T}partition _Measures = calculated", f"{T*2}mode: import", f'{T*2}source = ROW ( "Placeholder", "" )', "",
            f"{T}annotation PBI_ResultType = Table", ""]
    return "\n".join(out)


def kpi_selector_tmdl() -> str:
    kpis = ["Revenue", "Orders", "Customers", "Average Order Value", "On-Time Delivery %", "Avg Review Score"]
    rows = ", ".join(f'{{ "{k}", {i + 1} }}' for i, k in enumerate(kpis))
    return "\n".join([
        "/// Disconnected slicer table driving the [Selected KPI Value] dynamic measure.",
        "table 'KPI Selector'", f"{T}lineageTag: {tag('KPI Selector')}", "",
        f"{T}column KPI", f"{T*2}dataType: string", f"{T*2}lineageTag: {tag('KPI Selector', 'KPI')}", f"{T*2}summarizeBy: none",
        f"{T*2}sourceColumn: [KPI]", f"{T*2}sortByColumn: KPI_Order", "", f"{T*2}annotation SummarizationSetBy = Automatic", "",
        f"{T}column KPI_Order", f"{T*2}dataType: int64", f"{T*2}isHidden", f"{T*2}formatString: 0",
        f"{T*2}lineageTag: {tag('KPI Selector', 'KPI_Order')}", f"{T*2}summarizeBy: none", f"{T*2}sourceColumn: [KPI_Order]", "",
        f"{T*2}annotation SummarizationSetBy = Automatic", "",
        f"{T}partition 'KPI Selector' = calculated", f"{T*2}mode: import",
        f'{T*2}source = DATATABLE ( "KPI", STRING, "KPI_Order", INTEGER, {{ {rows} }} )', "",
        f"{T}annotation PBI_ResultType = Table", ""])


def field_parameter_tmdl() -> str:
    fields = ["Total Revenue", "Total Orders", "Unique Customers", "Average Order Value", "On-Time Delivery %", "Avg Review Score"]
    rows = ",\n".join(f'{T*4}("{f}", NAMEOF(\'_Measures\'[{f}]), {i})' for i, f in enumerate(fields))
    return "\n".join([
        "/// Field parameter: lets users swap the measure shown in a visual.",
        "table 'Metric Selector'", f"{T}lineageTag: {tag('Metric Selector')}", "",
        f"{T}column 'Metric Selector'", f"{T*2}dataType: string", f"{T*2}lineageTag: {tag('Metric Selector', 'name')}",
        f"{T*2}summarizeBy: none", f"{T*2}sourceColumn: [Value1]", f"{T*2}sortByColumn: 'Metric Selector Order'", "",
        f"{T*2}relatedColumnDetails", f"{T*3}groupByColumn: 'Metric Selector Fields'", "",
        f"{T*2}annotation SummarizationSetBy = Automatic", "",
        f"{T}column 'Metric Selector Fields'", f"{T*2}dataType: string", f"{T*2}isHidden",
        f"{T*2}lineageTag: {tag('Metric Selector', 'fields')}", f"{T*2}summarizeBy: none", f"{T*2}sourceColumn: [Value2]",
        f"{T*2}sortByColumn: 'Metric Selector Order'", "", f"{T*2}extendedProperty ParameterMetadata =",
        f"{T*4}{{", f'{T*4}  "version": 3,', f'{T*4}  "kind": 2', f"{T*4}}}", "",
        f"{T*2}annotation SummarizationSetBy = Automatic", "",
        f"{T}column 'Metric Selector Order'", f"{T*2}dataType: int64", f"{T*2}isHidden", f"{T*2}formatString: 0",
        f"{T*2}lineageTag: {tag('Metric Selector', 'order')}", f"{T*2}summarizeBy: sum", f"{T*2}sourceColumn: [Value3]", "",
        f"{T*2}annotation SummarizationSetBy = Automatic", "",
        f"{T}partition 'Metric Selector' = calculated", f"{T*2}mode: import", f"{T*2}source =", f"{T*4}{{", rows, f"{T*4}}}", "",
        f"{T}annotation PBI_ResultType = Table", ""])


def roles_tmdl() -> dict[str, str]:
    roles = {}
    dyn = ("DimCustomer[region] IN CALCULATETABLE ( VALUES ( SecurityUserRegion[region] ), "
           "SecurityUserRegion[user_email] = USERPRINCIPALNAME () )")
    roles["Regional Manager (Dynamic)"] = "\n".join([
        "/// Dynamic RLS: users see customers of the regions mapped to their UPN in SecurityUserRegion.",
        "role 'Regional Manager (Dynamic)'", f"{T}modelPermission: read", "",
        f"{T}tablePermission DimCustomer = {dyn}", "",
        f"{T}tablePermission SecurityUserRegion = SecurityUserRegion[user_email] = USERPRINCIPALNAME ()", ""])
    for region in ["Sudeste", "Sul", "Nordeste", "Centro-Oeste", "Norte"]:
        roles[f"Region {region}"] = "\n".join([
            f"/// Static RLS: only customers in region {region}.", f"role 'Region {region}'", f"{T}modelPermission: read", "",
            f'{T}tablePermission DimCustomer = DimCustomer[region] = "{region}"', ""])
    roles["Executive (All Data)"] = "\n".join(["/// Full access.", "role 'Executive (All Data)'", f"{T}modelPermission: read", ""])
    return roles


def write_security_csv() -> None:
    p = CSV_DIR / "security_user_region.csv"
    pd.DataFrame({"user_email": ["ceo@example.com"] * 5 + ["south.manager@example.com", "southeast.manager@example.com",
                                                             "northeast.manager@example.com"],
                  "region": ["Sudeste", "Sul", "Nordeste", "Centro-Oeste", "Norte", "Sul", "Sudeste", "Nordeste"]}).to_csv(p, index=False)


def build_model(data_folder: str) -> dict[str, list[str]]:
    write_security_csv()
    if SM.exists():
        shutil.rmtree(SM)
    (SM / "definition" / "tables").mkdir(parents=True)
    (SM / "definition" / "roles").mkdir(parents=True)
    schema: dict[str, list[str]] = {}
    for t, (csv, desc) in TABLES.items():
        text, cols = table_tmdl(t, csv, desc)
        (SM / "definition" / "tables" / f"{t}.tmdl").write_text(text, encoding="utf-8")
        schema[t] = [c for c, _ in cols] + (["first_order_month"] if t == "DimCustomer" else [])
    (SM / "definition" / "tables" / "_Measures.tmdl").write_text(measures_tmdl(), encoding="utf-8")
    (SM / "definition" / "tables" / "KPI Selector.tmdl").write_text(kpi_selector_tmdl(), encoding="utf-8")
    (SM / "definition" / "tables" / "Metric Selector.tmdl").write_text(field_parameter_tmdl(), encoding="utf-8")
    schema["_Measures"] = [m[0] for m in MEASURES]
    schema["KPI Selector"] = ["KPI", "KPI_Order"]
    schema["Metric Selector"] = ["Metric Selector", "Metric Selector Fields", "Metric Selector Order"]
    for name, text in roles_tmdl().items():
        (SM / "definition" / "roles" / f"{name}.tmdl").write_text(text, encoding="utf-8")

    rel = []
    for ft, fc, tt, tc, active in RELATIONSHIPS:
        rel += [f"relationship {tag('rel', ft, fc, tt, tc)}"]
        if not active:
            rel.append(f"{T}isActive: false")
        rel += [f"{T}fromColumn: {q(ft)}.{q(fc)}", f"{T}toColumn: {q(tt)}.{q(tc)}", ""]
    (SM / "definition" / "relationships.tmdl").write_text("\n".join(rel), encoding="utf-8")

    df = data_folder.replace('"', '""')
    expr = "\n".join([
        f'expression DataFolder = "{df}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
        f"{T}lineageTag: {tag('param', 'DataFolder')}", "", f"{T}annotation PBI_ResultType = Text", "",
        'expression RangeStart = #datetime(2016, 1, 1, 0, 0, 0) meta [IsParameterQuery=true, Type="DateTime", IsParameterQueryRequired=true]',
        f"{T}lineageTag: {tag('param', 'RangeStart')}", "", f"{T}annotation PBI_ResultType = DateTime", "",
        'expression RangeEnd = #datetime(2030, 1, 1, 0, 0, 0) meta [IsParameterQuery=true, Type="DateTime", IsParameterQueryRequired=true]',
        f"{T}lineageTag: {tag('param', 'RangeEnd')}", "", f"{T}annotation PBI_ResultType = DateTime", ""])
    (SM / "definition" / "expressions.tmdl").write_text(expr, encoding="utf-8")

    all_tables = list(TABLES) + ["_Measures", "KPI Selector", "Metric Selector"]
    model = ["model Model", f"{T}culture: en-US", f"{T}defaultPowerBIDataSourceVersion: powerBI_V3",
             f"{T}discourageImplicitMeasures", f"{T}sourceQueryCulture: en-US", f"{T}dataAccessOptions",
             f"{T*2}legacyRedirects", f"{T*2}returnErrorValuesAsNull", "",
             f'annotation PBI_QueryOrder = {json.dumps(["DataFolder", "RangeStart", "RangeEnd"] + list(TABLES))}', "",
             "annotation __PBI_TimeIntelligenceEnabled = 0", "",
             'annotation PBI_ProTooling = ["DevMode"]', ""] + [f"ref table {q(t)}" for t in all_tables] + [""] + \
            [f"ref role {q(r)}" for r in roles_tmdl()] + [""]
    (SM / "definition" / "model.tmdl").write_text("\n".join(model), encoding="utf-8")
    (SM / "definition" / "database.tmdl").write_text("database\n\tcompatibilityLevel: 1567\n", encoding="utf-8")
    (SM / "definition.pbism").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2", "settings": {}}, indent=2), encoding="utf-8")
    (SM / ".platform").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "SemanticModel", "displayName": "NexusBI"},
        "config": {"version": "2.0", "logicalId": tag("semanticmodel")}}, indent=2), encoding="utf-8")
    return schema


# ------------------------------------------------------------------------------------------- report (PBIR)
VC = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.4.0/schema.json"
PAGE = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"


def fld(entity: str, prop: str, measure: bool) -> dict:
    kind = "Measure" if measure else "Column"
    return {kind: {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}}


def proj(entity: str, prop: str, measure: bool) -> dict:
    return {"field": fld(entity, prop, measure), "queryRef": f"{entity}.{prop}", "nativeQueryRef": prop}


def M(name):
    return ("_Measures", name, True)


def C(table, col):
    return (table, col, False)


def lit(v):
    """PBIR Literal expression: strings quoted, numbers as D (double), booleans as true/false."""
    if isinstance(v, bool):
        return {"expr": {"Literal": {"Value": "true" if v else "false"}}}
    if isinstance(v, (int, float)):
        return {"expr": {"Literal": {"Value": f"{v}D"}}}
    return {"expr": {"Literal": {"Value": "'" + str(v).replace("'", "''") + "'"}}}


def solid(color):
    return {"solid": {"color": lit(color)}}


def mcolor(measure: str):
    """Colour driven by a DAX measure (conditional formatting 'fx -> field value')."""
    return {"solid": {"color": {"expr": fld("_Measures", measure, True)}}}


ALL_POINTS = {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}

# ----- design tokens: dark navy canvas, white panels, vivid WCAG-AA tiles (>= 4.5:1 with white text)
CANVAS = "#0B1F3A"
PANEL = "#FFFFFF"
INK = "#0B1F3A"
TILES = ["#0F766E", "#4338CA", "#BE185D", "#B45309", "#6D28D9", "#0369A1"]
ACCENTS = ["#0D9488", "#4F46E5", "#DB2777", "#D97706", "#7C3AED", "#0284C7"]


def visual(name, vtype, x, y, w, h, buckets: dict, title: str | None = None, objects: dict | None = None,
           accent: str = "#0D9488", panel: bool = True, z=0):
    v = {"visualType": vtype, "drillFilterOtherVisuals": True}
    if buckets:
        v["query"] = {"queryState": {b: {"projections": [proj(*f) for f in fields]} for b, fields in buckets.items()}}
    vco = {}
    if title:
        vco["title"] = [{"properties": {"show": lit(True), "text": lit(title), "fontColor": solid(accent),
                                        "fontSize": lit(11), "bold": lit(True)}}]
    if panel:
        vco["background"] = [{"properties": {"show": lit(True), "color": solid(PANEL), "transparency": lit(0)}}]
        vco["border"] = [{"properties": {"show": lit(True), "color": solid(accent), "radius": lit(10)}}]
        vco["dropShadow"] = [{"properties": {"show": lit(True)}}]
    if vco:
        v["visualContainerObjects"] = vco
    if objects:
        v["objects"] = objects
    return {"$schema": VC, "name": name, "position": {"x": x, "y": y, "z": z, "width": w, "height": h, "tabOrder": z},
            "visual": v}


def textbox(name, text, x, y, w, h, size=20, color="#FFFFFF"):
    return {"$schema": VC, "name": name, "position": {"x": x, "y": y, "z": 0, "width": w, "height": h},
            "visual": {"visualType": "textbox", "objects": {"general": [{"properties": {"paragraphs": [{
                "textRuns": [{"value": text, "textStyle": {"fontWeight": "bold", "fontSize": f"{size}pt", "color": color}}]}]}}]}}}


def color_rule(measure_for_value: str, color_measure: str) -> dict:
    return {"values": [{"properties": {"fontColor": mcolor(color_measure)},
                        "selector": {"metadata": f"_Measures.{measure_for_value}"}}]}


def kpi_tile(name, measure, x, y, w, h, color):
    """Vivid KPI tile: coloured background, white value + label."""
    v = visual(name, "card", x, y, w, h, {"Values": [M(measure)]}, panel=False,
               objects={"labels": [{"properties": {"color": solid("#FFFFFF"), "fontSize": lit(24)}}],
                        "categoryLabels": [{"properties": {"show": lit(True), "color": solid("#FFFFFF"), "fontSize": lit(10)}}]})
    v["visual"]["visualContainerObjects"] = {
        "background": [{"properties": {"show": lit(True), "color": solid(color), "transparency": lit(0)}}],
        "border": [{"properties": {"show": lit(True), "color": solid(color), "radius": lit(12)}}],
        "dropShadow": [{"properties": {"show": lit(True)}}]}
    return v


def kpis(prefix, measures, y=104):
    w, gap, x0 = 200, 12, 18
    return [kpi_tile(f"{prefix}Card{i}", m, x0 + i * (w + gap), y, w, 86, TILES[i % len(TILES)])
            for i, m in enumerate(measures)]


def slicer(name, field, x, y, w, h, title, mode="Dropdown"):
    obj = {"data": [{"properties": {"mode": lit(mode)}}]}
    return visual(name, "slicer", x, y, w, h, {"Values": [field]}, title, objects=obj, accent="#4F46E5")


def header(prefix, title, slicers: list[tuple]):
    """Title, up to 4 slicers in the top band, and the built-in page navigator."""
    out = [textbox(f"{prefix}Title", title, 18, 6, 360, 44, size=20)]
    x = 390
    for i, (field, label, mode) in enumerate(slicers):
        out.append(slicer(f"{prefix}Slicer{i}", field, x, 4, 214, 52, label, mode))
        x += 222
    nav = visual(f"{prefix}Nav", "pageNavigator", 18, 60, 1244, 36, {}, panel=False)
    out.append(nav)
    return out


def labels_on(extra: dict | None = None) -> dict:
    o = {"labels": [{"properties": {"show": lit(True)}}]}
    o.update(extra or {})
    return o


def fill_by(measure: str) -> dict:
    return {"dataPoint": [{"properties": {"fill": mcolor(measure)}, "selector": ALL_POINTS}]}


ROW1, ROW2, RH = 202, 460, 250


def pages() -> list[tuple[str, str, list[dict]]]:
    D = lambda c: C("DimDate", c)  # noqa: E731
    P = []
    # ================================================================== 1 Executive
    v = header("exec", "Executive Command Center", [
        (D("year"), "Year", "Dropdown"), (C("DimCustomer", "region"), "Region", "Dropdown"),
        (C("DimProduct", "category_display_name"), "Category", "Dropdown"), (D("full_date"), "Date range", "Between")])
    v += kpis("exec", ["Total Revenue", "Total Orders", "Unique Customers", "Average Order Value", "Revenue YoY %",
                       "On-Time Delivery %"])
    v += [
        visual("execTrend", "areaChart", 18, ROW1, 610, RH,
               {"Category": [D("year"), D("quarter_label"), D("month_start")], "Y": [M("Total Revenue"), M("Revenue PY")]},
               "Revenue vs prior year – drill year › quarter › month", accent=ACCENTS[0]),
        visual("execPayments", "donutChart", 640, ROW1, 300, RH,
               {"Category": [C("DimPaymentType", "payment_type_label")], "Y": [M("Total Revenue")]},
               "Revenue by payment method", objects=labels_on(), accent=ACCENTS[1]),
        visual("execGauge", "gauge", 952, ROW1, 310, RH,
               {"Y": [M("On-Time Delivery %")], "MinValue": [M("Gauge Min")], "MaxValue": [M("Gauge Max %")],
                "TargetValue": [M("Target On-Time %")]}, "On-time delivery vs 90% target", accent=ACCENTS[2]),
        visual("execCategory", "treemap", 18, ROW2, 420, RH,
               {"Group": [C("DimProduct", "category_display_name")], "Values": [M("Item Revenue")]},
               "Category revenue – click a tile to filter the page", accent=ACCENTS[3]),
        visual("execState", "clusteredColumnChart", 450, ROW2, 410, RH,
               {"Category": [C("DimCustomer", "state")], "Y": [M("Total Revenue")]},
               "Revenue by state (heat colours)", objects=fill_by("Color State Revenue"), accent=ACCENTS[4]),
        visual("execRibbon", "ribbonChart", 872, ROW2, 390, RH,
               {"Category": [D("quarter_label")], "Series": [C("DimCustomer", "region")], "Y": [M("Total Revenue")]},
               "Regional revenue ranking by quarter", accent=ACCENTS[5]),
    ]
    P.append(("ExecutiveCommandCenter", "Executive Command Center", v))
    # ================================================================== 2 Customer
    v = header("cust", "Customer Intelligence", [
        (D("year"), "Year", "Dropdown"), (C("DimCustomer", "region"), "Region", "Dropdown"),
        (C("DimCustomer", "state"), "State", "Dropdown"), (C("CustomerSegments", "cluster_name"), "ML segment", "Dropdown")])
    v += kpis("cust", ["Unique Customers", "Repeat Customer Rate", "Revenue per Customer", "Estimated CLV",
                       "Avg Churn Probability", "High Risk Customers"])
    v += [
        visual("custSegments", "donutChart", 18, ROW1, 330, RH,
               {"Category": [C("CustomerSegments", "cluster_name")], "Y": [M("Segment Customers")]},
               "ML customer segments", objects=labels_on(), accent=ACCENTS[0]),
        visual("custScatter", "scatterChart", 360, ROW1, 520, RH,
               {"Category": [C("DimCustomer", "state")], "Series": [C("DimCustomer", "region")],
                "X": [M("Revenue per Customer")], "Y": [M("Repeat Customer Rate")], "Size": [M("Unique Customers")]},
               "States: value per customer vs repeat rate (bubble = customers)", accent=ACCENTS[1]),
        visual("custRfm", "clusteredBarChart", 892, ROW1, 370, RH,
               {"Category": [C("CustomerSegments", "rfm_segment")], "Y": [M("Segment Customers")]},
               "RFM segments", objects=labels_on(fill_by("Color RFM Segment")), accent=ACCENTS[2]),
        visual("custCohort", "pivotTable", 18, ROW2, 820, RH,
               {"Rows": [C("DimCustomer", "first_order_month")], "Columns": [D("month_start")], "Values": [M("Active Customers")]},
               "Acquisition cohorts – active customers by month (heat map)",
               objects={"values": [{"properties": {"backColor": mcolor("Color Cohort Heat")},
                                    "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}],
                                                 "metadata": "_Measures.Active Customers"}}]}, accent=ACCENTS[3]),
        visual("custRegion", "hundredPercentStackedColumnChart", 850, ROW2, 412, RH,
               {"Category": [C("DimCustomer", "region")], "Series": [C("CustomerSegments", "cluster_name")],
                "Y": [M("Unique Customers")]}, "Segment mix by region", accent=ACCENTS[4]),
    ]
    P.append(("CustomerIntelligence", "Customer Intelligence", v))
    # ================================================================== 3 Operations
    v = header("ops", "Operations Intelligence", [
        (D("year"), "Year", "Dropdown"), (C("DimCustomer", "region"), "Customer region", "Dropdown"),
        (C("DimSeller", "state"), "Seller state", "Dropdown"), (D("full_date"), "Date range", "Between")])
    v += kpis("ops", ["On-Time Delivery %", "Avg Delivery Days", "Late Orders", "Avg Delay of Late Orders",
                      "Cancellation Rate", "Avg Review Score"])
    v += [
        visual("opsTrend", "lineClusteredColumnComboChart", 18, ROW1, 560, RH,
               {"Category": [D("year"), D("month_start")], "Y": [M("Avg Delivery Days")], "Y2": [M("On-Time Delivery %")]},
               "Delivery days (columns) and on-time % (line)", accent=ACCENTS[0]),
        visual("opsReviews", "clusteredColumnChart", 590, ROW1, 360, RH,
               {"Category": [C("FactReviews", "review_score")], "Y": [M("Review Count")]},
               "Review score distribution", objects=labels_on(fill_by("Color Review Score")), accent=ACCENTS[1]),
        visual("opsGauge", "gauge", 962, ROW1, 300, RH,
               {"Y": [M("Avg Review Score")], "MinValue": [M("Gauge Min")], "MaxValue": [M("Gauge Max Review")],
                "TargetValue": [M("Target Review")]}, "Average review vs 4.0 target", accent=ACCENTS[2]),
        visual("opsState", "clusteredColumnChart", 18, ROW2, 520, RH,
               {"Category": [C("DimCustomer", "state")], "Y": [M("Late Delivery %")]},
               "Late-delivery rate by state (green → red)", objects=fill_by("Color State Late"), accent=ACCENTS[3]),
        visual("opsSellerScatter", "scatterChart", 550, ROW2, 360, RH,
               {"Category": [C("DimSeller", "seller_id")], "Series": [C("DimSeller", "region")],
                "X": [M("Item Revenue")], "Y": [M("Seller Avg Review")], "Size": [M("Items Sold")]},
               "Sellers: revenue vs review", accent=ACCENTS[4]),
        visual("opsSellers", "tableEx", 922, ROW2, 340, RH,
               {"Values": [C("DimSeller", "seller_id"), M("Item Revenue"), M("Seller On-Time %"), M("Seller Avg Review")]},
               "Seller scorecard (right-click → Drill through)",
               objects=color_rule("Seller On-Time %", "Color Seller On-Time"), accent=ACCENTS[5]),
    ]
    P.append(("OperationsIntelligence", "Operations Intelligence", v))
    # ================================================================== 4 Predictive
    v = header("pred", "Predictive Intelligence", [
        (C("RevenueForecast", "model_name"), "Forecast model", "Dropdown"),
        (C("DemandForecast", "category"), "Demand category", "Dropdown"),
        (C("ChurnScores", "risk_band"), "Churn risk band", "Dropdown"), (D("full_date"), "Date range", "Between")])
    v += kpis("pred", ["Forecast Revenue", "Forecast MAPE", "Demand Forecast Units", "Avg Churn Probability",
                       "High Risk Customers", "Anomaly Days"])
    v += [
        visual("predRevenue", "lineChart", 18, ROW1, 820, RH,
               {"Category": [D("full_date")], "Y": [M("Backtest Actual"), M("Forecast Revenue"), M("Forecast Lower 95"),
                                                    M("Forecast Upper 95")]},
               "Revenue: actual vs predicted with 95% interval", accent=ACCENTS[0]),
        visual("predChurn", "donutChart", 850, ROW1, 412, RH,
               {"Category": [C("ChurnScores", "risk_band")], "Y": [M("Scored Customers")]},
               "Customers by churn risk band", objects=labels_on(fill_by("Color Risk Band")), accent=ACCENTS[1]),
        visual("predDemand", "stackedAreaChart", 18, ROW2, 520, RH,
               {"Category": [C("DemandForecast", "week_start")], "Series": [C("DemandForecast", "category")],
                "Y": [M("Demand Forecast Units")]}, "Weekly demand forecast by category", accent=ACCENTS[2]),
        visual("predAnomalyMonths", "clusteredColumnChart", 550, ROW2, 330, RH,
               {"Category": [D("month_start")], "Y": [M("Anomaly Days")]}, "Anomaly days per month",
               objects=labels_on(fill_by("Color Alert")), accent=ACCENTS[3]),
        visual("predAnomalies", "tableEx", 892, ROW2, 370, RH,
               {"Values": [C("Anomalies", "metric_date"), C("Anomalies", "severity"), C("Anomalies", "direction"),
                           M("Anomaly Revenue")]}, "Anomaly alerts", accent=ACCENTS[4]),
    ]
    P.append(("PredictiveIntelligence", "Predictive Intelligence", v))
    # ================================================================== 5 Seller drill-through
    v = [textbox("sdTitle", "Seller Detail (drill-through)", 18, 6, 800, 44)]
    v += kpis("sd", ["Item Revenue", "Seller Orders", "Seller On-Time %", "Seller Avg Review", "Freight Ratio",
                     "Seller Revenue Rank"], y=60)
    v += [visual("sdTrend", "areaChart", 18, 160, 820, 270, {"Category": [D("month_start")], "Y": [M("Item Revenue")]},
                 "Seller monthly item revenue", accent=ACCENTS[0]),
          visual("sdCategory", "donutChart", 850, 160, 412, 270, {"Category": [C("DimProduct", "category_display_name")],
                                                                   "Y": [M("Item Revenue")]}, "Seller category mix",
                 objects=labels_on(), accent=ACCENTS[1]),
          visual("sdStates", "clusteredBarChart", 18, 442, 1244, 270, {"Category": [C("DimCustomer", "state")],
                                                                        "Y": [M("Item Revenue")]},
                 "Where this seller's customers are", objects=fill_by("Color State Revenue"), accent=ACCENTS[2])]
    P.append(("SellerDetail", "Seller Detail", v))
    # ================================================================== 6 Tooltip page
    v = [visual("ttCard", "card", 10, 10, 300, 90, {"Values": [M("Item Revenue")]}),
         visual("ttTrend", "areaChart", 10, 105, 300, 125, {"Category": [D("month_start")], "Y": [M("Item Revenue")]})]
    P.append(("CategoryTooltip", "Category Tooltip", v))
    return P


# ------------------------------------------------------------------ accessibility (WCAG 2.1 / EN 301 549)
# Same output format as the pbip-accessibility audit tool: alt text in
# visualContainerObjects.general[0].properties.altText (quoted Literal) and position.tabOrder in DESCENDING
# multiples of 1000 (highest = first focus) following reading order: top-to-bottom, then left-to-right.
TYPE_PHRASE = {
    "card": "KPI card showing", "lineChart": "Line chart showing", "clusteredBarChart": "Bar chart comparing",
    "clusteredColumnChart": "Column chart comparing", "tableEx": "Table listing", "pivotTable": "Matrix showing",
    "lineClusteredColumnComboChart": "Combined line and column chart showing",
    "donutChart": "Donut chart showing", "treemap": "Treemap showing", "scatterChart": "Scatter chart showing",
    "gauge": "Gauge showing", "areaChart": "Area chart showing", "stackedAreaChart": "Stacked area chart showing",
    "ribbonChart": "Ribbon chart showing", "hundredPercentStackedColumnChart": "100% stacked column chart showing",
}
FRIENDLY_FIELD = {"year": "year", "model_name": "forecast model", "Metric Selector": "the metric shown in the trend chart",
                  "month_start": "month", "full_date": "date", "week_start": "week"}
BUILDER_NOTES = re.compile(r"\s*\((filter [^)]*|right-click[^)]*|field parameter)\)")


def _fields(v: dict, bucket: str) -> list[str]:
    return [p["field"][next(iter(p["field"]))]["Property"]
            for p in v["visual"].get("query", {}).get("queryState", {}).get(bucket, {}).get("projections", [])]


def _title(v: dict) -> str | None:
    t = v["visual"].get("visualContainerObjects", {}).get("title")
    return t[0]["properties"]["text"]["expr"]["Literal"]["Value"].strip("'") if t else None


def alt_text(v: dict) -> str:
    vt = v["visual"]["visualType"]
    if vt == "textbox":
        runs = v["visual"]["objects"]["general"][0]["properties"]["paragraphs"][0]["textRuns"]
        return f"Page title: {''.join(r['value'] for r in runs)}"
    if vt == "pageNavigator":
        return "Page navigation: buttons to move between the report pages."
    if vt == "slicer":
        f = _fields(v, "Values")[0]
        return f"Slicer to filter the page by {FRIENDLY_FIELD.get(f, f.replace('_', ' '))}."
    if vt == "card":
        return f"KPI card showing {_fields(v, 'Values')[0]}."
    title = _title(v)
    if title:   # sentence-case the title after the type phrase ("Monthly revenue" -> "monthly revenue"; keep "RFM")
        subject = BUILDER_NOTES.sub("", title)
        if subject[:1].isupper() and not subject[:2].isupper():
            subject = subject[0].lower() + subject[1:]
    else:       # untitled visual: name its measures (verbatim) by category
        y = " and ".join(_fields(v, "Y")) or "values"
        cat = _fields(v, "Category")
        subject = f"{y} by {FRIENDLY_FIELD.get(cat[0], cat[0])}" if cat else y
    text = f"{TYPE_PHRASE.get(vt, 'Visual showing')} {subject}."
    if "click a tile" in (title or ""):
        text = text.replace(" – click a tile to filter the page", "") + " Select a tile to filter the other visuals."
    if "drill year" in (title or ""):
        text = text.replace(" – drill year › quarter › month", "") + " Drill down from year to quarter to month."
    if "right-click" in (title or ""):
        text += " Right-click a row and choose Drill through to open the seller detail page."
    return text


def reading_order(visuals: list[dict]) -> list[dict]:
    """Rows by vertical overlap (>= half the height of the shorter visual), then left-to-right;
    a page-title textbox in the first row receives focus first (same rule as the audit tool)."""
    rows: list[list[dict]] = []
    for v in sorted(visuals, key=lambda v: v["position"]["y"]):
        p = v["position"]
        for row in rows:
            r = row[0]["position"]
            overlap = min(p["y"] + p["height"], r["y"] + r["height"]) - max(p["y"], r["y"])
            if overlap >= 0.5 * min(p["height"], r["height"]):
                row.append(v)
                break
        else:
            rows.append([v])
    order = [v for row in rows for v in sorted(row, key=lambda v: v["position"]["x"])]
    titles = [v for v in rows[0] if v["visual"]["visualType"] == "textbox"] if rows else []
    return titles + [v for v in order if v not in titles]


def apply_accessibility(visuals: list[dict]) -> None:
    order = reading_order(visuals)
    for i, v in enumerate(order):
        v["position"]["tabOrder"] = (len(order) - i) * 1000
        vco = v["visual"].setdefault("visualContainerObjects", {})
        vco["general"] = [{"properties": {"altText": {"expr": {"Literal": {"Value": "'" + alt_text(v).replace("'", "''") + "'"}}}}}]


def build_report(schema: dict[str, list[str]]) -> list[str]:
    if RP.exists():
        shutil.rmtree(RP)
    d = RP / "definition"
    (d / "pages").mkdir(parents=True)
    theme_src = PBI / "NexusBI_Theme.json"
    res = RP / "StaticResources" / "RegisteredResources"
    res.mkdir(parents=True)
    shutil.copy(theme_src, res / "NexusBI_Theme.json")
    (RP / "definition.pbir").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byPath": {"path": "../NexusBI.SemanticModel"}}}, indent=2), encoding="utf-8")
    (RP / ".platform").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report", "displayName": "NexusBI"}, "config": {"version": "2.0", "logicalId": tag("report")}},
        indent=2), encoding="utf-8")
    (d / "version.json").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
        "version": "2.0.0"}, indent=2), encoding="utf-8")
    (d / "report.json").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.0.0/schema.json",
        "themeCollection": {"customTheme": {"name": "NexusBI_Theme.json", "reportVersionAtImport": {"visual": "2.4.0", "report": "3.0.0", "page": "2.1.0"},
                                            "type": "RegisteredResources"}},
        "resourcePackages": [{"name": "RegisteredResources", "type": "RegisteredResources",
                              "items": [{"name": "NexusBI_Theme.json", "path": "NexusBI_Theme.json", "type": "CustomTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True, "defaultDrillFilterOtherVisuals": True,
                     "allowChangeFilterTypes": True, "useEnhancedTooltips": True}}, indent=2), encoding="utf-8")
    errors, order = [], []
    for pname, display, visuals in pages():
        order.append(pname)
        pd_ = d / "pages" / pname
        (pd_ / "visuals").mkdir(parents=True)
        page = {"$schema": PAGE, "name": pname, "displayName": display, "displayOption": "FitToPage", "height": 720, "width": 1280}
        if pname == "CategoryTooltip":
            page.update(height=240, width=320, visibility="HiddenInViewMode")
        if pname == "SellerDetail":
            page["visibility"] = "HiddenInViewMode"
        (pd_ / "page.json").write_text(json.dumps(page, indent=2), encoding="utf-8")
        apply_accessibility(visuals)
        for v in visuals:
            for b in v["visual"].get("query", {}).get("queryState", {}).values():
                for p in b["projections"]:
                    f = p["field"]
                    k = "Measure" if "Measure" in f else "Column"
                    ent, prop = f[k]["Expression"]["SourceRef"]["Entity"], f[k]["Property"]
                    if prop not in schema.get(ent, []):
                        errors.append(f"{pname}/{v['name']}: {ent}.{prop} not in model")
            (pd_ / "visuals" / v["name"]).mkdir()
            (pd_ / "visuals" / v["name"] / "visual.json").write_text(json.dumps(v, indent=2), encoding="utf-8")
    (d / "pages" / "pages.json").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": order, "activePageName": order[0]}, indent=2), encoding="utf-8")
    (PBI / "NexusBI.pbip").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0", "artifacts": [{"report": {"path": "NexusBI.Report"}}], "settings": {"enableAutoRecovery": True}},
        indent=2), encoding="utf-8")
    return errors


DASH_FOLDERS = {"ExecutiveCommandCenter": "executive_dashboard", "CustomerIntelligence": "customer_dashboard",
                "OperationsIntelligence": "operations_dashboard", "PredictiveIntelligence": "predictive_dashboard",
                "SellerDetail": "sales_dashboard", "CategoryTooltip": "sales_dashboard"}


def write_dashboard_specs() -> None:
    """One DASHBOARD_SPEC.md per dashboard folder, generated from the same page spec as the report."""
    desc = {m[0]: m[4] for m in MEASURES}
    specs: dict[str, list[str]] = {}
    for pname, display, visuals in pages():
        L = specs.setdefault(DASH_FOLDERS[pname], [])
        L += [f"## Page: {display} (`{pname}`)", "", "| Visual | Type | Position (x,y,w,h) | Fields |", "|---|---|---|---|"]
        used = set()
        for v in visuals:
            fields = []
            for bucket, b in v["visual"].get("query", {}).get("queryState", {}).items():
                for pr in b["projections"]:
                    fields.append(f"{bucket}: `{pr['queryRef']}`")
                    if pr["queryRef"].startswith("_Measures."):
                        used.add(pr["queryRef"].split(".", 1)[1])
            pos = v["position"]
            L.append(f"| {v['name']} | {v['visual']['visualType']} | {pos['x']},{pos['y']},{pos['width']},{pos['height']} | "
                     f"{'<br>'.join(fields) or '–'} |")
        L += ["", "**Measures used**", ""] + [f"- `[{m}]` – {desc.get(m, '')}" for m in sorted(used)] + [""]
        if pname == "SellerDetail":
            L += ["**Manual step in Power BI Desktop:** select this page → *Visualizations › Drill through* → drag "
                  "`DimSeller[seller_id]` into the drill-through well (keep *Keep all filters* on).", ""]
        if pname == "CategoryTooltip":
            L += ["**Manual step:** *Format page › Page information* → turn **Allow use as tooltip** on; on the Executive "
                  "'Category performance' bar chart set *Tooltips › Type = Report page, Page = Category Tooltip*.", ""]
    for folder, body in specs.items():
        out = PBI / folder
        out.mkdir(exist_ok=True)
        head = [f"# {folder.replace('_', ' ').title()} – specification", "",
                "_Generated by `powerbi/build_pbip.py` from the same definition used to write the PBIR report, so it always "
                "matches `NexusBI.Report`. Validation: `python powerbi/validate_pbip.py`._", ""]
        (out / "DASHBOARD_SPEC.md").write_text("\n".join(head + body), encoding="utf-8")


def write_dax_library() -> None:
    lines = ["// NEXUS BI – DAX measure library (generated from powerbi/dax/measures.py)", "// Home table: _Measures", ""]
    for name, expr, fmt, folder, desc in MEASURES:
        lines += [f"// {folder} | {desc}" + (f" | format: {fmt}" if fmt else ""), f"[{name}] :=", expr, ""]
    (PBI / "dax" / "NexusBI_Measures.dax").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--data-folder", default=r"C:\NEXUS-BI\data\processed\powerbi",
                   help="absolute Windows path of data/processed/powerbi on the machine running Power BI Desktop")
    args = a.parse_args()
    schema = build_model(args.data_folder)
    errors = build_report(schema)
    write_dax_library()
    write_dashboard_specs()
    (PBI / "model_schema.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")
    print(f"tables={len(schema)} measures={len(MEASURES)} relationships={len(RELATIONSHIPS)} field_errors={len(errors)}")
    for e in errors:
        print("  ERROR", e)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
