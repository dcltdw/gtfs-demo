"""Runtime settings loaded from the environment.

Defaults match the values committed to ``.env.example``. A ``.env`` file in the
working directory overrides them.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, populated from the environment or ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    gtfs_static_feed_url: str = Field(default="https://cdn.mbta.com/MBTA_GTFS.zip")
    gtfs_cache_dir: Path = Field(default_factory=lambda: Path.home() / ".cache" / "gtfs-dleung")
    gtfs_static_ttl_days: int = Field(default=7, ge=1)
    gtfs_user_agent: str = Field(
        default="gtfs-dleung/0.0.1 (https://github.com/dcltdw/gtfs-dleung)"
    )


def get_settings() -> Settings:
    """Return a freshly-loaded settings instance.

    Not memoised on purpose: tests construct ``Settings`` directly with overrides
    to avoid leaking environment state across cases.
    """
    return Settings()
