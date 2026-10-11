"""Sprint 12: telemetry sample + report shapes."""

from unittest.mock import patch

from worker.gpu_stats import query_gpu
from worker.monitoring import build_report, sample_resources


class FakeState:
    cpu_percent = 13.3
    gpu_percent = 42.0
    gpu_temp_c = 55.5
    gpu_vram_used_mb = 1024.0
    on_battery = None
    idle_seconds = None


def test_build_report_maps_state():
    report = build_report(FakeState())
    assert report == {
        "cpu_percent": 13.3,
        "ram_available_mb": report["ram_available_mb"],  # machine-dependent
        "ram_used_percent": report["ram_used_percent"],
        "gpu_percent": 42.0,
        "gpu_vram_used_mb": 1024,
        "gpu_temp_c": 55.5,
    }
    assert report["ram_available_mb"] > 0


def test_build_report_handles_none_gpu():
    class NoneState(FakeState):
        gpu_percent = None
        gpu_temp_c = None
        gpu_vram_used_mb = None

    report = build_report(NoneState())
    assert report["gpu_percent"] is None
    assert report["gpu_vram_used_mb"] is None
    assert report["gpu_temp_c"] is None


def test_sample_resources_shape(monkeypatch):
    monkeypatch.setattr("worker.monitoring.collect_state", lambda: FakeState())
    sample = sample_resources()
    assert set(sample) == {
        "cpu_percent", "ram_available_mb", "ram_used_percent",
        "gpu_percent", "gpu_vram_used_mb", "gpu_temp_c",
    }
    assert sample["gpu_vram_used_mb"] == 1024


def test_query_gpu_no_nvidia_smi(monkeypatch):
    monkeypatch.setattr("worker.gpu_stats.shutil.which", lambda _name: None)
    assert query_gpu() == {"utilization_gpu": None, "memory_used_mb": None,
                           "temperature_gpu": None}


def test_query_gpu_parses_single_call(monkeypatch):
    class FakeRun:
        returncode = 0
        stdout = "42, 2048, 61\n"

    def fake_run(cmd, **_kwargs):
        assert "--query-gpu=utilization.gpu,memory.used,temperature.gpu" in cmd
        return FakeRun()

    monkeypatch.setattr("worker.gpu_stats.shutil.which", lambda _name: "nvidia-smi")
    monkeypatch.setattr("worker.gpu_stats.subprocess.run", fake_run)
    assert query_gpu() == {"utilization_gpu": 42.0, "memory_used_mb": 2048,
                           "temperature_gpu": 61.0}


def test_report_resources_swallows_errors(monkeypatch):
    import httpx

    def boom(*_a, **_k):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx, "post", boom)
    from worker.monitoring import report_resources

    assert report_resources("http://127.0.0.1:8000", "w1", {"cpu_percent": 1.0}) is None
