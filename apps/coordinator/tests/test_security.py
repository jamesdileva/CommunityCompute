"""Sprint 21: boundary enforcement — submit allowlist + sealed claims."""

import logging
import uuid

from fastapi.testclient import TestClient

from packages.protocol.signing import DEV_SIGNING_KEY, verify_manifest

WORKER = "aaaaaaaa-0000-0000-0000-000000000001"


def _register(client: TestClient, wid: str = WORKER) -> None:
    assert client.post(
        "/workers/register",
        json={"worker_id": wid, "worker_version": "t", "hostname": "PC-A"},
    ).status_code == 200


def test_unknown_workload_type_rejected_at_submit(client: TestClient):
    resp = client.post(
        "/jobs",
        json={"workload_type": "train_gpt", "total_units": 10, "chunk_size": 5},
    )
    assert resp.status_code == 422
    assert "not allowlisted" in str(resp.json())


def test_unknown_workload_creates_no_rows(client: TestClient):
    before = len(client.get("/jobs").json())
    client.post("/jobs", json={"workload_type": "evil", "total_units": 1,
                               "chunk_size": 1})
    assert len(client.get("/jobs").json()) == before  # nothing persisted


def test_known_workloads_still_accepted(client: TestClient):
    for workload in ("hello_compute", "stats_range", "embeddings", "image_generate"):
        resp = client.post(
            "/jobs",
            json={"workload_type": workload, "total_units": 2, "chunk_size": 2},
        )
        assert resp.status_code == 201, (workload, resp.text)


def test_claim_carries_valid_seal(client: TestClient):
    client.post(
        "/jobs",
        json={"workload_type": "hello_compute", "params": {"op": "sum"},
              "total_units": 2, "chunk_size": 1},
    )
    _register(client)
    assignment = client.post(f"/work/{WORKER}/claim").json()
    assert assignment["manifest_signature"]
    assert verify_manifest(assignment, assignment["manifest_signature"],
                           DEV_SIGNING_KEY) is True


def test_seal_covers_inputs(client: TestClient):
    client.post(
        "/jobs",
        json={"workload_type": "hello_compute", "params": {"op": "sum"},
              "total_units": 1, "chunk_size": 1},
    )
    _register(client)
    assignment = client.post(f"/work/{WORKER}/claim").json()
    good = assignment["manifest_signature"]
    assert verify_manifest(assignment, good, DEV_SIGNING_KEY) is True
    flipped = {**assignment, "range_end": assignment["range_end"] + 1000}
    assert verify_manifest(flipped, good, DEV_SIGNING_KEY) is False


def test_seal_survives_duplicate_units(client: TestClient):
    """Duplicates are separate sealed units (same ranges, distinct ids)."""
    job = client.post(
        "/jobs",
        json={"workload_type": "hello_compute", "params": {"op": "sum"},
              "total_units": 1, "chunk_size": 1, "verify_sample": 1.0},
    ).json()["id"]
    _register(client)
    other = str(uuid.uuid4())
    client.post("/workers/register",
                json={"worker_id": other, "worker_version": "t", "hostname": "PC-B"})
    first = client.post(f"/work/{WORKER}/claim").json()
    assert first  # original
    client.post(
        f"/work/{first['work_unit_id']}/result",
        json={"worker_id": WORKER, "status": "completed",
              "value": first["range_end"]},
    )
    dup = client.post(f"/work/{other}/claim").json()
    assert dup and dup["work_unit_id"] != first["work_unit_id"]
    assert verify_manifest(dup, dup["manifest_signature"], DEV_SIGNING_KEY) is True


def test_dev_signing_key_warns_on_startup(caplog):
    """The dev default must be loud: sealed-but-forgeable assignments."""
    from app.main import app

    with caplog.at_level(logging.WARNING, logger="coordinator"), TestClient(app):
        pass
    assert any("WORKLOAD_SIGNING_KEY" in r.message for r in caplog.records)
