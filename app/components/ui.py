"""Reusable UI building blocks."""
from __future__ import annotations

import html

import plotly.graph_objects as go
import streamlit as st

from app.components.theme import plotly_template


def page_header(title: str, subtitle: str) -> None:
    st.markdown(f'<div class="nx-header"><h1>{html.escape(title)}</h1></div>'
                f'<div class="nx-sub">{html.escape(subtitle)}</div>', unsafe_allow_html=True)


def section(title: str) -> None:
    st.markdown(f'<div class="nx-section">{html.escape(title)}</div>', unsafe_allow_html=True)


def note(text: str) -> None:
    st.markdown(f'<div class="nx-note">{text}</div>', unsafe_allow_html=True)


def insight(text: str) -> None:
    st.markdown(f'<div class="nx-insight">{text}</div>', unsafe_allow_html=True)


def kpi_card(label: str, value: str, delta: float | None = None, delta_label: str = "",
             invert: bool = False, accent: bool = False) -> None:
    """KPI card. ``invert`` = True when a decrease is good (e.g. late rate)."""
    if delta is None:
        d = f'<span class="delta-neu">{html.escape(delta_label)}</span>' if delta_label else "&nbsp;"
    else:
        good = (delta < 0) if invert else (delta >= 0)
        cls = "delta-pos" if good else "delta-neg"
        arrow = "▲" if delta >= 0 else "▼"
        d = f'<span class="{cls}">{arrow} {abs(delta):.1f}%</span> <span class="delta-neu">{html.escape(delta_label)}</span>'
    st.markdown(f'<div class="nx-card{" accent" if accent else ""}"><div class="lbl">{html.escape(label)}</div>'
                f'<div class="val">{html.escape(value)}</div><div>{d}</div></div>', unsafe_allow_html=True)


def kpi_row(cards: list[dict]) -> None:
    cols = st.columns(len(cards))
    for col, c in zip(cols, cards):
        with col:
            kpi_card(**c)


def chart(fig: go.Figure, height: int = 360, key: str | None = None) -> None:
    fig.update_layout(template=plotly_template(), height=height)
    st.plotly_chart(fig, width="stretch", key=key, config={"displaylogo": False})


def empty_state(message: str = "No data for the selected filters.") -> None:
    st.info(f"ℹ️ {message} Try widening the date range or clearing filters.")


def brl(x: float, decimals: int = 0) -> str:
    if x is None:
        return "–"
    if abs(x) >= 1e6:
        return f"R$ {x / 1e6:,.2f}M"
    if abs(x) >= 1e3 and decimals == 0:
        return f"R$ {x / 1e3:,.1f}K"
    return f"R$ {x:,.{decimals}f}"


def pct(x: float | None, decimals: int = 1) -> str:
    return "–" if x is None else f"{100 * x:.{decimals}f}%"


def num(x: float | None) -> str:
    return "–" if x is None else f"{x:,.0f}"
