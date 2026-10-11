"""Sprint 12: resource telemetry samples + availability-driven statuses."""

import uuid

from fastapi.testclient import TestClient

WORKER = "aaaaaaaa-0000-0000-0000-000000000001"

REPORT = {
    "cpu_percent": 22.5,
    "ram_available_mb": 4000,
    "ram_used_percent": 75.5,
    "gpu_percent": 10.0,
    "gpu_vram_used_mb": 2048,
    "gpu_temp_c": 61.0,
}


def _register(client: TestClient, wid: str = WORKER) -> None:
    assert client.post(
        "/workers/register",
        json={"worker_id": wid, "worker_version": "t", "hostname": "PC-A"},
    ).status_code == 200


def test_post_sample_ok(client: TestClient):
    _register(client)
    resp = client.post(f"/workers/{WORKER}/resources", json=REPORT)
    assert resp.status_code == 200
    row = resp.json()
    assert row["worker_id"] == WORKER
    assert row["cpu_percent"] == 22.5
    assert row["gpu_vram_used_mb"] == 2048
    assert row["sampled_at"]


def test_post_sample_unknown_worker_404(client: TestClient):
    wid = str(uuid.uuid4())
    assert client.post(f"/workers/{wid}/resources", json=REPORT).status_code == 404


def test_samples_list_newest_first(client: TestClient):
    _register(client)
    for cpu in (1.0, 2.0, 3.0):
        assert client.post(f"/workers/{WORKER}/resources",
                           json={**REPORT, "cpu_percent": cpu}).status_code == 200
    rows = client.get(f"/workers/{WORKER}/resources").json()
    assert [r["cpu_percent"] for r in rows[:3]] == [3.0, 2.0, 1.0]


def test_partial_sample_allowed(client: TestClient):
    """Undetectable metrics omitted (None) — schemas must accept partials."""
    _register(client)
    resp = client.post(f"/workers/{WORKER}/resources", json={"cpu_percent": 1.0})
    assert resp.status_code == 200
    assert resp.json()["gpu_temp_c"] is None


def test_heartbeat_availability_paused_status(client: TestClient):
    _register(client)
    body = {"worker_id": WORKER, "resources": {"cpu_percent": 5.0},
            "availability": {"available": True, "paused": True, "reason": "paused by contributor"}}
    resp = client.post(f"/workers/{WORKER}/heartbeat", json=body)
    assert resp.status_code == 200
    assert resp.json()["status"] == "paused"
    assert {w["id"]: w for w in client.get("/workers").json()}[WORKER]["status"] == "paused"


def test_heartbeat_availability_throttled_status(client: TestClient):
    _register(client)
    body = {"worker_id": WORKER, "resources": {"cpu_percent": 95.0},
            "availability": {"available": False, "paused": False,
                             "reason": "cpu 95.0% > limit 10%"}}
    resp = client.post(f"/workers/{WORKER}/heartbeat", json=body)
    assert resp.status_code == 200
    assert resp.json()["status"] == "throttled"
    assert {w["id"]: w for w in client.get("/workers").json()}[WORKER]["status"] == "throttled"


def test_throttled_worker_back_to_online(client: TestClient):
    _register(client)
    client.post(f"/workers/{WORKER}/heartbeat", json={
        "worker_id": WORKER, "resources": {},
        "availability": {"available": False, "paused": False, "reason": "busy"},
    })
    resp = client.post(f"/workers/{WORKER}/heartbeat", json={
        "worker_id": WORKER, "resources": {},
        "availability": {"available": True, "paused": False, "reason": "ok"},
    })
    assert resp.json()["status"] == "online"


def test_heartbeat_without_availability_derives_online(client: TestClient):
    _register(client)
    resp = client.post(f"/workers/{WORKER}/heartbeat",
                       json={"worker_id": WORKER, "resources": {}})
    assert resp.json()["status"] == "online"
