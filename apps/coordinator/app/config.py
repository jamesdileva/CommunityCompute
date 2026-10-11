"""Coordinator configuration (Sprint 1).

All values overridable via environment / `.env` (never commit `.env`).
Env names: COORDINATOR_HOST, COORDINATOR_PORT, DATABASE_URL, LOG_LEVEL.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    coordinator_host: str = "127.0.0.1"
    coordinator_port: int = 8000
    database_url: str = "sqlite:///./communitycompute.db"
    log_level: str = "info"


@lru_cache
def get_settings() -> Settings:
    return Settings()
