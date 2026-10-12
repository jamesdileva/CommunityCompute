"""Sprint 14: embeddings job end-to-end via the claim→result API (M4 proof)."""

import uuid

from fastapi.testclient import TestClient

WORKER_A = "aaaaaaaa-0000-0000-0000-000000000001"
WORKER_B = "bbbbbbbb-0000-0000-0000-000000000002"

_DIM = 32


def _register(client: TestClient, wid: str) -> None:
    assert client.post(
        "/workers/register",
        json={"worker_id": wid, "worker_version": "t", "hostname": "PC-A"},
    ).status_code == 200


def _batch(start: int, end: int) -> dict:
    """Same deterministic math as both sides (small mirror for the test)."""
    import hashlib
    import math
    import re

    token_re = re.compile(r"[a-z0-9]+")

    def text(i: int) -> str:
        return (f"document {i} topic {i % 12} "
                f"community compute worker index {i} sample text {i % 7}")

    vectors = []
    for i in range(start, end + 1):
        vector = [0.0] * _DIM
        for token in token_re.findall(text(i).lower()):
            digest = hashlib.sha256(token.encode()).digest()
            slot = int.from_bytes(digest[:4], "big") % _DIM
            sign = 1.0 if digest[4] & 1 == 0 else -1.0
            vector[slot] += sign
        norm = math.sqrt(sum(v * v for v in vector))
        vectors.append([round(v / norm, 6) for v in vector])
    return {"dim": _DIM, "vectors": vectors}


def test_embeddings_job_verified_batch(client: TestClient):
    resp = client.post(
        "/jobs",
        json={"workload_type": "embeddings", "params": {"dim": _DIM},
              "total_units": 10, "chunk_size": 5},
    )
    assert resp.status_code == 201, resp.text
    job_id = resp.json()["id"]
    _register(client, WORKER_A)

    for expected_batch in ((_batch(1, 5)), (_batch(6, 10))):
        unit = client.post(f"/work/{WORKER_A}/claim").json()
        body = {"worker_id": WORKER_A, "status": "completed",
                "value": expected_batch, "metrics": {"docs": 5, "dim": _DIM}}
        assert client.post(f"/work/{unit['work_unit_id']}/result",
                           json=body).status_code == 200

    detail = client.get(f"/jobs/{job_id}").json()
    assert detail["status"] == "completed"
    assert detail["counts"] == {"completed": 2}


def test_embeddings_wrong_vectors_rejected(client: TestClient):
    resp = client.post(
        "/jobs",
        json={"workload_type": "embeddings", "params": {"dim": _DIM},
              "total_units": 5, "chunk_size": 5},
    )
    assert resp.status_code == 201
    job_id = resp.json()["id"]
    _register(client, WORKER_A)
    unit = client.post(f"/work/{WORKER_A}/claim").json()
    tampered = _batch(1, 5)
    tampered["vectors"][0] = [0.0] * _DIM  # single corrupted vector
    resp = client.post(f"/work/{unit['work_unit_id']}/result",
                       json={"worker_id": WORKER_A, "status": "completed",
                             "value": tampered})
    assert resp.status_code == 422
    assert resp.json()["error"]["message"]["failure_kind"] == "value_mismatch"
    detail = client.get(f"/jobs/{job_id}").json()
    assert detail["status"] == "failed"


def test_embeddings_two_workers_split_batches(client: TestClient):
    client.post(
        "/jobs",
        json={"workload_type": "embeddings", "params": {"dim": _DIM},
              "total_units": 4, "chunk_size": 2},
    )
    _register(client, WORKER_A)
    _register(client, WORKER_B)
    a = client.post(f"/work/{WORKER_A}/claim").json()
    b = client.post(f"/work/{WORKER_B}/claim").json()
    assert a["work_unit_id"] != b["work_unit_id"]
    for unit, wid in ((a, WORKER_A), (b, WORKER_B)):
        body = {"worker_id": wid, "status": "completed",
                "value": _batch(unit["range_start"], unit["range_end"])}
        assert client.post(f"/work/{unit['work_unit_id']}/result",
                           json=body).status_code == 200
