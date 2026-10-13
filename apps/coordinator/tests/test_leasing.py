"""Sprint 7: leases, expiry sweep, attempt records, late-result conflicts."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models.attempt import WorkUnitAttempt
from app.models.work_unit import WorkUnit

WORKER_A = "aaaaaaaa-0000-0000-0000-000000000001"
WORKER_B = "bbbbbbbb-0000-0000-0000-000000000002"

HB = {"worker_id": WORKER_A, "resources": {"cpu_percent": 10.0}}


def _register(client: TestClient, worker_id: str) -> None:
    assert client.post(
        "/workers/register",
        json={"worker_id": worker_id, "worker_version": "0.1.0-sprint7", "hostname": "PC-A"},
    ).status_code == 200


def _submit(client: TestClient, total: int = 1, chunk: int = 1) -> str:
    resp = client.post(
        "/jobs",
        json={"workload_type": "hello_compute", "params": {"op": "sum"},
              "total_units": total, "chunk_size": chunk},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _claim(client: TestClient, worker_id: str) -> dict:
    return client.post(f"/work/{worker_id}/claim").json()


def test_claim_creates_lease_with_attempt_1(client: TestClient):
    _submit(client)
    _register(client, WORKER_A)
    a = _claim(client, WORKER_A)
    assert a["lease_id"] and a["attempt_number"] == 1
    assert a["lease_expires_at"]


def test_active_lease_is_not_double_claimed(client: TestClient):
    _submit(client, total=1, chunk=1)
    _register(client, WORKER_A)
    _register(client, WORKER_B)
    a = _claim(client, WORKER_A)
    assert a["work_unit_id"]
    assert _claim(client, WORKER_B) == {}  # held by A until expiry


def test_expired_lease_requeues_with_attempt_2(client: TestClient):
    _submit(client, total=1, chunk=1)
    _register(client, WORKER_A)
    _register(client, WORKER_B)
    a = _claim(client, WORKER_A)

    # age the lease past expiry (simulates crashed worker A)
    db = next(iter(app.dependency_overrides[get_db]()))
    unit = db.get(WorkUnit, a["work_unit_id"])
    unit.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=5)
    db.commit()
    db.close()

    b = _claim(client, WORKER_B)  # sweep runs on claim
    assert b["work_unit_id"] == a["work_unit_id"]
    assert b["attempt_number"] == 2
    assert b["lease_id"] != a["lease_id"]

    db = next(iter(app.dependency_overrides[get_db]()))
    attempts = (
        db.query(WorkUnitAttempt).filter_by(work_unit_id=a["work_unit_id"])
        .order_by(WorkUnitAttempt.attempt_number).all()
    )
    assert [x.attempt_number for x in attempts] == [1, 2]
    assert attempts[0].outcome == "expired"
    assert attempts[0].worker_id == WORKER_A
    assert attempts[1].worker_id == WORKER_B
    db.close()


def test_late_result_after_requeue_conflicts(client: TestClient):
    """A completes nothing; B completes the unit; A's late submit -> 409."""
    _submit(client, total=1, chunk=1)
    _register(client, WORKER_A)
    _register(client, WORKER_B)
    a = _claim(client, WORKER_A)

    db = next(iter(app.dependency_overrides[get_db]()))
    unit = db.get(WorkUnit, a["work_unit_id"])
    unit.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=5)
    db.commit()
    db.close()

    b = _claim(client, WORKER_B)
    good = {"worker_id": WORKER_B, "status": "completed", "value": 1,
            "metrics": {"execution_ms": 1.0}}
    assert client.post(f"/work/{b['work_unit_id']}/result", json=good).status_code == 200

    # A's late (stale) result for the same unit conflicts
    late = {"worker_id": WORKER_A, "status": "completed", "value": 999}
    resp = client.post(f"/work/{a['work_unit_id']}/result", json=late)
    assert resp.status_code == 409


def test_identical_resubmit_after_completion_is_ok(client: TestClient):
    _submit(client, total=1, chunk=1)
    _register(client, WORKER_A)
    a = _claim(client, WORKER_A)
    good = {"worker_id": WORKER_A, "status": "completed", "value": 1,
            "metrics": {"execution_ms": 1.0}}
    assert client.post(f"/work/{a['work_unit_id']}/result", json=good).status_code == 200
    assert client.post(f"/work/{a['work_unit_id']}/result", json=good).status_code == 200


def test_attempt_closed_on_completion(client: TestClient):
    _submit(client, total=1, chunk=1)
    wid = str(uuid.uuid4())
    _register(client, wid)
    a = _claim(client, wid)
    client.post(f"/work/{a['work_unit_id']}/result",
                json={"worker_id": wid, "status": "completed", "value": 1})
    db = next(iter(app.dependency_overrides[get_db]()))
    attempts = db.query(WorkUnitAttempt).filter_by(work_unit_id=a["work_unit_id"]).all()
    assert len(attempts) == 1
    assert attempts[0].outcome == "completed"
    assert attempts[0].ended_at is not None
    db.close()


def test_bulk_expired_leases_sweep_in_one_pass(client: TestClient):
    """Sprint 18: a crashed worker holding many units — one sweep requeues all."""
    _submit(client, total=6, chunk=1)
    _register(client, WORKER_A)
    _register(client, WORKER_B)
    held = [_claim(client, WORKER_A) for _ in range(3)]
    assert all(u["work_unit_id"] for u in held)

    # age every held lease past expiry (simulates crashed worker A)
    db = next(iter(app.dependency_overrides[get_db]()))
    past = datetime.now(timezone.utc) - timedelta(seconds=5)
    for u in held:
        db.get(WorkUnit, u["work_unit_id"]).lease_expires_at = past
    db.commit()
    db.close()

    # B drains: swept units come back with attempt 2, fresh units with attempt 1
    seen: dict[str, int] = {}
    for _ in range(6):
        c = _claim(client, WORKER_B)
        assert c, "all 6 units must be claimable after the sweep"
        seen[c["work_unit_id"]] = c["attempt_number"]
        client.post(f"/work/{c['work_unit_id']}/result",
                    json={"worker_id": WORKER_B, "status": "completed",
                          "value": c["range_start"]})
    assert _claim(client, WORKER_B) == {}
    assert sum(1 for n in seen.values() if n == 2) == 3
    assert sum(1 for n in seen.values() if n == 1) == 3

    db = next(iter(app.dependency_overrides[get_db]()))
    expired = db.query(WorkUnitAttempt).filter_by(outcome="expired").all()
    assert len(expired) == 3
    assert {x.worker_id for x in expired} == {WORKER_A}
    db.close()
