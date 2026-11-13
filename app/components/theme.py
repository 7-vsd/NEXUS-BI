"""NEXUS BI visual identity: palette, CSS injection, Plotly templates (dark navy + light)."""
from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

PALETTE = {
    "navy": "#0B1F3A", "navy_2": "#13294B", "navy_3": "#1C3A63", "blue": "#3B6EA8", "muted_blue": "#7FA7D1",
    "teal": "#14B8A6", "teal_dark": "#0F8F82", "green": "#16A34A", "red": "#DC2626", "amber": "#D97706",
    "grey": "#94A3B8", "grey_dark": "#64748B", "white": "#FFFFFF",
}
SERIES = ["#14B8A6", "#3B6EA8", "#7FA7D1", "#F59E0B", "#8B5CF6", "#EC4899", "#64748B", "#22C55E", "#EF4444", "#0EA5E9"]

THEMES = {
    "dark": {"bg": "#0B1F3A", "panel": "#13294B", "panel_2": "#1C3A63", "text": "#E6EDF5", "muted": "#9FB3C8",
             "border": "#24456F", "grid": "#24456F"},
    "light": {"bg": "#F4F6FA", "panel": "#FFFFFF", "panel_2": "#EEF2F7", "text": "#13294B", "muted": "#5B6B7F",
              "border": "#DCE3EC", "grid": "#E3E8EF"},
}


def current_mode() -> str:
    return st.session_state.get("theme_mode", "dark")


def colors() -> dict:
    return THEMES[current_mode()]


def register_plotly_templates() -> None:
    import plotly.express as px

    px.defaults.color_discrete_sequence = SERIES   # brand palette for all Plotly Express charts
    for mode, c in THEMES.items():
        t = go.layout.Template()
        t.layout = go.Layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, Segoe UI, Roboto, sans-serif", color=c["text"], size=12),
            colorway=SERIES, title=dict(font=dict(size=15, color=c["text"]), x=0.01, xanchor="left"),
            xaxis=dict(gridcolor=c["grid"], zerolinecolor=c["grid"], linecolor=c["border"]),
            yaxis=dict(gridcolor=c["grid"], zerolinecolor=c["grid"], linecolor=c["border"]),
            legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h", yanchor="bottom", y=1.02, x=0),
            margin=dict(l=10, r=10, t=50, b=10), hoverlabel=dict(font_size=12),
        )
        pio.templates[f"nexus_{mode}"] = t


def plotly_template() -> str:
    return f"nexus_{current_mode()}"


def inject_css() -> None:
    c = colors()
    st.markdown(f"""
<style>
  .stApp {{ background: {c['bg']}; color: {c['text']}; }}
  [data-testid="stSidebar"] {{ background: {c['panel']}; border-right: 1px solid {c['border']}; }}
  [data-testid="stSidebar"] * {{ color: {c['text']}; }}
  [data-testid="stHeader"] {{ background: transparent; }}
  h1, h2, h3, h4, p, label, span, div {{ color: {c['text']}; }}
  .block-container {{ padding-top: 1.6rem; max-width: 1400px; }}
  .nx-header {{ display:flex; align-items:baseline; gap:14px; margin-bottom: 4px; }}
  .nx-header h1 {{ font-size: 1.65rem; margin: 0; font-weight: 650; letter-spacing: -0.01em; }}
  .nx-sub {{ color: {c['muted']}; font-size: 0.92rem; margin-bottom: 1.1rem; }}
  .nx-card {{ background: {c['panel']}; border: 1px solid {c['border']}; border-radius: 10px;
             padding: 14px 16px 12px; height: 100%; }}
  .nx-card .lbl {{ font-size: 0.72rem; text-transform: uppercase; letter-spacing: .06em; color: {c['muted']}; }}
  .nx-card .val {{ font-size: 1.55rem; font-weight: 650; margin-top: 2px; color: {c['text']}; }}
  .nx-card .delta-pos {{ color: {PALETTE['green']}; font-size: .82rem; font-weight: 600; }}
  .nx-card .delta-neg {{ color: {PALETTE['red']}; font-size: .82rem; font-weight: 600; }}
  .nx-card .delta-neu {{ color: {c['muted']}; font-size: .82rem; }}
  .nx-card.accent {{ border-left: 3px solid {PALETTE['teal']}; }}
  .nx-section {{ font-size: 1.02rem; font-weight: 600; margin: 1.3rem 0 .4rem; padding-bottom: 4px;
                 border-bottom: 1px solid {c['border']}; }}
  .nx-note {{ background: {c['panel_2']}; border-left: 3px solid {PALETTE['amber']}; padding: 8px 12px;
              border-radius: 6px; font-size: .85rem; color: {c['text']}; margin: 6px 0 10px; }}
  .nx-insight {{ background: {c['panel_2']}; border-left: 3px solid {PALETTE['teal']}; padding: 8px 12px;
                 border-radius: 6px; font-size: .86rem; margin: 4px 0 12px; }}
  .nx-badge {{ display:inline-block; padding: 2px 8px; border-radius: 999px; font-size: .72rem; font-weight: 600; }}
  .nx-badge.ok {{ background: rgba(22,163,74,.18); color: {PALETTE['green']}; }}
  .nx-badge.warn {{ background: rgba(217,119,6,.18); color: {PALETTE['amber']}; }}
  .nx-badge.bad {{ background: rgba(220,38,38,.18); color: {PALETTE['red']}; }}
  [data-testid="stDataFrame"] {{ border: 1px solid {c['border']}; border-radius: 8px; }}
  .stTabs [data-baseweb="tab"] {{ color: {c['muted']}; }}
  .stTabs [aria-selected="true"] {{ color: {PALETTE['teal']} !important; }}
</style>""", unsafe_allow_html=True)
