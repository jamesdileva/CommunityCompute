"""Sprint 16: operator pause/resume, enforcement, summary, work, stats."""

import uuid

from fastapi.testclient import TestClient

WORKER_A = "aaaaaaaa-0000-0000-0000-000000000001"
WORKER_B = "bbbbbbbb-0000-0000-0000-000000000002"


def _register(client: TestClient, wid: str) -> None:
    assert client.post(
        "/workers/register",
        json={"worker_id": wid, "worker_version": "t", "hostname": "PC-A"},
    ).status_code == 200


def _submit(client: TestClient, total: int = 2, chunk: int = 1) -> str:
    resp = client.post(
        "/jobs",
        json={"workload_type": "hello_compute", "params": {"op": "sum"},
              "total_units": total, "chunk_size": chunk},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _complete(client: TestClient, wid: str) -> None:
    unit = client.post(f"/work/{wid}/claim").json()
    assert unit, "expected queued work"
    body = {"worker_id": wid, "status": "completed",
            "value": (unit["range_start"] + unit["range_end"])
            * (unit["range_end"] - unit["range_start"] + 1) // 2}
    assert client.post(f"/work/{unit['work_unit_id']}/result",
                       json=body).status_code == 200


def test_pause_resume_cycle(client: TestClient):
    _register(client, WORKER_A)
    assert client.post(f"/workers/{WORKER_A}/pause").status_code == 200
    row = {w["id"]: w for w in client.get("/workers").json()}[WORKER_A]
    assert row["status"] == "paused"
    assert row["paused_by_operator"] is True
    assert client.post(f"/workers/{WORKER_A}/resume").status_code == 200
    row = {w["id"]: w for w in client.get("/workers").json()}[WORKER_A]
    assert row["paused_by_operator"] is False


def test_pause_unknown_worker_404(client: TestClient):
    assert client.post(f"/workers/{str(uuid.uuid4())}/pause").status_code == 404
    assert client.post(f"/workers/{str(uuid.uuid4())}/resume").status_code == 404


def test_paused_worker_gets_no_work(client: TestClient):
    _register(client, WORKER_A)
    _submit(client)
    client.post(f"/workers/{WORKER_A}/pause")
    assert client.post(f"/work/{WORKER_A}/claim").json() == {}
    client.post(f"/workers/{WORKER_A}/resume")
    assert client.post(f"/work/{WORKER_A}/claim").json()["work_unit_id"]


def test_network_summary_counts(client: TestClient):
    _register(client, WORKER_A)
    _register(client, WORKER_B)
    _submit(client, total=3, chunk=1)
    _complete(client, WORKER_A)
    summary = client.get("/network/summary").json()
    assert summary["workers"]["total"] == 2
    assert summary["workers"]["by_status"]["online"] == 2
    assert summary["units"]["completed"] == 1
    assert summary["units"]["queued"] == 2
    assert summary["jobs"] == 1
    assert summary["completed_last_5m"] == 1


def test_worker_current_work_lists_leases(client: TestClient):
    _register(client, WORKER_A)
    _submit(client, total=2, chunk=1)
    assert client.get(f"/workers/{WORKER_A}/work").json() == []
    unit = client.post(f"/work/{WORKER_A}/claim").json()
    rows = client.get(f"/workers/{WORKER_A}/work").json()
    assert [r["id"] for r in rows] == [unit["work_unit_id"]]


def test_worker_stats_accumulate(client: TestClient):
    _register(client, WORKER_A)
    _submit(client, total=2, chunk=1)
    _complete(client, WORKER_A)
    _complete(client, WORKER_A)
    stats = client.get(f"/workers/{WORKER_A}/stats").json()
    assert stats["worker_id"] == WORKER_A
    assert stats["completed_units"] == 2
    assert stats["failed_units"] == 0
    assert stats["total_execution_ms"] >= 0
    assert stats["attempts"] == 2


def test_stats_unknown_worker_404(client: TestClient):
    assert client.get(f"/workers/{str(uuid.uuid4())}/stats").status_code == 404
    assert client.get(f"/workers/{str(uuid.uuid4())}/work").status_code == 404
