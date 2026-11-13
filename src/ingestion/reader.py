"""CSV ingestion with schema validation and type conversion.

Raw files are never modified. Every column is first read as string to avoid
silent coercion (e.g. leading zeros in zip codes), then validated and cast to
its target dtype. Values that fail casting are counted and reported rather
than dropped silently.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from src.logging.logger import get_logger
from src.validation.schemas import SCHEMAS, DatasetSchema

log = get_logger("ingestion.reader")


class SchemaValidationError(ValueError):
    """Raised when a source file does not contain the expected columns."""


@dataclass
class IngestionResult:
    dataset: str
    frame: pd.DataFrame
    rows: int
    cast_failures: dict[str, int] = field(default_factory=dict)
    extra_columns: list[str] = field(default_factory=list)


def read_raw(path: Path) -> pd.DataFrame:
    """Read a CSV as all-string columns (BOM-safe)."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""], encoding="utf-8-sig")
    df.columns = [c.strip() for c in df.columns]
    return df


def validate_columns(df: pd.DataFrame, schema: DatasetSchema) -> list[str]:
    missing = [c for c in schema.columns if c not in df.columns]
    if missing:
        raise SchemaValidationError(f"{schema.name}: missing columns {missing}")
    return [c for c in df.columns if c not in schema.columns]


def cast_frame(df: pd.DataFrame, schema: DatasetSchema) -> tuple[pd.DataFrame, dict[str, int]]:
    """Cast string columns to target dtypes; return the frame and failure counts."""
    out = pd.DataFrame(index=df.index)
    failures: dict[str, int] = {}
    for col, dtype in schema.columns.items():
        s = df[col]
        if dtype == "string":
            out[col] = s.astype("string").str.strip()
        elif dtype in ("float", "int"):
            num = pd.to_numeric(s, errors="coerce")
            failures[col] = int((num.isna() & s.notna()).sum())
            if dtype == "int":
                out[col] = num.round().astype("Int64")
            else:
                out[col] = num.astype("float64")
        elif dtype == "datetime":
            dt = pd.to_datetime(s, errors="coerce", format="%Y-%m-%d %H:%M:%S")
            failures[col] = int((dt.isna() & s.notna()).sum())
            out[col] = dt
        else:  # pragma: no cover - guarded by schema definitions
            raise ValueError(f"Unknown dtype {dtype}")
    return out, {k: v for k, v in failures.items() if v}


def ingest(dataset: str, path: Path) -> IngestionResult:
    schema = SCHEMAS[dataset]
    raw = read_raw(path)
    extra = validate_columns(raw, schema)
    typed, failures = cast_frame(raw, schema)
    if failures:
        log.warning("%s: cast failures %s", dataset, failures)
    log.info("Ingested %s: %d rows x %d cols", dataset, len(typed), typed.shape[1])
    return IngestionResult(dataset, typed, len(typed), failures, extra)


def ingest_all(sources: dict) -> dict[str, IngestionResult]:
    return {name: ingest(name, src.path) for name, src in sources.items()}


def memory_mb(df: pd.DataFrame) -> float:
    return float(np.round(df.memory_usage(deep=True).sum() / 1e6, 2))
