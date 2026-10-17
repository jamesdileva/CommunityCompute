"""Small real-database validation for the simulation (Sprint 32).

The million-node runs stay in memory, but the prototype's persistence/queue
layer must still be *measurable* — so this drives the real service path
(Worker/WorkerCapability rows, ``create_job``, ``claim_next_unit``,
``submit_result``) against a modest, safe number of simulated workers. It
answers "does the DB/queue architecture hold up as node count grows?" without
putting tens of thousands of rows on a laptop.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.capability import WorkerCapability
from app.models.worker import Worker
from app.schemas.job import JobCreate
from app.schemas.work import WorkResult
from app.services import jobs as job_service
from app.services import work as work_service
from app.simulation.workers import make_workers
from packages.protocol import PROTOCOL_VERSION


def register_simulated_workers(db: Session, count: int, *, seed: int = 32,
                               version: str = "0.1.0-sprint32") -> list:
    """Insert ``count`` simulated workers (+capability rows). Returns the fleet."""
    now = datetime.now(timezone.utc)
    fleet = []
    for worker in make_workers(count, seed=seed):
        db.add(Worker(id=worker.id, worker_version=version, hostname=f"sim-{worker.klass}",
                      status="online", last_seen=now))
        db.add(WorkerCapability(worker_id=worker.id, profile=worker.profile()))
        fleet.append(worker)
    db.commit()
    return fleet


def _sum(start: int, end: int) -> int:
    return (start + end) * (end - start + 1) // 2


def run_db_backed(db: Session, *, workers: int = 150, units: int | None = None,
                  seed: int = 32) -> dict:
    """Register workers, submit one job, drain it through real claims. Returns stats."""
    units = workers if units is None else units
    started = time.perf_counter()

    fleet = register_simulated_workers(db, workers, seed=seed)
    job, _created_units = job_service.create_job(
        db, JobCreate(workload_type="hello_compute", params={"op": "sum"},
                      total_units=units, chunk_size=1)
    )

    claimed = 0
    completed = 0
    used: set[str] = set()
    # one claim per worker is enough to drain a fleet-sized job; loop for the
    # (units > workers) case so the harness is honest for any ratio.
    for _round in range((units // workers) + 2):
        idle = 0
        for worker in fleet:
            assignment = work_service.claim_next_unit(
                db, worker.id, cached_models=set(worker.cached)
            )
            if assignment is None:
                idle += 1
                continue
            claimed += 1
            used.add(worker.id)
            ok, _reason, _result = work_service.submit_result(
                db, assignment.work_unit_id,
                WorkResult(
                    protocol_version=PROTOCOL_VERSION, worker_id=worker.id,
                    status="completed",
                    value=_sum(assignment.range_start, assignment.range_end),
                    metrics={"execution_ms": 1.0},
                ),
            )
            if ok:
                completed += 1
        if idle == len(fleet):
            break  # nothing left to claim

    elapsed_ms = (time.perf_counter() - started) * 1000.0
    status = job_service.job_status(db, job.id)
    aggregate = work_service.aggregate_job(db, job.id)
    return {
        "workers": workers,
        "units": units,
        "workers_used": len(used),
        "claimed": claimed,
        "completed": completed,
        "job_status": status.job.status if status else None,
        "aggregate_final": (aggregate or {}).get("final"),
        "expected_final": _sum(1, units),
        "rows_written": workers * 2 + units,  # 2 rows/worker + 1 unit/row
        "elapsed_ms": elapsed_ms,
        "rows_per_second": round((workers * 2 + units) / max(elapsed_ms / 1000, 1e-9), 1),
    }
