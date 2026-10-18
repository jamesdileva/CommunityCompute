"""Measured inputs for the economics model (Sprint 34).

Pulls only what the prototype actually records — it does not invent data:

- **Work**: `ContributionRecord` rows give per-unit execution time, CPU/GPU
  time, and the hardware class of the machine that ran each unit.
- **Overhead**: `Result` rows vs. useful (credit-earning) units give the
  verification/duplication overhead factor; `Result.ok=False` gives failures.
- **Uptime/utilization**: heartbeats give availability and the observed
  window; utilization is busy-machine-time / online-machine-time.
- **Volume**: credit ledger gives useful units and the internal customer price
  proxy (1 credit per useful unit, Sprint 28).

Everything that cannot be measured is returned as `None` (unknown), never a
guessed zero — the report decides how to surface that.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.accounting import ContributionRecord
from app.models.capability import WorkerCapability
from app.models.credit import EARN_VERIFIED_UNIT, SPEND_JOB_SUBMIT, CreditEntry
from app.models.heartbeat import WorkerHeartbeat
from app.models.result import Result
from app.models.worker import Worker
from app.services import accounting
from app.services.availability import effective_status

MS_PER_HOUR = 3_600_000.0


def classify_worker(profile: dict | None) -> str:
    """Map a capability profile to a hardware class (matches simulation names)."""
    gpus = (profile or {}).get("gpus") or []
    if not gpus:
        return "cpu_only"
    gpu = max(gpus, key=lambda g: g.get("vram_mb") or 0)
    vendor = str(gpu.get("vendor") or "").lower()
    vram = gpu.get("vram_mb") or 0
    if vendor in ("intel", "unknown", "none", "") or vram < 1024:
        return "igpu"
    if vendor == "amd":
        return "amd_gpu"
    if vram >= 24_576:
        return "high_gpu"
    if vram >= 12_288:
        return "mid_gpu"
    return "consumer_gpu"


@dataclass
class Measurement:
    """Everything the model knows from data (None == not measurable yet)."""

    useful_units: int = 0
    contribution_records: int = 0
    results_total: int = 0
    failures: int = 0
    attempts_total: int = 0
    cpu_time_ms: float = 0.0
    gpu_time_ms: float = 0.0
    busy_ms: float = 0.0
    gpu_units: int = 0
    workers_total: int = 0
    workers_online: int = 0
    workers_by_class: dict[str, int] = field(default_factory=dict)
    busy_ms_by_class: dict[str, float] = field(default_factory=dict)
    per_workload: dict[str, dict] = field(default_factory=dict)
    credits_earned: int = 0
    credits_spent: int = 0
    mean_availability: float | None = None
    window_hours: float | None = None
    utilization: float | None = None

    @property
    def verification_overhead(self) -> float | None:
        """Executions per useful unit (>1 means duplicates re-ran work)."""
        if self.useful_units <= 0:
            return None
        return round(self.results_total / self.useful_units, 4)

    @property
    def failure_rate(self) -> float | None:
        if self.results_total <= 0:
            return None
        return round(self.failures / self.results_total, 4)

    @property
    def mean_unit_ms(self) -> float | None:
        if self.contribution_records <= 0:
            return None
        return round(self.busy_ms / self.contribution_records, 4)

    @property
    def mean_gpu_unit_ms(self) -> float | None:
        if self.gpu_units <= 0:
            return None
        return round(self.gpu_time_ms / self.gpu_units, 4)

    def to_dict(self) -> dict:
        return {
            "useful_units": self.useful_units,
            "contribution_records": self.contribution_records,
            "results_total": self.results_total,
            "failures": self.failures,
            "attempts_total": self.attempts_total,
            "cpu_time_ms": round(self.cpu_time_ms, 3),
            "gpu_time_ms": round(self.gpu_time_ms, 3),
            "busy_ms": round(self.busy_ms, 3),
            "gpu_units": self.gpu_units,
            "mean_unit_ms": self.mean_unit_ms,
            "mean_gpu_unit_ms": self.mean_gpu_unit_ms,
            "verification_overhead": self.verification_overhead,
            "failure_rate": self.failure_rate,
            "workers_total": self.workers_total,
            "workers_online": self.workers_online,
            "workers_by_class": dict(self.workers_by_class),
            "busy_ms_by_class": {k: round(v, 3) for k, v in self.busy_ms_by_class.items()},
            "per_workload": self.per_workload,
            "credits_earned": self.credits_earned,
            "credits_spent": self.credits_spent,
            "mean_availability": self.mean_availability,
            "window_hours": self.window_hours,
            "utilization": self.utilization,
        }


def measure(db: Session, settings=None) -> Measurement:
    settings = settings or get_settings()
    m = Measurement()

    classes = {cap.worker_id: classify_worker(cap.profile)
               for cap in db.query(WorkerCapability).all()}

    records = db.query(ContributionRecord).all()
    for r in records:
        m.contribution_records += 1
        exec_ms = r.execution_ms or 0.0
        m.busy_ms += exec_ms
        m.cpu_time_ms += r.cpu_time_ms or 0.0
        m.gpu_time_ms += r.gpu_time_ms or 0.0
        if (r.gpu_time_ms or 0.0) > 0:
            m.gpu_units += 1
        klass = classes.get(r.worker_id, "cpu_only")
        m.busy_ms_by_class[klass] = m.busy_ms_by_class.get(klass, 0.0) + exec_ms
        bucket = m.per_workload.setdefault(
            r.workload_type, {"units": 0, "cpu_ms": 0.0, "gpu_ms": 0.0, "busy_ms": 0.0})
        bucket["units"] += 1
        bucket["cpu_ms"] += r.cpu_time_ms or 0.0
        bucket["gpu_ms"] += r.gpu_time_ms or 0.0
        bucket["busy_ms"] += exec_ms

    for bucket in m.per_workload.values():
        for key in ("cpu_ms", "gpu_ms", "busy_ms"):
            bucket[key] = round(bucket[key], 3)
        bucket["mean_ms"] = round(bucket["busy_ms"] / bucket["units"], 4) if bucket["units"] else None

    m.results_total = db.query(func.count(Result.work_unit_id)).scalar() or 0
    m.failures = (db.query(func.count(Result.work_unit_id))
                  .filter(Result.ok.is_(False)).scalar() or 0)
    from app.models.attempt import WorkUnitAttempt
    m.attempts_total = db.query(func.count(WorkUnitAttempt.id)).scalar() or 0

    m.useful_units = (db.query(func.count(CreditEntry.id))
                      .filter(CreditEntry.reason == EARN_VERIFIED_UNIT).scalar() or 0)
    m.credits_earned = (db.query(func.coalesce(func.sum(CreditEntry.amount), 0))
                        .filter(CreditEntry.reason == EARN_VERIFIED_UNIT).scalar() or 0)
    m.credits_spent = (db.query(func.coalesce(func.sum(CreditEntry.amount), 0))
                       .filter(CreditEntry.reason == SPEND_JOB_SUBMIT).scalar() or 0)

    workers = db.query(Worker).all()
    m.workers_total = len(workers)
    timeout = settings.heartbeat_timeout_seconds
    m.workers_online = sum(1 for w in workers if effective_status(w, timeout) == "online")
    for w in workers:
        klass = classes.get(w.id, "cpu_only")
        m.workers_by_class[klass] = m.workers_by_class.get(klass, 0) + 1

    window = _heartbeat_window(db)
    m.window_hours = window
    # Availability is measured over the *observed window*, not the 24h default:
    # a short capture would otherwise report ~0 coverage and make utilization
    # meaningless. Utilization = busy machine-time / online machine-time.
    lookback = window or 24.0
    availabilities = []
    for w in workers:
        frac = accounting.availability_fraction(db, w.id, hours=lookback)
        if frac is not None:
            availabilities.append(frac)
    if availabilities:
        m.mean_availability = round(sum(availabilities) / len(availabilities), 4)

    if window and m.workers_online > 0 and m.mean_availability:
        online_hours = m.workers_online * window * m.mean_availability
        machine_ms = online_hours * MS_PER_HOUR
        if machine_ms > 0:
            m.utilization = round(min(m.busy_ms / machine_ms, 1.0), 4)
    return m


def _heartbeat_window(db: Session) -> float | None:
    first, last = db.query(
        func.min(WorkerHeartbeat.received_at), func.max(WorkerHeartbeat.received_at)
    ).one()
    if first is None or last is None:
        return None
    hours = (_aware(last) - _aware(first)).total_seconds() / 3600.0
    return round(hours, 4) if hours > 0 else None


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
