"""Sprint 26: capacity rollup, version gating, lease-cap abuse control."""

import uuid

from fastapi.testclient import TestClient

from app.services import reputation  # noqa: F401 - ensures service import order
from settings_override import override_settings

AMD_PROFILE = {
    "schema_version": "1",
    "cpu": {"arch": "AMD64", "logical_cores": 12, "physical_cores": 6},
    "ram": {"total_mb": 16258, "available_mb": 5000},
    "os": {"system": "Windows", "release": "11"},
    "gpus": [{"vendor": "amd", "model": "RX 6400", "vram_mb": 4080}],
    "runtimes": ["hello_compute"],
    "cached_models": [{"name": "hashing-embedder", "version": "1"}],
}


def _register(client: TestClient, wid: str, version: str = "0.1.0-x") -> None:
    assert client.post(
        "/workers/register",
        json={"worker_id": wid, "worker_version": version, "hostname": "PC-A"},
    ).status_code == 200


def _submit(client: TestClient, total: int = 1, chunk: int = 1) -> str:
    resp = client.post(
        "/jobs",
        json={"workload_type": "hello_compute", "params": {"op": "sum"},
              "total_units": total, "chunk_size": chunk},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def test_capacity_rollup(client: TestClient):
    wid_a, wid_b = str(uuid.uuid4()), str(uuid.uuid4())
    _register(client, wid_a)
    _register(client, wid_b)
    assert client.post(f"/workers/{wid_a}/capabilities",
                       json=AMD_PROFILE).status_code == 200
    client.post(f"/workers/{wid_a}/heartbeat",
                json={"worker_id": wid_a, "resources": {}})
    _submit(client, total=3, chunk=1)
    cap = client.get("/network/capacity").json()
    assert cap["total_workers"] == 2
    assert cap["online_workers"] == 2  # both freshly registered (last_seen now)
    assert cap["cpu_cores"] == 6
    assert cap["ram_mb"] == 16258
    assert cap["gpus_by_tier"] == {"H1": 1}  # 4080MB RX 6400
    assert cap["gpus_by_vendor"] == {"amd": 1}
    assert cap["cached_models"] == {"hashing-embedder@1": 1}
    assert cap["runtimes"] == {"hello_compute": 1}
    assert cap["queued_units"] == 3


def test_capacity_empty_pool(client: TestClient):
    cap = client.get("/network/capacity").json()
    assert cap == {"online_workers": 0, "total_workers": 0, "cpu_cores": 0,
                   "ram_mb": 0, "gpus_by_tier": {}, "gpus_by_vendor": {},
                   "cached_models": {}, "runtimes": {}, "versions": {},
                   "queued_units": 0}


def test_versions_listed(client: TestClient):
    _register(client, str(uuid.uuid4()), version="0.1.0-old")
    _register(client, str(uuid.uuid4()), version="0.1.0-new")
    versions = client.get("/network/capacity").json()["versions"]
    assert versions == {"0.1.0-old": 1, "0.1.0-new": 1}


def test_outdated_worker_gets_426(client: TestClient):
    wid = str(uuid.uuid4())
    _register(client, wid, version="0.0.1-ancient")
    _submit(client)
    with override_settings(MIN_WORKER_VERSION="0.1.0"):
        resp = client.post(f"/work/{wid}/claim", json={})
    assert resp.status_code == 426
    assert resp.json()["error"]["message"]["minimum"] == "0.1.0"


def test_current_worker_unaffected_by_gate(client: TestClient):
    wid = str(uuid.uuid4())
    _register(client, wid, version="9.9.9")
    _submit(client)
    with override_settings(MIN_WORKER_VERSION="0.1.0"):
        assert client.post(f"/work/{wid}/claim", json={}) != {}


def test_lease_cap_blocks_hoarding(client: TestClient):
    wid = str(uuid.uuid4())
    _register(client, wid)
    _submit(client, total=10, chunk=1)
    with override_settings(MAX_LEASES_PER_WORKER="2"):
        assert client.post(f"/work/{wid}/claim", json={}).json()["work_unit_id"]
        assert client.post(f"/work/{wid}/claim", json={}).json()["work_unit_id"]
        assert client.post(f"/work/{wid}/claim", json={}).json() == {}  # capped
