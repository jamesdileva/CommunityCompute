"""Sprint 34: economics research - the measured cost-per-useful-compute model.

Covers the pure model math (worked examples, monotonicity, unknown handling)
and the DB-backed report (measured inputs from a seeded prototype, empty-DB
behaviour, and the operator endpoint shape).
"""

import uuid

from app.config import get_settings
from app.economics import model
from app.economics.measure import classify_worker
from app.services.workloads import image_generate
from fastapi.testclient import TestClient

GPU_PROFILE = {
    "schema_version": "1",
    "cpu": {"arch": "AMD64", "logical_cores": 12, "physical_cores": 6},
    "ram": {"total_mb": 16258, "available_mb": 5000},
    "os": {"system": "Windows", "release": "11"},
    "gpus": [{"vendor": "amd", "model": "RX 6400", "vram_mb": 4080}],
    "runtimes": ["hello_compute", "image_generate"],
}


# ---- model math ---------------------------------------------------------------

def test_classify_worker_maps_hardware():
    assert classify_worker(None) == "cpu_only"
    assert classify_worker({"gpus": []}) == "cpu_only"
    assert classify_worker({"gpus": [{"vendor": "intel", "vram_mb": 2048}]}) == "igpu"
    assert classify_worker({"gpus": [{"vendor": "amd", "vram_mb": 4080}]}) == "amd_gpu"
    assert classify_worker({"gpus": [{"vendor": "nvidia", "vram_mb": 8192}]}) == "consumer_gpu"
    assert classify_worker({"gpus": [{"vendor": "nvidia", "vram_mb": 16384}]}) == "mid_gpu"
    assert classify_worker({"gpus": [{"vendor": "nvidia", "vram_mb": 49152}]}) == "high_gpu"


def test_hardware_cost_worked_example():
    hw = model.HardwareCost("x", idle_watts=50.0, load_watts=250.0,
                            acquisition_usd=1000.0, life_hours=10_000.0)
    # At full utilization: 250W * $0.20/kWh = $0.05/hr electricity.
    assert round(hw.electricity_per_hour(0.20, 1.0), 6) == 0.05
    # Idle: 50W * $0.20/kWh = $0.01/hr.
    assert round(hw.electricity_per_hour(0.20, 0.0), 6) == 0.01
    assert hw.depreciation_per_hour() == 0.1
    assert round(hw.wall_hour_cost(0.20, 1.0), 6) == 0.15
    # Useful-hour cost divides the wall hour by utilization (you pay the idle time).
    assert round(hw.useful_hour_cost(0.20, 0.5), 6) == round(0.13 / 0.5, 6)


def test_useful_hour_cost_rises_as_utilization_falls():
    hw = model.HardwareCost("x", 50.0, 250.0, 1000.0, 10_000.0)
    high = hw.useful_hour_cost(0.17, 0.9)
    low = hw.useful_hour_cost(0.17, 0.1)
    assert low > high  # idle hardware is expensive per useful hour


def test_cost_for_ms_and_zero_guard():
    # $1.00/hour for 1,800,000 ms (half an hour) = $0.50.
    assert model.cost_for_ms(1.0, 1_800_000.0) == 0.5
    assert model.cost_for_ms(1.0, 0.0) == 0.0
    assert model.cost_for_ms(1.0, None) == 0.0


def test_class_busy_cost_unknown_class_is_safe():
    a = model.default_assumptions(get_settings())
    row = model.class_busy_cost("no_such_class", a, 0.3, 1000.0)
    assert row["known"] is False and row["cost_usd"] == 0.0


def test_default_assumptions_shape():
    a = model.default_assumptions(get_settings())
    assert set(a.hardware) >= {"cpu_only", "igpu", "consumer_gpu", "amd_gpu",
                               "mid_gpu", "high_gpu"}
    assert a.baselines and all("source" in b for b in a.baselines)
    assert any(b["unit"] == "gpu_hour" for b in a.baselines)
    assert any(b["unit"] == "cpu_hour" for b in a.baselines)
    assert 0.0 < a.assumed_utilization <= 1.0


