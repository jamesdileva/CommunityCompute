"""Coordinator configuration (Sprint 1; S4 timeout; S7 lease; S20 auth; S21 signing).

All values overridable via environment / `.env` (never commit `.env`).
Env names: COORDINATOR_HOST, COORDINATOR_PORT, DATABASE_URL, LOG_LEVEL,
HEARTBEAT_TIMEOUT_SECONDS, LEASE_DURATION_SECONDS, AUTH_ENABLED,
WORKLOAD_SIGNING_KEY.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from packages.protocol.signing import DEV_SIGNING_KEY


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
    # Sprint 31 (scheduling optimization): weighted score over compatible
    # candidates (architecture §10). `scoring_enabled=False` restores plain
    # FIFO (the A/B baseline). Weights are prototype defaults; the reference
    # values give the normalizers sensible midpoints.
    scoring_enabled: bool = True
    scoring_weight_capability: float = 1.0
    scoring_weight_speed: float = 1.0
    scoring_weight_cache: float = 2.0
    scoring_weight_reliability: float = 1.5
    scoring_weight_availability: float = 0.5
    scoring_weight_transfer: float = 1.5
    scoring_weight_location: float = 1.0
    scoring_reference_ms: float = 50.0
    scoring_reference_transfer_bytes: int = 50_000_000
    scoring_bytes_per_range_unit: int = 4
    scoring_model_default_mb: int = 256
    # Sprint 34 (economics research): ASSUMED cost inputs for the measured
    # cost-per-useful-compute model. Every one of these is an assumption, not a
    # measurement — the report keeps them in a separate `assumptions` block and
    # the only measured inputs are what the network already records (execution
    # time, uptime, overhead, unit volume). Override via env / .env.
    economics_electricity_usd_per_kwh: float = 0.17
    economics_bandwidth_usd_per_gb: float = 0.0
    economics_transfer_mb_per_unit: float = 1.0
    economics_infra_usd_per_month: float = 40.0
    economics_assumed_utilization: float = 0.30
    economics_cloud_gpu_usd_per_hour: float = 0.53
    economics_cloud_cpu_usd_per_hour: float = 0.032
    # JSON overrides ("" = built-in defaults in app.economics.model):
    # hardware class power/price/life, and the cited centralized baselines.
    economics_hardware_classes: str = ""
    economics_cloud_baselines: str = ""
    # Sprint 35 (public beta readiness): data-retention windows in days. These
    # are only *read* by readiness; enforcement is always explicit (dry-run by
    # default) via scripts/prune.py or POST /beta/prune -- never automatic.
    # telemetry = heartbeats + resource samples; work = terminal units/results/
    # attempts + used tokens; financial = contribution records + credit ledger
    # (0 = keep forever). See docs/data-retention.md.
    retention_telemetry_days: int = 7
    retention_work_days: int = 30
    retention_financial_days: int = 0


@lru_cache
def get_settings() -> Settings:
    return Settings()
