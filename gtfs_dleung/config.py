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
        default="gtfs-dleung/0.1.0 (David Leung; claude.unraveled663@simplelogin.com)"
    )
    gtfs_rt_fetch_interval_seconds: int = Field(default=10, ge=1)
    gtfs_stale_threshold_s: int = Field(default=30, ge=1)
    """Seconds: data older than this is considered stale. MBTA publishes ~5s; 30s is a real problem."""

    gtfs_demo_username: str = Field(default="demo")
    """Single seeded username for the demo Streamlit app. See ``docs/SECURITY.md``."""

    gtfs_demo_password_bcrypt: str = Field(
        default="$2b$12$nGiMs9lnemij6sGDk6MNCOGm0ycfLJpBY8keXWIIIuYdc7Fle.xZ6"
    )
    """Bcrypt hash of the demo password (default is the public placeholder; production .env overrides)."""

    gtfs_cookie_key: str = Field(default="gtfs-dleung-demo-cookie-key-rotate-me")
    """HMAC key for streamlit-authenticator's session cookie. Rotate alongside the password."""

    gtfs_cookie_expiry_days: int = Field(default=1, ge=0)

    gtfs_inbound_limit_per_min: int = Field(default=30, ge=1)
    """Inbound rate-limit budget per Streamlit session per window."""

    gtfs_inbound_window_s: float = Field(default=60.0, gt=0)
    """Sliding window size in seconds for the inbound rate limiter."""

    gtfs_inbound_idle_evict_s: float = Field(default=3600.0, gt=0)
    """Drop a session's bucket after this much idle time (bounds limiter memory)."""


def get_settings() -> Settings:
    """Return a freshly-loaded settings instance.

    Not memoised on purpose: tests construct ``Settings`` directly with overrides
    to avoid leaking environment state across cases.
    """
    return Settings()