def test_sensitivity_grid_is_monotonic():
    a = model.default_assumptions(get_settings())
    grid = model.sensitivity(a, "consumer_gpu", electricity_prices=(0.10, 0.30),
                             utilizations=(0.10, 0.90))
    assert len(grid) == 4
    by = {(row["electricity_usd_per_kwh"], row["utilization"]): row for row in grid}
    assert by[(0.10, 0.90)]["useful_hour_cost_usd"] < by[(0.30, 0.90)]["useful_hour_cost_usd"]
    assert by[(0.10, 0.90)]["useful_hour_cost_usd"] < by[(0.10, 0.10)]["useful_hour_cost_usd"]
    assert by[(0.10, 0.90)]["cheaper_than_cloud"] is True  # cheap power, high utilization


def test_competitive_ratio_handles_none():
    assert model.competitive_ratio(None, 1.0) is None
    assert model.competitive_ratio(1.0, None) is None
    assert model.competitive_ratio(1.0, 0.0) is None
    assert model.competitive_ratio(0.25, 1.0) == 0.25


# ---- report -------------------------------------------------------------------

def test_report_on_empty_db(client: TestClient):
    resp = client.get("/economics/report")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["measured"]["useful_units"] == 0
    assert body["contributor"]["cost_per_useful_unit_usd"] is None
    assert body["utilization"]["source"] in ("measured", "assumed")
    assert body["centralized"] and body["limitations"]
    assert body["sensitivity"] == []  # no GPU work measured yet
    assert set(body["assumptions"]["hardware"]) >= {"cpu_only", "amd_gpu"}


def _register_and_report(client: TestClient, wid: str) -> None:
    assert client.post("/workers/register", json={
        "worker_id": wid, "worker_version": "t", "hostname": "t"}).status_code == 200
    assert client.post(f"/workers/{wid}/capabilities", json=GPU_PROFILE).status_code == 200


def _run_hello_units(client: TestClient, wid: str, total: int = 2) -> None:
    resp = client.post("/jobs", json={"workload_type": "hello_compute",
                                      "params": {"op": "sum"}, "total_units": total,
                                      "chunk_size": 1})
    assert resp.status_code == 201, resp.text
    for _ in range(total):
        unit = client.post(f"/work/{wid}/claim").json()
        assert unit["work_unit_id"]
        value = (unit["range_start"] + unit["range_end"]) * (
            unit["range_end"] - unit["range_start"] + 1) // 2
        assert client.post(f"/work/{unit['work_unit_id']}/result", json={
            "worker_id": wid, "status": "completed", "value": value,
            "metrics": {"execution_ms": 5.0}}).json()["ok"] is True


def _run_gpu_unit(client: TestClient, wid: str) -> None:
    resp = client.post("/jobs", json={"workload_type": "image_generate",
                                      "params": {"size": 8}, "total_units": 1,
                                      "chunk_size": 1,
                                      "requirements": {"gpu": True, "min_vram_mb": 2048}})
    assert resp.status_code == 201, resp.text
    unit = client.post(f"/work/{wid}/claim").json()
    value = image_generate.compute(unit["range_start"], unit["range_end"], 8, "cc")
    assert client.post(f"/work/{unit['work_unit_id']}/result", json={
        "worker_id": wid, "status": "completed", "value": value,
        "metrics": {"execution_ms": 3.0}}).json()["ok"] is True


def test_report_reflects_measured_work(client: TestClient):
    wid = str(uuid.uuid4())
    _register_and_report(client, wid)
    _run_hello_units(client, wid, total=2)
    _run_gpu_unit(client, wid)

    body = client.get("/economics/report").json()
    m = body["measured"]
    assert m["useful_units"] == 3          # 2 CPU + 1 GPU original verified units
    assert m["results_total"] == 3
    assert m["verification_overhead"] == 1.0
    assert m["gpu_units"] == 1
    assert m["workers_by_class"].get("amd_gpu") == 1
    assert m["busy_ms"] > 0 and m["gpu_time_ms"] > 0
    assert "hello_compute" in m["per_workload"] and "image_generate" in m["per_workload"]

    # The GPU baseline is compared against the local amd_gpu useful-hour cost.
    gpu_rows = [c for c in body["centralized"] if c["unit"] == "gpu_hour"]
    assert gpu_rows and all(r["local_class"] == "amd_gpu" for r in gpu_rows)
    assert gpu_rows[0]["local_useful_hour_usd"] > 0
    assert body["sensitivity"]  # a GPU class ran work, so a grid exists
    assert body["contributor"]["by_class"][0]["class"] == "amd_gpu"
