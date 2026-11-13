"""Thin, fault-tolerant client for the NEXUS BI FastAPI service."""
from __future__ import annotations

import os
from typing import Any

import httpx
import streamlit as st

API_URL = os.getenv("NEXUS_API_URL", "http://localhost:8000").rstrip("/")
TIMEOUT = float(os.getenv("NEXUS_API_TIMEOUT", "15"))


class ApiError(RuntimeError):
    pass


def _request(method: str, path: str, **kw) -> Any:
    try:
        r = httpx.request(method, f"{API_URL}{path}", timeout=TIMEOUT, **kw)
    except httpx.HTTPError as exc:
        raise ApiError(f"API unreachable at {API_URL} ({exc.__class__.__name__}). "
                       "Start it with `uvicorn api.main:app --port 8000`.") from exc
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail")
        except ValueError:
            detail = r.text
        raise ApiError(f"API {r.status_code}: {detail}")
    return r.json()


def get(path: str, params: dict | None = None) -> Any:
    return _request("GET", path, params={k: v for k, v in (params or {}).items() if v not in (None, "")})


def post(path: str, payload: dict) -> Any:
    return _request("POST", path, json=payload)


@st.cache_data(ttl=60, show_spinner=False)
def cached_get(path: str, params: tuple = ()) -> Any:
    return get(path, dict(params))


@st.cache_data(ttl=300, show_spinner=False)
def cached_post(path: str, payload_items: tuple) -> Any:
    return post(path, dict(payload_items))


def health() -> tuple[bool, dict | str]:
    try:
        return True, get("/health", {"check_db": "true"})
    except ApiError as exc:
        return False, str(exc)
