"""Central configuration.

All paths are derived from the project root, and every credential comes from
environment variables (optionally loaded from a local ``.env`` file). Nothing
machine-specific or secret is hardcoded here.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:  # python-dotenv is optional at runtime
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
except ImportError:  # pragma: no cover
    pass

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    return value if value not in (None, "") else default


@dataclass(frozen=True)
class Settings:
    """Runtime settings resolved from environment variables."""

    project_root: Path = PROJECT_ROOT
    raw_dir: Path = field(default_factory=lambda: Path(_env("NEXUS_RAW_DIR", str(PROJECT_ROOT / "data" / "raw"))))
    staging_dir: Path = PROJECT_ROOT / "data" / "staging"
    processed_dir: Path = PROJECT_ROOT / "data" / "processed"
    synthetic_dir: Path = PROJECT_ROOT / "data" / "synthetic"
    sample_dir: Path = PROJECT_ROOT / "data" / "sample"
    reports_dir: Path = PROJECT_ROOT / "reports"
    logs_dir: Path = PROJECT_ROOT / "logs"
    sql_dir: Path = PROJECT_ROOT / "sql"
    ml_artifacts_dir: Path = PROJECT_ROOT / "ml" / "artifacts"

    # Database (PostgreSQL). Credentials ONLY from the environment.
    db_host: str = field(default_factory=lambda: _env("NEXUS_DB_HOST", "localhost"))
    db_port: int = field(default_factory=lambda: int(_env("NEXUS_DB_PORT", "5432")))
    db_name: str = field(default_factory=lambda: _env("NEXUS_DB_NAME", "nexus_bi"))
    db_user: str = field(default_factory=lambda: _env("NEXUS_DB_USER", "nexus"))
    db_password: str | None = field(default_factory=lambda: _env("NEXUS_DB_PASSWORD"))

    # Services
    api_base_url: str = field(default_factory=lambda: _env("NEXUS_API_URL", "http://localhost:8000"))
    log_level: str = field(default_factory=lambda: _env("NEXUS_LOG_LEVEL", "INFO"))
    random_seed: int = field(default_factory=lambda: int(_env("NEXUS_RANDOM_SEED", "42")))
    load_batch_size: int = field(default_factory=lambda: int(_env("NEXUS_LOAD_BATCH_SIZE", "50000")))

    @property
    def database_url(self) -> str:
        """SQLAlchemy URL (psycopg 3 driver). Password is never logged."""
        pwd = f":{self.db_password}" if self.db_password else ""
        return f"postgresql+psycopg://{self.db_user}{pwd}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def safe_database_url(self) -> str:
        return f"postgresql+psycopg://{self.db_user}:***@{self.db_host}:{self.db_port}/{self.db_name}"

    def ensure_dirs(self) -> None:
        for p in (self.staging_dir, self.processed_dir, self.synthetic_dir, self.sample_dir,
                  self.reports_dir, self.logs_dir, self.ml_artifacts_dir):
            p.mkdir(parents=True, exist_ok=True)


settings = Settings()
