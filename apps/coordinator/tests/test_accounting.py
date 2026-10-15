"""Sprint 27: auditable contribution records — every completed unit accounted."""

import uuid

from fastapi.testclient import TestClient

from app.services.accounting import (
    availability_fraction,
    estimate_times,
    record_completion,
    void_record,
    worker_summary,
)

WORKER_A = "aaaaaaaa-0000-0000-0000-000000000001"
WORKER_B = "bbbbbbbb-0000-0000-0000-000000000002"


def _register(client: TestClient, wid: str) -> None:
    assert client.post(
        "/workers/register",
        json={"worker_id": wid, "worker_version": "t", "hostname": "PC-A"},
    ).status_code == 200


def _submit(client: TestClient, requirements: dict | None = None,
            total: int = 2, chunk: int = 1) -> str:
    body = {"workload_type": "hello_compute", "params": {"op": "sum"},
            "total_units": total, "chunk_size": chunk}
    if requirements is not None:
        body["requirements"] = requirements
    resp = client.post("/jobs", json=body)
    assert resp.status_code == 201
    return resp.json()["id"]


def _claim(client: TestClient, wid: str) -> dict:
    return client.post(f"/work/{wid}/claim", json={}).json()


def _complete(client: TestClient, unit: dict, wid: str, value=None) -> int:
    value = unit["range_end"] if value is None else value
    return client.post(
        f"/work/{unit['work_unit_id']}/result",
        json={"worker_id": wid, "status": "completed", "value": value,
              "metrics": {"execution_ms": 4.0}},
    ).status_code


def test_estimate_times_model():
    assert estimate_times(100.0, requires_gpu=False) == (100.0, 0.0)
    assert estimate_times(100.0, requires_gpu=True) == (100.0, 100.0)
    assert estimate_times(None, requires_gpu=True) == (None, None)


def test_completed_unit_produces_record(client: TestClient):
    _register(client, WORKER_A)
    _submit(client)
    unit = _claim(client, WORKER_A)
    assert _complete(client, unit, WORKER_A) == 200
    rows = client.get("/accounting/entries").json()
    assert len(rows) == 1
    row = rows[0]
    assert row["work_unit_id"] == unit["work_unit_id"]
    assert row["worker_id"] == WORKER_A
    assert row["cpu_time_ms"] == 4.0
    assert row["gpu_time_ms"] == 0.0  # CPU-only job: no GPU time
    assert row["verified"] is True
    assert row["voided_at"] is None


def test_gpu_job_records_gpu_time(client: TestClient):
    _register(client, WORKER_A)
    client.post(f"/workers/{WORKER_A}/capabilities", json={
        "schema_version": "1",
        "cpu": {"logical_cores": 8}, "ram": {"total_mb": 16000},
        "os": {"system": "Windows"},
        "gpus": [{"vendor": "amd", "model": "RX", "vram_mb": 8000}],
        "runtimes": ["hello_compute"],
    })
    _submit(client, requirements={"gpu": True, "gpu_vendor": "amd"})
    unit = _claim(client, WORKER_A)
    assert _complete(client, unit, WORKER_A) == 200
    row = client.get("/accounting/entries").json()[0]
    assert row["cpu_time_ms"] == 4.0
    assert row["gpu_time_ms"] == 4.0  # GPU-required job: wall time counts


def test_failed_unit_produces_no_record(client: TestClient):
    _register(client, WORKER_A)
    _submit(client)
    unit = _claim(client, WORKER_A)
    resp = client.post(f"/work/{unit['work_unit_id']}/result",
                       json={"worker_id": WORKER_A, "status": "completed",
                             "value": -999})
    assert resp.status_code == 422
    assert client.get("/accounting/entries").json() == []


def test_resubmit_does_not_double_count(client: TestClient):
    _register(client, WORKER_A)
    _submit(client, total=1, chunk=1)
    unit = _claim(client, WORKER_A)
    assert _complete(client, unit, WORKER_A) == 200
    assert _complete(client, unit, WORKER_A) == 200  # idempotent resubmit
    assert len(client.get("/accounting/entries").json()) == 1


