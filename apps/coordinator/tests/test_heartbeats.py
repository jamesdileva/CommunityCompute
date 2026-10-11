"""Sprint 4: heartbeat upsert, online/offline derivation, malformed rejection."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models.worker import Worker

HB = {
    "worker_id": "",  # filled per-test
    "resources": {"cpu_percent": 42.5, "ram_available_mb": 5000, "gpu_percent": 12.0},
}


def _register(client: TestClient, wid: str) -> None:
    resp = client.post(
        "/workers/register",
        json={"worker_id": wid, "worker_version": "0.1.0-sprint4", "hostname": "PC-A"},
    )
    assert resp.status_code == 200


def _beat(client: TestClient, wid: str, **overrides) -> TestClient:
    body = {**HB, "worker_id": wid, **overrides}
    return client.post(f"/workers/{wid}/heartbeat", json=body)


def test_heartbeat_refreshes_status_and_resources(client: TestClient):
    wid = str(uuid.uuid4())
    _register(client, wid)
    resp = _beat(client, wid)
    assert resp.status_code == 200
    assert resp.json()["status"] == "online"
    assert "server_time" in resp.json()

    row = {w["id"]: w for w in client.get("/workers").json()}[wid]
    assert row["status"] == "online"
    assert row["cpu_percent"] == 42.5
    assert row["gpu_percent"] == 12.0
    assert row["ram_available_mb"] == 5000


def test_heartbeat_unknown_worker_404(client: TestClient):
    wid = str(uuid.uuid4())
    assert _beat(client, wid).status_code == 404


def test_heartbeat_id_mismatch_422(client: TestClient):
    wid = str(uuid.uuid4())
    _register(client, wid)
    body = {**HB, "worker_id": str(uuid.uuid4())}  # different from path
    resp = client.post(f"/workers/{wid}/heartbeat", json=body)
    assert resp.status_code == 422


def test_heartbeat_bad_resources_422(client: TestClient):
    wid = str(uuid.uuid4())
    _register(client, wid)
    body = {**HB, "worker_id": wid, "resources": {"cpu_percent": 999}}
    assert client.post(f"/workers/{wid}/heartbeat", json=body).status_code == 422


def test_worker_goes_offline_after_timeout(client: TestClient):
    wid = str(uuid.uuid4())
    _register(client, wid)
    assert _beat(client, wid).status_code == 200

    # age last_seen beyond timeout (60s default)
    db = next(iter(app.dependency_overrides[get_db]()))
    worker = db.get(Worker, wid)
    worker.last_seen = datetime.now(timezone.utc) - timedelta(seconds=120)
    db.commit()
    db.close()

    row = {w["id"]: w for w in client.get("/workers").json()}[wid]
    assert row["status"] == "offline"

    # a fresh heartbeat brings it back
    assert _beat(client, wid).status_code == 200
    row = {w["id"]: w for w in client.get("/workers").json()}[wid]
    assert row["status"] == "online"


def test_heartbeat_log_accumulates(client: TestClient):
    wid = str(uuid.uuid4())
    _register(client, wid)
    _beat(client, wid)
    _beat(client, wid)
    log = client.get(f"/workers/{wid}/heartbeats").json()
    assert len(log) == 2
    assert log[0]["resources"]["cpu_percent"] == 42.5  # newest first
