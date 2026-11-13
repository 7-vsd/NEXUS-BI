"""Automatic discovery of source files in the raw data folder."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from src.config.settings import settings
from src.logging.logger import get_logger
from src.validation.schemas import SCHEMAS

log = get_logger("ingestion.discovery")


@dataclass(frozen=True)
class SourceFile:
    dataset: str
    path: Path
    size_bytes: int
    md5: str


def file_md5(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.md5()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def discover_sources(raw_dir: Path | None = None, with_checksum: bool = True) -> dict[str, SourceFile]:
    """Map each logical dataset to the CSV file found in ``raw_dir``.

    Matching is done with each schema's filename regex, so both
    ``olist_orders_dataset.csv`` and ``orders_dataset.csv`` are accepted.
    Raises ``FileNotFoundError`` if a required dataset is missing.
    """
    raw_dir = Path(raw_dir or settings.raw_dir)
    files = sorted(raw_dir.glob("*.csv"))
    found: dict[str, SourceFile] = {}
    for name, schema in SCHEMAS.items():
        # order_items/payments/reviews also match "orders?" loosely -> use strict anchored match on suffix
        rx = re.compile(r"(^|_)" + schema.pattern)
        matches = [f for f in files if rx.search(f.name)]
        if name == "orders":  # avoid matching order_items / order_payments / order_reviews
            matches = [f for f in matches if re.search(r"(^|_)orders?_dataset\.csv$", f.name)
                       and not re.search(r"order_(items|payments|reviews)", f.name)]
        if not matches:
            continue
        f = matches[0]
        found[name] = SourceFile(name, f, f.stat().st_size, file_md5(f) if with_checksum else "")
    missing = sorted(set(SCHEMAS) - set(found))
    if missing:
        raise FileNotFoundError(f"Missing source datasets in {raw_dir}: {missing}")
    log.info("Discovered %d source files in %s", len(found), raw_dir)
    return found