def test_overturn_voids_record(client: TestClient):
    _register(client, WORKER_A)
    _register(client, WORKER_B)
    client.post(
        "/jobs",
        json={"workload_type": "hello_compute", "params": {"op": "sum"},
              "total_units": 1, "chunk_size": 1, "verify_sample": 1.0},
    )
    original = _claim(client, WORKER_A)
    assert _complete(client, original, WORKER_A) == 200
    dup = _claim(client, WORKER_B)
    assert dup["work_unit_id"] != original["work_unit_id"]
    resp = client.post(
        f"/work/{dup['work_unit_id']}/result",
        json={"worker_id": WORKER_B, "status": "completed", "value": 123456},
    )
    assert resp.status_code == 422
    rows = {r["work_unit_id"]: r for r in client.get("/accounting/entries").json()}
    assert rows[original["work_unit_id"]]["verified"] is False
    assert rows[original["work_unit_id"]]["voided_at"] is not None


def test_entries_filtering(client: TestClient):
    _register(client, WORKER_A)
    _register(client, WORKER_B)
    j1 = _submit(client)
    for wid in (WORKER_A, WORKER_B):
        unit = _claim(client, wid)
        assert _complete(client, unit, wid) == 200
    assert len(client.get("/accounting/entries").json()) == 2
    assert len(client.get(f"/accounting/entries?job_id={j1}").json()) == 2
    assert len(client.get(f"/accounting/entries?worker_id={WORKER_A}").json()) == 1
    assert client.get("/accounting/entries?worker_id=missing").json() == []
    assert len(client.get("/accounting/entries?limit=1").json()) == 1


def test_worker_summary_reconciles(client: TestClient):
    _register(client, WORKER_A)
    _submit(client, total=2, chunk=1)
    for _ in range(2):
        unit = _claim(client, WORKER_A)
        assert _complete(client, unit, WORKER_A) == 200
    summary = client.get(f"/workers/{WORKER_A}/accounting").json()
    assert summary["worker_id"] == WORKER_A
    assert summary["units_completed"] == 2
    assert summary["units_valid"] == 2
    assert summary["units_voided"] == 0
    assert summary["total_execution_ms"] == 8.0
    assert summary["total_cpu_time_ms"] == 8.0
    assert summary["total_gpu_time_ms"] == 0.0
    assert summary["verified_units"] == 2
    assert summary["reliability"] is None  # only 2 outcomes < MIN_EVIDENCE


def test_worker_summary_unknown_worker_404(client: TestClient):
    assert client.get(f"/workers/{uuid.uuid4()}/accounting").status_code == 404


def test_availability_none_without_heartbeats(client: TestClient):
    _register(client, WORKER_A)
    from app.db import get_db
    from app.main import app

    db = next(iter(app.dependency_overrides[get_db]()))
    try:
        from app.services.accounting import availability_fraction

        assert availability_fraction(db, WORKER_A) is None
    finally:
        db.close()


def test_availability_full_with_fresh_heartbeats(client: TestClient):
    from datetime import datetime, timedelta, timezone

    from app.db import get_db
    from app.main import app
    from app.models.heartbeat import WorkerHeartbeat

    _register(client, WORKER_A)
    db = next(iter(app.dependency_overrides[get_db]()))
    try:
        now = datetime.now(timezone.utc)
        # dense coverage of the last minute: every gap far below the timeout
        for seconds_ago in (50, 35, 20, 5):
            db.add(WorkerHeartbeat(worker_id=WORKER_A,
                                   received_at=now - timedelta(seconds=seconds_ago),
                                   resources={}))
        db.commit()
        from app.services.accounting import availability_fraction

        fraction = availability_fraction(db, WORKER_A, hours=1 / 60)
    finally:
        db.close()
    assert 0.7 < fraction <= 1.0


def test_availability_gap_counts_offline(client: TestClient):
    from datetime import datetime, timedelta, timezone

    from app.db import get_db
    from app.main import app
    from app.models.heartbeat import WorkerHeartbeat

    _register(client, WORKER_A)
    db = next(iter(app.dependency_overrides[get_db]()))
    try:
        now = datetime.now(timezone.utc)
        db.add(WorkerHeartbeat(worker_id=WORKER_A,
                               received_at=now - timedelta(minutes=50),
                               resources={}))
        db.add(WorkerHeartbeat(worker_id=WORKER_A, received_at=now, resources={}))
        db.commit()
        from app.services.accounting import availability_fraction

        fraction = availability_fraction(db, WORKER_A, hours=1.0)
    finally:
        db.close()
    assert fraction is not None and fraction < 0.05  # 50min gap in a 60min window
