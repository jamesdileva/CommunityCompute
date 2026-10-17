"""Coordinator configuration (Sprint 1; S4 timeout; S7 lease; S20 auth; S21 signing).

All values overridable via environment / `.env` (never commit `.env`).
Env names: COORDINATOR_HOST, COORDINATOR_PORT, DATABASE_URL, LOG_LEVEL,
HEARTBEAT_TIMEOUT_SECONDS, LEASE_DURATION_SECONDS, AUTH_ENABLED,
WORKLOAD_SIGNING_KEY.
"""

from functools import lru_cache

from packages.protocol.signing import DEV_SIGNING_KEY
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
    # Sprint 26 (beta guardrails): minimum worker version to claim work
    # (empty = no gate); max simultaneous leases per worker (anti-hoarding).
    min_worker_version: str = ""
    max_leases_per_worker: int = 8
    # Sprint 21: HMAC key sealing work assignments. The dev default matches the
    # worker default so LAN prototypes work; ANY production use needs a real
    # secret here (startup warns loudly when the default is in effect).
    workload_signing_key: str = DEV_SIGNING_KEY
    # Sprint 30 (per-customer quotas, enforced at POST /api/v1/jobs):
    # max units one job may request, max concurrent in-flight jobs, and max
    # units in flight across all of a customer's jobs.
    customer_max_units_per_job: int = 1000
    customer_max_in_flight_jobs: int = 5
    customer_max_units_in_flight: int = 2000


@lru_cache
def get_settings() -> Settings:
    return Settings()
