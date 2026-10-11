"""Sprint 3: capability persistence + retrieval via API."""

import uuid

from fastapi.testclient import TestClient

PROFILE = {
    "schema_version": "1",
    "cpu": {
        "arch": "AMD64",
        "processor": "AMD64 Family 25",
        "logical_cores": 12,
        "physical_cores": 6,
        "freq_mhz": 3600.0,
    },
    "ram": {"total_mb": 16258, "available_mb": 5000},
    "os": {"system": "Windows", "release": "11", "version": "10.0.26300"},
    "gpus": [
        {
            "vendor": "amd",
            "model": "AMD Radeon RX 6400",
            "vram_mb": 4080,
            "driver": "32.0.21045.5002",
            "utilization_percent": None,
            "source": "Win32_VideoController",
        }
    ],
}


def _register(client: TestClient, wid: str | None = None) -> str:
    wid = wid or str(uuid.uuid4())
    resp = client.post(
        "/workers/register",
        json={"worker_id": wid, "worker_version": "0.1.0-sprint3", "hostname": "PC-X"},
    )
    assert resp.status_code == 200
    return wid


def test_report_capabilities_ok(client: TestClient):
    wid = _register(client)
    resp = client.post(f"/workers/{wid}/capabilities", json=PROFILE)
    assert resp.status_code == 200
    assert resp.json()["gpus"][0]["model"] == "AMD Radeon RX 6400"

    cap = client.get(f"/workers/{wid}").json()["capabilities"]
    assert cap is not None
    assert cap["cpu"]["logical_cores"] == 12
    assert cap["gpus"][0]["vram_mb"] == 4080


def test_report_capabilities_upserts(client: TestClient):
    wid = _register(client)
    assert client.post(f"/workers/{wid}/capabilities", json=PROFILE).status_code == 200
    updated = {**PROFILE, "cpu": {**PROFILE["cpu"], "logical_cores": 8}}
    assert client.post(f"/workers/{wid}/capabilities", json=updated).status_code == 200
    assert client.get(f"/workers/{wid}").json()["capabilities"]["cpu"]["logical_cores"] == 8


def test_report_capabilities_unknown_worker_404(client: TestClient):
    resp = client.post(f"/workers/{str(uuid.uuid4())}/capabilities", json=PROFILE)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == 404


def test_report_capabilities_rejects_extra_fields(client: TestClient):
    wid = _register(client)
    bad = {**PROFILE, "mystery": 42}
    assert client.post(f"/workers/{wid}/capabilities", json=bad).status_code == 422


def test_list_workers_shows_different_profiles(client: TestClient):
    wid_a = _register(client, str(uuid.uuid4()))
    wid_b = _register(client, str(uuid.uuid4()))
    client.post(f"/workers/{wid_a}/capabilities", json=PROFILE)
    # PC-B style profile: Intel Iris Xe, weaker CPU
    intel = {
        **PROFILE,
        "cpu": {**PROFILE["cpu"], "physical_cores": 2},
        "gpus": [{**PROFILE["gpus"][0], "vendor": "intel",
                  "model": "Intel(R) Iris(R) Xe Graphics", "vram_mb": 2048,
                  "driver": "31.0.101.1"}],
    }
    client.post(f"/workers/{wid_b}/capabilities", json=intel)

    rows = {w["id"]: w for w in client.get("/workers").json()}
    assert rows[wid_a]["capabilities"]["gpus"][0]["vendor"] == "amd"
    assert rows[wid_b]["capabilities"]["gpus"][0]["vendor"] == "intel"


def test_list_workers_capabilities_none_before_report(client: TestClient):
    wid = _register(client)
    rows = {w["id"]: w for w in client.get("/workers").json()}
    assert rows[wid]["capabilities"] is None
