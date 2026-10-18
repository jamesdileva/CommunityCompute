"""Sprint 33: multi-workload network.

Roadmap exit: different hardware classes simultaneously process different
workload types through one shared scheduler. These tests exercise the first
GPU-gated workload (image_generate) alongside the CPU workloads, proving:
- the new type is allowlisted, verified, and reproduces exact values;
- a GPU-required job only routes to GPU-capable workers;
- a GPU worker and a CPU-only worker claim different workload types at the
  same time, with both jobs running concurrently.
"""

import uuid

from app.services.workloads import image_generate
from fastapi.testclient import TestClient

# GPU class (matches the prototype PC) and a CPU-only class (the laptop).
GPU_PROFILE = {
    "schema_version": "1",
    "cpu": {"arch": "AMD64", "logical_cores": 12, "physical_cores": 6},
    "ram": {"total_mb": 16258, "available_mb": 5000},
    "os": {"system": "Windows", "release": "11"},
    "gpus": [{"vendor": "amd", "model": "RX 6400", "vram_mb": 4080}],
    "runtimes": ["image_generate", "hello_compute"],
}

CPU_ONLY_PROFILE = {
    "schema_version": "1",
    "cpu": {"arch": "x86_64", "logical_cores": 4, "physical_cores": 2},
    "ram": {"total_mb": 8000, "available_mb": 3000},
    "os": {"system": "Windows", "release": "11"},
    "gpus": [],
    "runtimes": ["hello_compute", "stats_range", "embeddings"],
}

GPU_REQ = {"gpu": True, "min_vram_mb": 2048}


def _register(client: TestClient, wid: str) -> None:
    assert client.post(
        "/workers/register",
        json={"worker_id": wid, "worker_version": "t", "hostname": "t"},
    ).status_code == 200


def _report(client: TestClient, wid: str, profile: dict) -> None:
    assert client.post(f"/workers/{wid}/capabilities", json=profile).status_code == 200


def _submit(client: TestClient, workload_type: str, requirements: dict,
            params: dict | None = None, total: int = 2, chunk: int = 1) -> str:
    resp = client.post(
        "/jobs",
        json={"workload_type": workload_type, "params": params or {},
              "total_units": total, "chunk_size": chunk, "requirements": requirements},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _result(unit: dict, value) -> dict:
    return {"worker_id": unit["worker_id"], "status": "completed", "value": value,
            "metrics": {"execution_ms": 1.0}}


def test_image_generate_is_allowlisted(client: TestClient):
    from app.services.workloads import KNOWN_WORKLOAD_TYPES

    assert "image_generate" in KNOWN_WORKLOAD_TYPES


def test_image_generate_roundtrip_on_gpu_worker(client: TestClient):
    wid = str(uuid.uuid4())
    _register(client, wid)
    _report(client, wid, GPU_PROFILE)
    _submit(client, "image_generate", GPU_REQ, params={"size": 16})
    unit = client.post(f"/work/{wid}/claim").json()
    unit["worker_id"] = wid
    assert unit["workload_type"] == "image_generate"
    expected = image_generate.compute(unit["range_start"], unit["range_end"], 16, "cc")
    resp = client.post(f"/work/{unit['work_unit_id']}/result", json=_result(unit, expected))
    assert resp.status_code == 200, resp.text
    assert resp.json()["ok"] is True


def test_image_generate_wrong_value_rejected(client: TestClient):
    wid = str(uuid.uuid4())
    _register(client, wid)
    _report(client, wid, GPU_PROFILE)
    _submit(client, "image_generate", GPU_REQ, params={"size": 16})
    unit = client.post(f"/work/{wid}/claim").json()
    unit["worker_id"] = wid
    bad = {"size": 16, "tiles": 1, "checksum": "deadbeef"}
    resp = client.post(f"/work/{unit['work_unit_id']}/result", json=_result(unit, bad))
    assert resp.status_code == 422
    assert resp.json()["error"]["message"]["failure_kind"] == "value_mismatch"


def test_cpu_only_worker_excluded_from_gpu_job(client: TestClient):
    cpu = str(uuid.uuid4())
    _register(client, cpu)
    _report(client, cpu, CPU_ONLY_PROFILE)
    _submit(client, "image_generate", GPU_REQ)
    assert client.post(f"/work/{cpu}/claim").json() == {}


def test_mixed_classes_claim_different_workloads_concurrently(client: TestClient):
    gpu, cpu = str(uuid.uuid4()), str(uuid.uuid4())
    _register(client, gpu)
    _register(client, cpu)
    _report(client, gpu, GPU_PROFILE)
    _report(client, cpu, CPU_ONLY_PROFILE)

    # Only the GPU class qualifies for the GPU-gated job.
    gpu_job = _submit(client, "image_generate", GPU_REQ, params={"size": 8})
    assert client.post(f"/work/{cpu}/claim").json() == {}  # CPU class excluded
    gpu_unit = client.post(f"/work/{gpu}/claim").json()
    assert gpu_unit["workload_type"] == "image_generate"
    assert gpu_unit["job_id"] == gpu_job

    # A CPU job submitted afterwards is claimed by the CPU class, so the one
    # scheduler now has two different workload types in flight at once.
    cpu_job = _submit(client, "hello_compute", {}, params={"op": "sum"})
    cpu_unit = client.post(f"/work/{cpu}/claim").json()
    assert cpu_unit["workload_type"] == "hello_compute"
    assert cpu_unit["job_id"] == cpu_job

    assert client.get(f"/jobs/{gpu_job}").json()["status"] == "running"
    assert client.get(f"/jobs/{cpu_job}").json()["status"] == "running"

    # Finish both correctly.
    gpu_unit["worker_id"] = gpu
    expected = image_generate.compute(gpu_unit["range_start"], gpu_unit["range_end"], 8, "cc")
    assert client.post(f"/work/{gpu_unit['work_unit_id']}/result",
                       json=_result(gpu_unit, expected)).json()["ok"] is True
    cpu_unit["worker_id"] = cpu
    assert client.post(f"/work/{cpu_unit['work_unit_id']}/result",
                       json=_result(cpu_unit, 1)).json()["ok"] is True


def test_unlisted_workload_type_still_rejected(client: TestClient):
    resp = client.post(
        "/jobs",
        json={"workload_type": "gpu_inference", "total_units": 1, "chunk_size": 1},
    )
    assert resp.status_code == 422
