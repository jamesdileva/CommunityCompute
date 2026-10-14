"""Coordinator configuration (Sprint 1; S4 heartbeat timeout; S7 lease duration).

All values overridable via environment / `.env` (never commit `.env`).
Env names: COORDINATOR_HOST, COORDINATOR_PORT, DATABASE_URL, LOG_LEVEL,
HEARTBEAT_TIMEOUT_SECONDS, LEASE_DURATION_SECONDS.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    coordinator_host: str = "127.0.0.1"
    coordinator_port: int = 8000
    database_url: str = "sqlite:///./communitycompute.db"
    log_level: str = "info"
    heartbeat_timeout_seconds: int = 60
    lease_duration_seconds: int = 60
    # Sprint 20: worker authentication. False keeps the pre-Sprint-20 LAN dev
    # flow (anonymous callers allowed) while the authenticated path rolls out;
    # set true to lock every worker-facing route (401 without a valid bearer).
    auth_enabled: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
