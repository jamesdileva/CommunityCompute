"""Sprint 35: public-beta readiness - retention enforcement + the go/no-go checklist.

Covers the retention pruner (dry run, stale-only deletion, live-lease safety,
ledger kept by default) and the readiness endpoint (checklist shape, route- and
doc-derived statuses, and the NO-GO/GO decision).
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from app.config import get_settings
from app.db import Base
from app.models.accounting import ContributionRecord
from app.models.attempt import WorkUnitAttempt
from app.models.auth import EnrollmentToken, WorkerCredential
from app.models.credit import CreditEntry
from app.models.heartbeat import WorkerHeartbeat
from app.models.job import Job
from app.models.result import Result
from app.models.sample import ResourceSample
from app.models.work_unit import (
    COMPLETED,
    DISPATCHED,
    QUEUED,
    WorkUnit,
)
from app.models.worker import Worker
from app.services import retention
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture()
def db(tmp_path) -> Session:
    engine = create_engine(
        f"sqlite:///{tmp_path}/retention.db", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


def _old(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def _worker(db: Session) -> str:
    wid = str(uuid.uuid4())
    db.add(Worker(id=wid, worker_version="t", hostname="t", status="online"))
    db.commit()
    return wid


def _job(db: Session) -> str:
    jid = str(uuid.uuid4())
    db.add(Job(id=jid, workload_type="hello_compute", params={}, total_units=1, chunk_size=1))
    db.commit()
    return jid


def _unit(db: Session, jid: str, status: str, age_days: int,
          worker_id: str | None = None) -> str:
    uid = str(uuid.uuid4())
    ts = _old(age_days)
    db.add(WorkUnit(id=uid, job_id=jid, sequence=1, range_start=1, range_end=1,
                    status=status, assigned_worker_id=worker_id,
                    lease_worker_id=worker_id, created_at=ts, updated_at=ts))
    db.commit()
    return uid


def _result(db: Session, uid: str, wid: str, age_days: int = 0) -> None:
    db.add(Result(work_unit_id=uid, worker_id=wid, ok=True, value=1, created_at=_old(age_days)))
    db.commit()


def _attempt(db: Session, uid: str, wid: str) -> None:
    db.add(WorkUnitAttempt(work_unit_id=uid, attempt_number=1, worker_id=wid,
                           outcome="completed"))
    db.commit()


# ---- retention ---------------------------------------------------------------

def test_dry_run_counts_without_deleting(db: Session):
    wid, jid = _worker(db), _job(db)
    db.add(WorkerHeartbeat(worker_id=wid, received_at=_old(40)))
    db.add(ResourceSample(worker_id=wid, sampled_at=_old(40)))
    uid = _unit(db, jid, COMPLETED, age_days=40, worker_id=wid)
    _result(db, uid, wid, age_days=40)
    db.commit()

    report = retention.prune(db, telemetry_days=7, work_days=30, apply=False)

    assert report["applied"] is False
    assert report["deleted"]["worker_heartbeats"] == 1
    assert report["deleted"]["worker_resource_samples"] == 1
    assert report["deleted"]["work_units"] == 1
    # Nothing was removed on a dry run.
    assert db.query(WorkerHeartbeat).count() == 1
    assert db.get(WorkUnit, uid) is not None


def test_apply_deletes_only_stale_terminal_units(db: Session):
    wid, jid = _worker(db), _job(db)
    stale = _unit(db, jid, COMPLETED, age_days=60, worker_id=wid)
    _result(db, stale, wid, age_days=60)
    _attempt(db, stale, wid)
    fresh = _unit(db, jid, COMPLETED, age_days=1, worker_id=wid)
    _result(db, fresh, wid, age_days=1)
    queued = _unit(db, jid, QUEUED, age_days=60)
    running = _unit(db, jid, DISPATCHED, age_days=60, worker_id=wid)

    report = retention.prune(db, telemetry_days=7, work_days=30, apply=True)

    assert report["deleted"]["work_units"] == 1
    assert db.get(WorkUnit, stale) is None
    assert db.query(Result).filter_by(work_unit_id=stale).count() == 0
    assert db.query(WorkUnitAttempt).filter_by(work_unit_id=stale).count() == 0
    # Fresh terminal, queued, and lease-held units survive.
    assert db.get(WorkUnit, fresh) is not None
    assert db.query(Result).filter_by(work_unit_id=fresh).count() == 1
    assert db.get(WorkUnit, queued) is not None
    assert db.get(WorkUnit, running) is not None


def test_financial_records_kept_by_default(db: Session):
    wid, jid = _worker(db), _job(db)
    uid = _unit(db, jid, COMPLETED, age_days=400, worker_id=wid)
    db.add(ContributionRecord(work_unit_id=uid, job_id=jid, worker_id=wid,
                              workload_type="hello_compute", execution_ms=1.0,
                              created_at=_old(400)))
    db.add(CreditEntry(worker_id=wid, amount=1, reason="earn_verified_unit",
                       work_unit_id=uid, created_at=_old(400)))
    db.commit()

    keep = retention.prune(db, telemetry_days=7, work_days=30, financial_days=0, apply=True)
    assert keep["deleted"]["contribution_records"] == 0
    assert keep["deleted"]["credit_ledger"] == 0
    assert db.query(ContributionRecord).count() == 1
    assert db.query(CreditEntry).count() == 1

    purge = retention.prune(db, telemetry_days=7, work_days=30, financial_days=90, apply=True)
    assert purge["deleted"]["contribution_records"] == 1
    assert purge["deleted"]["credit_ledger"] == 1
    assert db.query(ContributionRecord).count() == 0
    assert db.query(CreditEntry).count() == 0


def test_used_enrollment_tokens_pruned_active_kept(db: Session):
    used = EnrollmentToken(id=str(uuid.uuid4()), token_hash="a" * 64,
                           used_at=_old(60), created_at=_old(60))
    active = EnrollmentToken(id=str(uuid.uuid4()), token_hash="b" * 64,
                             created_at=_old(60))
    db.add_all([used, active])
    db.commit()
    used_id, active_id = used.id, active.id

    report = retention.prune(db, telemetry_days=7, work_days=30, apply=True)
    assert report["deleted"]["enrollment_tokens"] == 1
    assert db.get(EnrollmentToken, used_id) is None
    assert db.get(EnrollmentToken, active_id) is not None


def test_identity_and_credentials_retained(db: Session):
    wid = _worker(db)
    db.add(WorkerCredential(id=str(uuid.uuid4()), worker_id=wid, token_hash="c" * 64))
    db.commit()

    retention.prune(db, telemetry_days=1, work_days=1, financial_days=1, apply=True)
    assert db.get(Worker, wid) is not None
    assert db.query(WorkerCredential).filter_by(worker_id=wid).count() == 1


# ---- readiness ---------------------------------------------------------------

def test_readiness_checklist_and_decision(client):
    resp = client.get("/beta/readiness")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    items = {c["item"]: c for c in body["checklist"]}
    assert set(items) == {
        "security_review", "sandboxing_review", "privacy_review", "abuse_controls",
        "worker_auto_update", "credential_revocation", "monitoring",
        "incident_handling", "terms_privacy", "data_retention", "customer_isolation",
    }
    valid = {"present", "documented", "partial", "gap"}
    assert all(c["status"] in valid for c in body["checklist"])
    assert all(c["evidence"] for c in body["checklist"])

    # Statuses derived from live routes/state, not hardcoded prose.
    assert items["credential_revocation"]["status"] == "present"
    assert items["monitoring"]["status"] == "present"
    assert items["customer_isolation"]["status"] == "present"
    assert items["data_retention"]["status"] == "present"

    assert body["retention"] == {"telemetry_days": 7, "work_days": 30, "financial_days": 0}
    assert body["decision"]["public_enrollment"] == "no-go"
    assert body["decision"]["invited_beta"] == "go"
    assert body["decision"]["public_blockers"]


def test_prune_endpoint_dry_run_by_default(client):
    resp = client.post("/beta/prune")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["applied"] is False
    assert body["windows"] == {"telemetry_days": 7, "work_days": 30, "financial_days": 0}

    applied = client.post("/beta/prune", params={"apply": "true", "work_days": 1}).json()
    assert applied["applied"] is True
    assert applied["windows"]["work_days"] == 1


def test_readiness_builder_reports_missing_docs_as_gap():
    from app.services.readiness import build_readiness

    report = build_readiness(
        version="0.1.0-test",
        settings=get_settings(),
        route_paths=set(),  # no routes -> route-derived checks fail
    )
    items = {c["item"]: c["status"] for c in report["checklist"]}
    assert items["credential_revocation"] == "gap"
    assert items["customer_isolation"] == "gap"
    assert report["decision"]["invited_beta"] == "no-go"
