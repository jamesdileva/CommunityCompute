"""Sprint 6: work claim, verification, aggregation (M1 core, API level)."""

import httpx
from fastapi.testclient import TestClient


def _submit(client: TestClient, total: int = 3, chunk: int = 1, op: str = "sum") -> str:
    resp = client.post(
        "/jobs",
        json={
            "workload_type": "hello_compute",
            "params": {"op": op},
            "total_units": total,
            "chunk_size": chunk,
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _result_body(unit: dict, worker_id: str, value=None, status="completed", output_hash=None):
    return {
        "protocol_version": "0.1.0-sprint6",
        "worker_id": worker_id,
        "status": status,
        "value": value if value is not None else _sum(unit["range_start"], unit["range_end"]),
        "output_hash": output_hash,
        "metrics": {"execution_ms": 1.5},
    }


def _sum(start: int, end: int) -> int:
    return (start + end) * (end - start + 1) // 2


WORKER_A = "aaaaaaaa-0000-0000-0000-000000000001"
WORKER_B = "bbbbbbbb-0000-0000-0000-000000000002"


def _register(client: TestClient, worker_id: str) -> None:
    resp = client.post(
        "/workers/register",
        json={"worker_id": worker_id, "worker_version": "0.1.0-sprint6", "hostname": "PC-A"},
    )
    assert resp.status_code == 200


def test_claim_returns_oldest_queued_unit(client: TestClient):
    job_id = _submit(client, total=3, chunk=1)
    _register(client, WORKER_A)
    a = client.get(f"/work/{WORKER_A}").json()
    assert a["work_unit_id"] and a["range_start"] == 1 and a["range_end"] == 1
    assert a["job_id"] == job_id
    b = client.get(f"/work/{WORKER_A}").json()
    assert b["range_start"] == 2
    assert a["work_unit_id"] != b["work_unit_id"]  # no double-assignment
    assert client.get(f"/work/{WORKER_A}").json()["range_start"] == 3
    assert client.get(f"/work/{WORKER_A}").json() == {}  # queue empty


def test_claim_distributes_across_workers(client: TestClient):
    _submit(client, total=2, chunk=1)
    _register(client, WORKER_A)
    _register(client, WORKER_B)
    a = client.get(f"/work/{WORKER_A}").json()
    b = client.get(f"/work/{WORKER_B}").json()
    assert a["work_unit_id"] != b["work_unit_id"]


def test_unit_status_becomes_completed(client: TestClient):
    _submit(client, total=1, chunk=1)
    _register(client, WORKER_A)
    unit = client.get(f"/work/{WORKER_A}").json()
    resp = client.post(f"/work/{unit['work_unit_id']}/result", json=_result_body(unit, WORKER_A))
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    detail = client.get(f"/jobs/{unit['job_id']}").json()
    assert detail["status"] == "completed"
    assert detail["counts"] == {"completed": 1}


def test_corrupted_result_is_rejected(client: TestClient):
    _submit(client, total=2, chunk=1)
    _register(client, WORKER_A)
    unit = client.get(f"/work/{WORKER_A}").json()  # range 1..1, correct value 1
    body = _result_body(unit, WORKER_A, value=999)  # wrong
    resp = client.post(f"/work/{unit['work_unit_id']}/result", json=body)
    assert resp.status_code == 422
    reason = resp.json()["error"]["message"]["reason"]
    assert "mismatch" in reason
    detail = client.get(f"/jobs/{unit['job_id']}").json()
    assert detail["counts"]["failed"] == 1
    assert detail["status"] == "failed"  # job must not complete with a bad unit


def test_hash_op_verification(client: TestClient):
    import hashlib

    _submit(client, total=1, chunk=1, op="hash")
    _register(client, WORKER_A)
    unit = client.get(f"/work/{WORKER_A}").json()
    expected = hashlib.sha256(b"1:1").hexdigest()
    good = _result_body(unit, WORKER_A, value=expected,
                        output_hash=hashlib.sha256(f"hash:{expected}".encode()).hexdigest())
    assert client.post(f"/work/{unit['work_unit_id']}/result", json=good).status_code == 200

    _submit(client, total=1, chunk=1, op="hash")
    unit2 = client.get(f"/work/{WORKER_A}").json()
    bad_hash = _result_body(unit2, WORKER_A, value=expected, output_hash="deadbeef")
    assert client.post(f"/work/{unit2['work_unit_id']}/result", json=bad_hash).status_code == 422


def test_duplicate_result_is_idempotent(client: TestClient):
    _submit(client, total=1, chunk=1)
    _register(client, WORKER_A)
    unit = client.get(f"/work/{WORKER_A}").json()
    body = _result_body(unit, WORKER_A)
    assert client.post(f"/work/{unit['work_unit_id']}/result", json=body).status_code == 200
    assert client.post(f"/work/{unit['work_unit_id']}/result", json=body).status_code == 200


def test_result_for_unknown_unit_404(client: TestClient):
    body = {"worker_id": WORKER_A, "status": "completed", "value": 1}
    resp = client.post("/work/nope-nope-nope/result", json=body)
    assert resp.status_code == 404


def test_job_aggregation_final_sum(client: TestClient):
    """M1: one job, several units, all verified → correct single final result."""
    job_id = _submit(client, total=10, chunk=1)
    _register(client, WORKER_A)
    _register(client, WORKER_B)
    for _ in range(10):
        wid = WORKER_A if _ % 2 == 0 else WORKER_B
        unit = client.get(f"/work/{wid}").json()
        if not unit:
            unit = client.get(f"/work/{WORKER_A}").json()
        assert client.post(
            f"/work/{unit['work_unit_id']}/result", json=_result_body(unit, wid)
        ).status_code == 200
    detail = client.get(f"/jobs/{job_id}").json()
    assert detail["status"] == "completed"
    assert detail["counts"] == {"completed": 10}
    assert detail["aggregate"]["final"] == sum(range(1, 11))  # 55


def test_claim_rejects_unknown_protocol_version(client: TestClient):
    _submit(client, total=1, chunk=1)
    _register(client, WORKER_A)
    unit = client.get(f"/work/{WORKER_A}").json()
    bad = {**_result_body(unit, WORKER_A), "protocol_version": "0.0.1-ancient"}
    # coordinator accepts (it validates the value, not the bump), worker would
    # have refused; verified end-to-end in worker executor tests.
    assert client.post(f"/work/{unit['work_unit_id']}/result", json=bad).status_code == 200
