"""Sprint 2: registration upsert + worker listing."""

import uuid

from fastapi.testclient import TestClient


def _payload(wid: str | None = None, **overrides) -> dict:
    body: dict = {
        "worker_id": wid or str(uuid.uuid4()),
        "worker_version": "0.1.0-sprint2",
        "hostname": "PC-A",
    }
    body.update(overrides)
    return body


def test_register_creates_worker(client: TestClient):
    body = _payload()
    resp = client.post("/workers/register", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == body["worker_id"]
    assert data["worker_version"] == body["worker_version"]
    assert data["hostname"] == "PC-A"
    assert data["status"] == "online"
    assert data["last_seen"] is not None

    listed = client.get("/workers").json()
    assert [w["id"] for w in listed] == [body["worker_id"]]


def test_register_is_idempotent(client: TestClient):
    wid = str(uuid.uuid4())
    assert client.post("/workers/register", json=_payload(wid)).status_code == 200
    resp = client.post(
        "/workers/register", json=_payload(wid, worker_version="0.1.0-sprint2b")
    )
    assert resp.status_code == 200
    assert resp.json()["worker_version"] == "0.1.0-sprint2b"
    assert len(client.get("/workers").json()) == 1


def test_two_workers_have_unique_ids(client: TestClient):
    id_a, id_b = str(uuid.uuid4()), str(uuid.uuid4())
    assert id_a != id_b
    client.post("/workers/register", json=_payload(id_a, hostname="PC-A"))
    client.post("/workers/register", json=_payload(id_b, hostname="PC-B"))
    ids = sorted(w["id"] for w in client.get("/workers").json())
    assert ids == sorted([id_a, id_b])


def test_register_rejects_bad_uuid(client: TestClient):
    resp = client.post("/workers/register", json=_payload("not-a-uuid"))
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == 422


def test_register_rejects_missing_version(client: TestClient):
    body = _payload()
    del body["worker_version"]
    resp = client.post("/workers/register", json=body)
    assert resp.status_code == 422
