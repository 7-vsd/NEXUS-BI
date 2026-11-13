"""Reusable, vectorised cleaning helpers shared by every dataset transform."""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class CleaningLog:
    """Collects every cleaning action so it is auditable in the DQ report."""

    entries: list[dict] = field(default_factory=list)

    def add(self, dataset: str, action: str, rows_affected: int, detail: str = "") -> None:
        self.entries.append({"dataset": dataset, "action": action,
                             "rows_affected": int(rows_affected), "detail": detail})

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.entries, columns=["dataset", "action", "rows_affected", "detail"])


def strip_accents(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))


def normalize_city(s: pd.Series) -> pd.Series:
    """Lower-case, accent-free, single-spaced city names (e.g. 'São Paulo ' -> 'sao paulo')."""
    uniq = s.dropna().unique()
    mapping = {u: " ".join(strip_accents(str(u)).lower().replace("'", " ").split()) for u in uniq}
    return s.map(mapping).astype("string")


def normalize_state(s: pd.Series) -> pd.Series:
    return s.str.strip().str.upper().astype("string")


def normalize_zip(s: pd.Series) -> pd.Series:
    """Zip-code prefixes are 5-digit strings; restore leading zeros if lost."""
    return s.astype("string").str.strip().str.zfill(5)


def normalize_category(s: pd.Series) -> pd.Series:
    return s.astype("string").str.strip().str.lower().str.replace(r"\s+", "_", regex=True)


def drop_exact_duplicates(df: pd.DataFrame, dataset: str, log: CleaningLog,
                          subset: list[str] | None = None) -> pd.DataFrame:
    before = len(df)
    df = df.drop_duplicates(subset=subset)
    removed = before - len(df)
    if removed:
        log.add(dataset, "drop_duplicates", removed, f"subset={subset or 'all columns'}")
    return df


def date_key(ts: pd.Series) -> pd.Series:
    """YYYYMMDD integer surrogate key for dim_date (nullable)."""
    return pd.to_numeric(ts.dt.strftime("%Y%m%d"), errors="coerce").astype("Int64")
