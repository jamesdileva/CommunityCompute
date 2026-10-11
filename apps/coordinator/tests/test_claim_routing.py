"""Sprint 9: requirement-aware claim routing (heterogeneous scheduling).

Roadmap exit: CPU-only units flow to every worker; GPU-required units only
to compatible workers.
"""

import uuid

from fastapi.testclient import TestClient

AMD_PROFILE = {
    "schema_version": "1",
    "cpu": {"arch": "AMD64", "logical_cores": 12, "physical_cores": 6},
    "ram": {"total_mb": 16258, "available_mb": 5000},
    "os": {"system": "Windows", "release": "11"},
    "gpus": [{"vendor": "amd", "model": "RX 6400", "vram_mb": 4080}],
    "runtimes": ["hello_compute"],
}

INTEL_PROFILE = {
    "schema_version": "1",
    "cpu": {"arch": "x86_64", "logical_cores": 4, "physical_cores": 2},
    "ram": {"total_mb": 8000, "available_mb": 3000},
    "os": {"system": "Windows", "release": "11"},
    "gpus": [{"vendor": "intel", "model": "Iris Xe", "vram_mb": 2048}],
    "runtimes": ["hello_compute"],
}


def _register(client: TestClient, wid: str) -> None:
    assert client.post(
        "/workers/register",
        json={"worker_id": wid, "worker_version": "t", "hostname": "t"},
    ).status_code == 200


def _report(client: TestClient, wid: str, profile: dict) -> None:
    assert client.post(f"/workers/{wid}/capabilities", json=profile).status_code == 200


def _submit(client: TestClient, requirements: dict, total: int = 1, chunk: int = 1) -> str:
    resp = client.post(
        "/jobs",
        json={"workload_type": "hello_compute", "params": {"op": "sum"},
              "total_units": total, "chunk_size": chunk, "requirements": requirements},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["requirements"] == requirements
    return resp.json()["id"]


def test_cpu_only_job_flows_to_both_workers(client: TestClient):
    wid_a, wid_b = str(uuid.uuid4()), str(uuid.uuid4())
    _register(client, wid_a)
    _register(client, wid_b)
    _report(client, wid_a, AMD_PROFILE)
    _report(client, wid_b, INTEL_PROFILE)
    _submit(client, {"cpu_cores": 2}, total=2, chunk=1)
    a = client.post(f"/work/{wid_a}/claim").json()
    b = client.post(f"/work/{wid_b}/claim").json()
    assert a and b and a["work_unit_id"] != b["work_unit_id"]


def test_gpu_required_job_only_on_amd_worker(client: TestClient):
    wid_a, wid_b = str(uuid.uuid4()), str(uuid.uuid4())
    _register(client, wid_a)
    _register(client, wid_b)
    _report(client, wid_a, AMD_PROFILE)
    _report(client, wid_b, INTEL_PROFILE)
    _submit(client, {"gpu": True, "gpu_vendor": "amd", "min_vram_mb": 3000})
    assert client.post(f"/work/{wid_b}/claim").json() == {}  # Intel: no fit
    a = client.post(f"/work/{wid_a}/claim").json()  # AMD: fits
    assert a["work_unit_id"]


def test_impossible_requirements_starve_everyone(client: TestClient):
    wid = str(uuid.uuid4())
    _register(client, wid)
    _report(client, wid, AMD_PROFILE)
    _submit(client, {"gpu": True, "gpu_vendor": "nvidia", "min_vram_mb": 24000})
    assert client.post(f"/work/{wid}/claim").json() == {}


def test_unrestricted_job_runs_without_profile(client: TestClient):
    """Backwards compat: legacy workers (no capabilities) still get plain jobs."""
    wid = str(uuid.uuid4())
    _register(client, wid)
    _submit(client, {})
    assert client.post(f"/work/{wid}/claim").json()["work_unit_id"]


def test_restricted_job_needs_profile(client: TestClient):
    wid = str(uuid.uuid4())
    _register(client, wid)  # no capabilities reported
    _submit(client, {"cpu_cores": 1})
    assert client.post(f"/work/{wid}/claim").json() == {}


def test_unknown_requirement_key_rejected(client: TestClient):
    resp = client.post(
        "/jobs",
        json={"workload_type": "hello_compute", "total_units": 1, "chunk_size": 1,
              "requirements": {"telepathy": True}},
    )
    assert resp.status_code == 422


def test_os_requirement_routes(client: TestClient):
    wid = str(uuid.uuid4())
    _register(client, wid)
    _report(client, wid, AMD_PROFILE)
    _submit(client, {"os": "Linux"})
    assert client.post(f"/work/{wid}/claim").json() == {}
    _submit(client, {"os": "Windows"})
    assert client.post(f"/work/{wid}/claim").json()["work_unit_id"]


def test_runtime_requirement_routes(client: TestClient):
    wid = str(uuid.uuid4())
    _register(client, wid)
    _report(client, wid, {**AMD_PROFILE, "runtimes": []})
    _submit(client, {"runtime": "hello_compute"})
    assert client.post(f"/work/{wid}/claim").json() == {}
