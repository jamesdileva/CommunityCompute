"""Sprint 20: worker authentication — enrollment, bearer, revocation, rotation.

Auth is enabled per-test via `AUTH_ENABLED=true`; the shared fixture keeps the
coordinator app in a config-free state (routes with auth pinned get 401s).
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.models.auth import EnrollmentToken, WorkerCredential
from settings_override import auth_enabled, override_settings

AUTH_BODY = {
    "worker_version": "0.1.0-sprint20",
    "hostname": "PC-A",
}


def test_enrollment_token_minted_once(client: TestClient):
    resp = client.post("/auth/enrollment-tokens", json={"note": "laptop"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["token"] and len(data["token"]) >= 20
    listed = client.get("/auth/enrollment-tokens").json()
    assert len(listed) == 1
    assert listed[0]["used"] is False


def test_enroll_returns_worker_and_credential(client: TestClient):
    mint = client.post("/auth/enrollment-tokens", json={}).json()["token"]
    resp = client.post("/auth/enroll", json={"enrollment_token": mint})
    assert resp.status_code == 201
    body = resp.json()
    assert body["worker_id"] and body["token"] and body["status"] == "enrolled"
    # enrollment token is single-use
    again = client.post("/auth/enroll", json={"enrollment_token": mint})
    assert again.status_code == 401
    # a worker record exists now
    workers = client.get("/workers").json()
    assert any(w["id"] == body["worker_id"] for w in workers)


def test_enroll_rejects_unknown_token(client: TestClient):
    resp = client.post("/auth/enroll", json={"enrollment_token": "nope-nope-nope"})
    assert resp.status_code == 401
    detail = resp.json()["error"]["message"]
    assert detail["reason"] == "unknown enrollment token"


def test_credential_stored_hashed_only(client: TestClient):
    mint = client.post("/auth/enrollment-tokens", json={}).json()["token"]
    body = client.post("/auth/enroll", json={"enrollment_token": mint}).json()
    from app.db import get_db
    from app.models.auth import WorkerCredential

    db = next(iter(client.app.dependency_overrides[get_db]()))
    try:
        cred = db.query(WorkerCredential).filter_by(worker_id=body["worker_id"]).first()
        assert cred is not None
        assert cred.token_hash != body["token"]  # the raw token is never stored
        assert len(cred.token_hash) == 64  # sha256 hex
    finally:
        db.close()


def test_auth_disabled_allows_anonymous(client: TestClient):
    # default AUTH_ENABLED=false: the pre-Sprint-20 flow keeps working
    resp = client.post(
        "/workers/register",
        json={"worker_id": "00000000-0000-0000-0000-000000000001", **AUTH_BODY},
    )
    assert resp.status_code == 200


def test_auth_enabled_blocks_anonymous(client: TestClient):
    with override_settings(**auth_enabled()):
        wid = "00000000-0000-0000-0000-000000000001"
        resp = client.post(
            "/workers/register", json={"worker_id": wid, **AUTH_BODY}
        )
        assert resp.status_code == 401
        # envelope nests reason under error.message
        assert resp.json()["error"]["message"]["error"] == "unauthorized"
        # claims and telemetry too
        assert client.post(f"/work/{wid}/claim").status_code == 401
        assert client.post(f"/workers/{wid}/heartbeat",
                           json={"worker_id": wid, "resources": {}}).status_code == 401

def test_auth_enabled_valid_bearer_passes(client: TestClient):
    with override_settings(**auth_enabled()):
        mint = client.post("/auth/enrollment-tokens", json={}).json()["token"]
        enrolled = client.post("/auth/enroll", json={"enrollment_token": mint}).json()
        headers = {"Authorization": f"Bearer {enrolled['token']}"}
        resp = client.post(
            "/workers/register",
            json={"worker_id": enrolled["worker_id"], **AUTH_BODY},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == enrolled["worker_id"]
        # heartbeat + resources + capabilities all accept the same bearer
        assert client.post(
            f"/workers/{enrolled['worker_id']}/heartbeat",
            json={"worker_id": enrolled["worker_id"],
                  "resources": {"cpu_percent": 1.0}},
            headers=headers,
        ).status_code == 200
        claim = client.post(f"/work/{enrolled['worker_id']}/claim", headers=headers)
        assert claim.status_code == 200


def test_token_of_other_worker_rejected(client: TestClient):
    with override_settings(**auth_enabled()):
        m1 = client.post("/auth/enrollment-tokens", json={}).json()["token"]
        m2 = client.post("/auth/enrollment-tokens", json={}).json()["token"]
        w1 = client.post("/auth/enroll", json={"enrollment_token": m1}).json()
        w2 = client.post("/auth/enroll", json={"enrollment_token": m2}).json()
        # worker 2's token used against worker 1's identity -> 401
        resp = client.post(
            "/workers/register",
            json={"worker_id": w2["worker_id"], **AUTH_BODY},
            headers={"Authorization": f"Bearer {w1['token']}"},
        )
        assert resp.status_code == 401


def test_revoked_worker_loses_access(client: TestClient):
    with override_settings(**auth_enabled()):
        mint = client.post("/auth/enrollment-tokens", json={}).json()["token"]
        w = client.post("/auth/enroll", json={"enrollment_token": mint}).json()
        headers = {"Authorization": f"Bearer {w['token']}"}
        assert client.post(
            "/workers/register",
            json={"worker_id": w["worker_id"], **AUTH_BODY},
            headers=headers,
        ).status_code == 200
        rev = client.post(f"/workers/{w['worker_id']}/revoke")
        assert rev.status_code == 200 and rev.json()["revoked"] == 1
        after = client.post(
            "/workers/register",
            json={"worker_id": w["worker_id"], **AUTH_BODY},
            headers=headers,
        )
        assert after.status_code == 401
        # claims stop too
        assert client.post(f"/work/{w['worker_id']}/claim",
                           headers=headers).status_code == 401


def test_rotation_invalidates_old_credential(client: TestClient):
    with override_settings(**auth_enabled()):
        mint = client.post("/auth/enrollment-tokens", json={}).json()["token"]
        w = client.post("/auth/enroll", json={"enrollment_token": mint}).json()
        old_headers = {"Authorization": f"Bearer {w['token']}"}
        rot = client.post(f"/workers/{w['worker_id']}/rotate-credential")
        assert rot.status_code == 200
        new_token = rot.json()["token"]
        assert client.post(
            "/workers/register",
            json={"worker_id": w["worker_id"], **AUTH_BODY},
            headers=old_headers,
        ).status_code == 401
        assert client.post(
            "/workers/register",
            json={"worker_id": w["worker_id"], **AUTH_BODY},
            headers={"Authorization": f"Bearer {new_token}"},
        ).status_code == 200


def test_enrollment_token_ttl_expires(client: TestClient):
    from datetime import datetime, timedelta, timezone

    mint = client.post(
        "/auth/enrollment-tokens", json={"ttl_minutes": 1}
    ).json()["token"]
    # age it
    from app.db import get_db

    db = next(iter(client.app.dependency_overrides[get_db]()))
    row = db.query(EnrollmentToken).first()
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db.commit()
    db.close()
    assert client.post("/auth/enroll",
                       json={"enrollment_token": mint}).status_code == 401


def _enrolled(client: TestClient) -> dict:
    mint = client.post("/auth/enrollment-tokens", json={}).json()["token"]
    return client.post("/auth/enroll", json={"enrollment_token": mint}).json()


def test_ws_without_token_refused_when_auth_enabled(client: TestClient):
    with override_settings(**auth_enabled()):
        w = _enrolled(client)
        with client.websocket_connect(f"/ws/worker/{w['worker_id']}") as ws:
            with pytest.raises(WebSocketDisconnect) as exc:
                ws.receive_json()
        assert exc.value.code == 4401


def test_ws_with_bad_token_refused(client: TestClient):
    with override_settings(**auth_enabled()):
        w = _enrolled(client)
        with client.websocket_connect(
            f"/ws/worker/{w['worker_id']}?token=nope-nope-nope"
        ) as ws:
            with pytest.raises(WebSocketDisconnect) as exc:
                ws.receive_json()
        assert exc.value.code == 4401


def test_ws_with_other_workers_token_refused(client: TestClient):
    with override_settings(**auth_enabled()):
        w1 = _enrolled(client)
        w2 = _enrolled(client)
        with client.websocket_connect(
            f"/ws/worker/{w1['worker_id']}?token={w2['token']}"
        ) as ws:
            with pytest.raises(WebSocketDisconnect) as exc:
                ws.receive_json()
        assert exc.value.code == 4401


def test_ws_with_own_token_works(client: TestClient):
    with override_settings(**auth_enabled()):
        w = _enrolled(client)
        with client.websocket_connect(
            f"/ws/worker/{w['worker_id']}?token={w['token']}"
        ) as ws:
            ws.send_json({"type": "hello"})
            assert ws.receive_json()["type"] == "hello_ack"
            ws.send_json({"type": "heartbeat", "resources": {"cpu_percent": 3.0}})
            ack = ws.receive_json()
            assert ack["type"] == "heartbeat_ack"
            assert ack["status"] == "online"


def test_ws_revoked_token_refused(client: TestClient):
    with override_settings(**auth_enabled()):
        w = _enrolled(client)
        assert client.post(f"/workers/{w['worker_id']}/revoke").status_code == 200
        with client.websocket_connect(
            f"/ws/worker/{w['worker_id']}?token={w['token']}"
        ) as ws:
            with pytest.raises(WebSocketDisconnect) as exc:
                ws.receive_json()
        assert exc.value.code == 4401


def test_ws_open_when_auth_disabled(client: TestClient):
    wid = str(uuid.uuid4())
    client.post("/workers/register",
                json={"worker_id": wid, **AUTH_BODY})
    with client.websocket_connect(f"/ws/worker/{wid}") as ws:
        ws.send_json({"type": "hello"})
        assert ws.receive_json()["type"] == "hello_ack"
