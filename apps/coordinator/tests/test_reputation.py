"""Sprint 23: reliability scoring — bad output is detected and the score drops."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.services import reputation
from app.services.reputation import MIN_EVIDENCE

WORKER_A = "aaaaaaaa-0000-0000-0000-000000000001"
WORKER_B = "bbbbbbbb-0000-0000-0000-000000000002"


def _register(client: TestClient, wid: str) -> None:
    assert client.post(
        "/workers/register",
        json={"worker_id": wid, "worker_version": "t", "hostname": "PC-A"},
    ).status_code == 200


def _submit(client: TestClient, total: int = 1, chunk: int = 1) -> str:
    resp = client.post(
        "/jobs",
        json={"workload_type": "hello_compute", "params": {"op": "sum"},
              "total_units": total, "chunk_size": chunk},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _claim(client: TestClient, wid: str) -> dict:
    return client.post(f"/work/{wid}/claim").json()


def _complete(client: TestClient, unit_id: str, wid: str, value) -> int:
    return client.post(
        f"/work/{unit_id}/result",
        json={"worker_id": wid, "status": "completed", "value": value},
    ).status_code


def test_new_worker_is_unrated(client: TestClient):
    _register(client, WORKER_A)
    body = client.get(f"/workers/{WORKER_A}/reputation").json()
    assert body["score"] is None
    assert body["rated"] is False
    assert body["outcomes"] == 0


def test_reputation_unknown_worker_404(client: TestClient):
    assert client.get(f"/workers/{uuid.uuid4()}/reputation").status_code == 404


def test_accepted_results_build_score(client: TestClient):
    _register(client, WORKER_A)
    _submit(client, total=MIN_EVIDENCE, chunk=1)
    for _ in range(MIN_EVIDENCE):
        unit = _claim(client, WORKER_A)
        assert _complete(client, unit["work_unit_id"], WORKER_A,
                         unit["range_end"]) == 200
    body = client.get(f"/workers/{WORKER_A}/reputation").json()
    assert body["rated"] is True
    assert body["accepted"] == MIN_EVIDENCE
    assert body["score"] == round((MIN_EVIDENCE + 1) / (MIN_EVIDENCE + 2), 4)


def test_incorrect_output_drops_score(client: TestClient):
    """Exit condition: intentionally wrong output is detected, score falls."""
    _register(client, WORKER_A)
    _register(client, WORKER_B)
    n = MIN_EVIDENCE * 2  # both workers reach the evidence threshold
    _submit(client, total=n, chunk=1)
    for i in range(n):
        wid = WORKER_A if i % 2 == 0 else WORKER_B
        unit = _claim(client, wid)
        value = unit["range_end"] if wid == WORKER_A else -999  # B lies
        assert _complete(client, unit["work_unit_id"], wid, value) in (200, 422)
    a = client.get(f"/workers/{WORKER_A}/reputation").json()
    b = client.get(f"/workers/{WORKER_B}/reputation").json()
    assert a["score"] is not None and b["score"] is not None
    assert b["score"] < a["score"]  # the liar scores lower
    assert b["rejections_by_kind"] == {"value_mismatch": n // 2}
    assert a["accepted"] == n // 2


def test_expired_lease_marks_vanished_worker(client: TestClient):
    from datetime import datetime, timedelta, timezone

    from app.db import get_db
    from app.main import app
    from app.models.work_unit import WorkUnit

    _register(client, WORKER_A)
    _register(client, WORKER_B)
    _submit(client, total=1, chunk=1)
    unit = _claim(client, WORKER_A)
    # age the lease past expiry (A vanishes); B's next claim sweeps it
    db = next(iter(app.dependency_overrides[get_db]()))
    row = db.get(WorkUnit, unit["work_unit_id"])
    row.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=5)
    db.commit()
    db.close()
    assert _claim(client, WORKER_B)["work_unit_id"] == unit["work_unit_id"]
    rep = client.get(f"/workers/{WORKER_A}/reputation").json()
    assert rep["expired"] == 1


def test_duplicate_agreement_confirms_reliability(client: TestClient):
    _register(client, WORKER_A)
    _register(client, WORKER_B)
    job = client.post(
        "/jobs",
        json={"workload_type": "hello_compute", "params": {"op": "sum"},
              "total_units": 1, "chunk_size": 1, "verify_sample": 1.0},
    ).json()["id"]
    assert job
    first = _claim(client, WORKER_A)
    assert _complete(client, first["work_unit_id"], WORKER_A, 1) == 200
    dup = _claim(client, WORKER_B)
    assert dup["work_unit_id"] != first["work_unit_id"]
    assert _complete(client, dup["work_unit_id"], WORKER_B, 1) == 200
    rep_b = client.get(f"/workers/{WORKER_B}/reputation").json()
    assert rep_b["agreed"] == 1


def test_disagreement_marks_both_sides(client: TestClient):
    _register(client, WORKER_A)
    _register(client, WORKER_B)
    client.post(
        "/jobs",
        json={"workload_type": "hello_compute", "params": {"op": "sum"},
              "total_units": 1, "chunk_size": 1, "verify_sample": 1.0},
    )
    first = _claim(client, WORKER_A)
    assert _complete(client, first["work_unit_id"], WORKER_A, 1) == 200
    dup = _claim(client, WORKER_B)
    resp = client.post(
        f"/work/{dup['work_unit_id']}/result",
        json={"worker_id": WORKER_B, "status": "completed", "value": 31337},
    )
    assert resp.status_code == 422
    rep_b = client.get(f"/workers/{WORKER_B}/reputation").json()
    assert rep_b["disagreed"] == 1
    rep_a = client.get(f"/workers/{WORKER_A}/reputation").json()
    assert rep_a["accepted"] == 1  # A's original acceptance still stands


def test_reputation_record_rejects_unknown_events(client: TestClient):
    _register(client, WORKER_A)
    from app.db import get_db
    from app.main import app

    db = next(iter(client.app.dependency_overrides[get_db]()))
    try:
        with pytest.raises(ValueError):
            reputation.record(db, WORKER_A, "made_up_event")
    finally:
        db.close()
