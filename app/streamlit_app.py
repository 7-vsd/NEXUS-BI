"""NEXUS BI – Streamlit application entry point.

Run:  streamlit run app/streamlit_app.py
Requires the processed marts (python -m src.pipeline) and, for KPI cards and
predictions, the API (uvicorn api.main:app --port 8000).
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from app.components.data import DataMissing, REGION_OF, load, pretty  # noqa: E402
from app.components.theme import inject_css, register_plotly_templates  # noqa: E402

st.set_page_config(page_title="NEXUS BI", page_icon="📊", layout="wide", initial_sidebar_state="expanded")
register_plotly_templates()

PAGES = [
    st.Page("pages/1_Executive_Overview.py", title="Executive Overview", icon="🏛️", default=True),
    st.Page("pages/2_Revenue_Intelligence.py", title="Revenue Intelligence", icon="💰"),
    st.Page("pages/3_Sales_Analytics.py", title="Sales Analytics", icon="🛒"),
    st.Page("pages/4_Customer_Intelligence.py", title="Customer Intelligence", icon="👥"),
    st.Page("pages/5_Operations_Analytics.py", title="Operations Analytics", icon="🚚"),
    st.Page("pages/6_Predictive_Analytics.py", title="Predictive Analytics", icon="🔮"),
    st.Page("pages/7_Anomaly_Monitoring.py", title="Anomaly Monitoring", icon="🚨"),
    st.Page("pages/8_Data_Quality.py", title="Data Quality", icon="🧪"),
    st.Page("pages/9_System_Monitoring.py", title="System Monitoring", icon="🖥️"),
]


def sidebar() -> None:
    with st.sidebar:
        st.markdown("### 📊 NEXUS BI")
        st.caption("Transforming Business Data into Intelligent Business Decisions")
        mode = st.toggle("Dark theme", value=st.session_state.get("theme_mode", "dark") == "dark")
        st.session_state["theme_mode"] = "dark" if mode else "light"
        st.divider()
        st.markdown("**Global filters**")
        try:
            om = load("order_mart")
        except DataMissing as exc:
            st.error(str(exc))
            st.stop()
        dmin, dmax = date(2017, 1, 1), om.order_purchase_timestamp.max().date()
        rng = st.date_input("Purchase date", value=(dmin, date(2018, 8, 31)), min_value=om.order_purchase_timestamp.min().date(),
                            max_value=dmax, format="YYYY-MM-DD")
        start, end = (rng if isinstance(rng, tuple) and len(rng) == 2 else (dmin, dmax))
        regions = st.multiselect("Region", sorted(set(REGION_OF.values())))
        states_avail = sorted(s for s in om.customer_state.dropna().unique() if not regions or REGION_OF.get(s) in regions)
        states = st.multiselect("State (UF)", states_avail)
        cats = sorted(om.main_category.dropna().unique())
        categories = st.multiselect("Product category", cats, format_func=pretty)
        st.session_state["filters"] = {"start": start, "end": end, "regions": regions, "states": states,
                                       "categories": categories}
        st.caption("Currency: BRL · Source: Olist public dataset (2016-09 → 2018-10). "
                   "Order capture is incomplete after 2018-08-22.")


sidebar()
inject_css()
st.navigation(PAGES, position="sidebar").run()
