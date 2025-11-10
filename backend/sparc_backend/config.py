"""Application configuration and settings management."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the Sparc backend."""

    model_config = SettingsConfigDict(
        env_prefix="SPARC_", env_file=".env", extra="ignore"
    )

    database_url: str = "postgresql+psycopg://sparc:sparc@localhost:5432/sparc"
    redis_url: str = "redis://localhost:6379/0"
    projects_root: Path = Path("./projects").resolve()
    repo_root: Path = Path(__file__).resolve().parents[2]
    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached instance of :class:`Settings`."""

    settings = Settings()
    settings.projects_root.mkdir(parents=True, exist_ok=True)
    return settings


__all__ = ["Settings", "get_settings"]
