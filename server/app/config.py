"""Runtime settings (P1-02).

One object, read once, injected everywhere. Architecture §8 keeps every environment-dependent value
here: no port, path or secret is hardcoded elsewhere. The DSN keeps the name `DB_DSN` so the existing
`init_db` script and this module read the same variable; everything else is prefixed `AV_`.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings, loaded from the environment and `.env` if present."""

    model_config = SettingsConfigDict(env_prefix="AV_", env_file=".env", extra="ignore")

    # Shared with scripts/init_db.py — do not rename without changing it too.
    db_dsn: str = Field(default="sqlite:///data/app.db", validation_alias="DB_DSN")

    # The secret is deliberately weak by default so a fresh clone runs; deployment must override it,
    # and the health endpoint reports whether it has.
    jwt_secret: str = Field(default="dev-only-insecure-secret", validation_alias="AV_JWT_SECRET")
    jwt_hours: int = Field(default=8, validation_alias="AV_JWT_HOURS")

    data_dir: str = Field(default="data", validation_alias="AV_DATA_DIR")
    # Intermediate frames older than this are cleanup candidates (FR-M2-05).
    retention_days: int = Field(default=30, validation_alias="AV_RETENTION_DAYS")
    max_concurrency: int = Field(default=2, validation_alias="AV_MAX_CONCURRENCY")
    detect_interval_ms: int = Field(default=300, validation_alias="AV_DETECT_INTERVAL_MS")
    quality_threshold: int = Field(default=60, validation_alias="AV_QUALITY_THRESHOLD")
    camera_index: int = Field(default=0, validation_alias="AV_CAMERA_INDEX")

    # The detection queue pool (architecture §5). Tests disable it so the suite stays deterministic.
    worker_enabled: bool = Field(default=True, validation_alias="AV_WORKER_ENABLED")
    worker_poll_seconds: float = Field(
        default=1.0, ge=0.05, validation_alias="AV_WORKER_POLL_SECONDS"
    )

    @property
    def jwt_secret_is_default(self) -> bool:
        """True when nobody has set a real secret — surfaced by /api/health, never silently."""
        return self.jwt_secret == "dev-only-insecure-secret"


@lru_cache
def get_settings() -> Settings:
    return Settings()
