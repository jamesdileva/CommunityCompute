"""Sprint 8: classified verification + duplicate execution (exit: corrupted
rejected, correct accepted — with reasons; sampling requires agreement)."""

import uuid

from fastapi.testclient import TestClient

WORKER_A = "aaaaaaaa-0000-0000-0000-000000000001"
WORKER_B = "bbbbbbbb-0000-0000-0000-000000000002"


def _register(client: TestClient, worker_id: str) -> None:
    assert client.post(
        "/workers/register",
        json={"worker_id": worker_id, "worker_version": "0.1.0-sprint8", "hostname": "PC-A"},
    ).status_code == 200


def _submit(client: TestClient, total: int = 1, chunk: int = 1, op: str = "sum",
            verify_sample: float = 0.0, **overrides) -> str:
    resp = client.post(
        "/jobs",
        json={
            "workload_type": "hello_compute",
            "params": {"op": op},
            "total_units": total,
            "chunk_size": chunk,
            "verify_sample": verify_sample,
            **overrides,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _claim(client: TestClient, worker_id: str) -> dict:
    return client.post(f"/work/{worker_id}/claim").json()


def _good(unit: dict, worker_id: str, value, output_hash=None) -> dict:
    return {
        "worker_id": worker_id,
        "status": "completed",
        "value": value,
        "output_hash": output_hash,
        "metrics": {"execution_ms": 1.0},
    }


def test_correct_result_accepted(client: TestClient):
    _submit(client)
    _register(client, WORKER_A)
    unit = _claim(client, WORKER_A)
    resp = client.post(f"/work/{unit['work_unit_id']}/result",
                       json=_good(unit, WORKER_A, 1))
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert resp.json()["failure_kind"] is None


def test_value_mismatch_classified(client: TestClient):
    _submit(client)
    _register(client, WORKER_A)
    unit = _claim(client, WORKER_A)
    bad = _good(unit, WORKER_A, 999)
    resp = client.post(f"/work/{unit['work_unit_id']}/result", json=bad)
    assert resp.status_code == 422
    detail = resp.json()["error"]["message"]
    assert detail["failure_kind"] == "value_mismatch"
    assert "mismatch" in detail["reason"]


def test_hash_mismatch_classified(client: TestClient):
    _submit(client)
    _register(client, WORKER_A)
    unit = _claim(client, WORKER_A)
    bad = _good(unit, WORKER_A, 1, output_hash="deadbeef")
    resp = client.post(f"/work/{unit['work_unit_id']}/result", json=bad)
    assert resp.status_code == 422
    assert resp.json()["error"]["message"]["failure_kind"] == "hash_mismatch"


def test_worker_error_classified(client: TestClient):
    _submit(client)
    _register(client, WORKER_A)
    unit = _claim(client, WORKER_A)
    failed = {"worker_id": WORKER_A, "status": "failed", "error": "gpu driver crashed"}
    resp = client.post(f"/work/{unit['work_unit_id']}/result", json=failed)
    assert resp.status_code == 422
    assert resp.json()["error"]["message"]["failure_kind"] == "worker_error"
    detail = client.get(f"/jobs/{unit['job_id']}").json()
    assert detail["aggregate"]["rejections"] == {"worker_error": 1}


def test_unsupported_workload_classified(client: TestClient):
    _submit(client, op="train_gpt")
    _register(client, WORKER_A)
    unit = _claim(client, WORKER_A)
    resp = client.post(f"/work/{unit['work_unit_id']}/result",
                       json=_good(unit, WORKER_A, 1))
    assert resp.status_code == 422
    assert resp.json()["error"]["message"]["failure_kind"] == "unsupported_workload"


def test_sample_zero_spawns_no_duplicates(client: TestClient):
    job_id = _submit(client, verify_sample=0.0)
    _register(client, WORKER_A)
    unit = _claim(client, WORKER_A)
    client.post(f"/work/{unit['work_unit_id']}/result", json=_good(unit, WORKER_A, 1))
    detail = client.get(f"/jobs/{job_id}").json()
    assert len(detail["work_units"]) == 1
    assert _claim(client, WORKER_A) == {}


def test_sample_full_duplicates_and_confirms(client: TestClient):
    """Two units, sample=1.0: every unit double-executed by different workers."""
    job_id = _submit(client, total=2, chunk=1, verify_sample=1.0)
    _register(client, WORKER_A)
    _register(client, WORKER_B)

    # originals
    a1 = _claim(client, WORKER_A)
    b1 = _claim(client, WORKER_B)
    assert a1["work_unit_id"] != b1["work_unit_id"]
    for unit, wid, value in ((a1, WORKER_A, a1["range_end"]), (b1, WORKER_B, b1["range_end"])):
        resp = client.post(f"/work/{unit['work_unit_id']}/result", json=_good(unit, wid, value))
        assert resp.status_code == 200

    # duplicates must go to the *other* worker
    a2 = _claim(client, WORKER_A)
    b2 = _claim(client, WORKER_B)
    assert {a2["work_unit_id"], b2["work_unit_id"]} != {a1["work_unit_id"], b1["work_unit_id"]}
    for unit, wid, value in ((a2, WORKER_A, a2["range_end"]), (b2, WORKER_B, b2["range_end"])):
        assert unit  # non-empty
        resp = client.post(f"/work/{unit['work_unit_id']}/result", json=_good(unit, wid, value))
        assert resp.status_code == 200

    detail = client.get(f"/jobs/{job_id}").json()
    assert detail["status"] == "completed"
    assert len(detail["work_units"]) == 4  # 2 originals + 2 check units
    assert _claim(client, WORKER_A) == {}

    from app.db import get_db
    from app.main import app
    from app.models.result import Result

    db = next(iter(app.dependency_overrides[get_db]()))
    originals = [r for r in db.query(Result).all() if r.verified_by]
    assert len(originals) == 2  # every original confirmed by the other worker
    assert {r.verified_by for r in originals} == {WORKER_A, WORKER_B}
    db.close()


def test_disagreement_fails_both(client: TestClient):
    job_id = _submit(client, total=1, chunk=1, verify_sample=1.0)
    _register(client, WORKER_A)
    _register(client, WORKER_B)

    original = _claim(client, WORKER_A)
    assert client.post(f"/work/{original['work_unit_id']}/result",
                       json=_good(original, WORKER_A, 1)).status_code == 200

    duplicate = _claim(client, WORKER_B)
    assert duplicate["work_unit_id"] != original["work_unit_id"]
    # B submits a *verifiable-but-wrong* value: differs from the confirmed 1
    resp = client.post(f"/work/{duplicate['work_unit_id']}/result",
                       json=_good(duplicate, WORKER_B, 7))
    assert resp.status_code == 422
    assert resp.json()["error"]["message"]["failure_kind"] == "verification_disagreement"

    detail = client.get(f"/jobs/{job_id}").json()
    statuses = {u["id"]: u["status"] for u in detail["work_units"]}
    assert statuses[original["work_unit_id"]] == "failed"  # overturned
    assert detail["status"] == "failed"


def test_same_worker_cannot_claim_own_duplicate(client: TestClient):
    """Only worker A around: its duplicate stays queued (verification must differ)."""
    _submit(client, total=1, chunk=1, verify_sample=1.0)
    _register(client, WORKER_A)
    original = _claim(client, WORKER_A)
    client.post(f"/work/{original['work_unit_id']}/result", json=_good(original, WORKER_A, 1))
    assert _claim(client, WORKER_A) == {}  # duplicate skipped for the same worker

    _register(client, WORKER_B)
    duplicate = _claim(client, WORKER_B)  # the other worker may take it
    assert duplicate and duplicate["work_unit_id"] != original["work_unit_id"]


def test_verify_sample_validation():
    from app.schemas.job import JobCreate

    try:
        JobCreate(workload_type="hello_compute", total_units=1, chunk_size=1,
                  verify_sample=1.5)
    except Exception:
        pass
    else:
        raise AssertionError("verify_sample > 1 must be rejected")
    assert str(uuid.uuid4())  # sanity
