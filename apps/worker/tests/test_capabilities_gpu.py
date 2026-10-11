"""Sprint 3: GPU provider registry behavior (mocked subprocess, no real GPU needed)."""

from unittest.mock import patch

from worker.capabilities.gpu.base import GPUProvider
from worker.capabilities.gpu.nvidia import NvidiaProvider
from worker.capabilities.gpu.registry import detect_gpus
from worker.capabilities.gpu.unknown import UnknownProvider
from worker.capabilities.gpu.wmi import WindowsVideoControllerProvider
from worker.capabilities.schema import GPUInfo


class _FakeProvider(GPUProvider):
    def __init__(self, name: str, available: bool, gpus: list[GPUInfo] | None = None,
                 boom: bool = False):
        self.name = name
        self._available = available
        self._gpus = gpus or []
        self._boom = boom

    def available(self) -> bool:
        return self._available

    def detect(self) -> list[GPUInfo]:
        if self._boom:
            raise RuntimeError("provider exploded")
        return list(self._gpus)


def test_registry_dedupes_same_model_across_providers():
    gpu = GPUInfo(vendor="amd", model="RX 6400", vram_mb=4080)
    gpus = detect_gpus([
        _FakeProvider("a", True, [gpu]),
        _FakeProvider("b", True, [GPUInfo(vendor="unknown", model="rx 6400")]),
    ])
    assert len(gpus) == 1
    assert gpus[0].vendor == "amd"  # first provider wins


def test_registry_skips_unavailable_and_falls_back_to_unknown():
    gpus = detect_gpus([_FakeProvider("a", False), _FakeProvider("b", False)])
    assert len(gpus) == 1
    assert gpus[0].source == "UnknownProvider"


def test_registry_survives_exploding_provider():
    gpus = detect_gpus([_FakeProvider("bad", True, boom=True)])
    assert len(gpus) == 1
    assert gpus[0].source == "UnknownProvider"


def test_registry_picks_first_available_provider():
    good = GPUInfo(vendor="intel", model="Iris Xe")
    gpus = detect_gpus([_FakeProvider("a", False), _FakeProvider("b", True, [good])])
    assert [g.model for g in gpus] == ["Iris Xe"]


def test_nvidia_provider_parses_csv():
    csv = "NVIDIA GeForce RTX 3060, 12288, 546.29, 17\n"
    provider = NvidiaProvider()
    with patch.object(provider, "available", return_value=True), patch(
        "worker.capabilities.gpu.nvidia.subprocess.run"
    ) as run:
        run.return_value = type("R", (), {"returncode": 0, "stdout": csv})()
        gpus = provider.detect()
    assert len(gpus) == 1
    assert gpus[0].vendor == "nvidia"
    assert gpus[0].vram_mb == 12288
    assert gpus[0].utilization_percent == 17.0
    assert gpus[0].source == "nvidia-smi"


def test_nvidia_provider_returns_empty_on_error():
    provider = NvidiaProvider()
    with patch.object(provider, "available", return_value=True), patch(
        "worker.capabilities.gpu.nvidia.subprocess.run"
    ) as run:
        run.return_value = type("R", (), {"returncode": 1, "stdout": ""})()
        assert provider.detect() == []


def test_nvidia_provider_not_available_without_smi():
    with patch("worker.capabilities.gpu.nvidia.shutil.which", return_value=None):
        assert NvidiaProvider().available() is False


def test_wmi_provider_maps_vendor_and_vram():
    payload = '[{"Name": "Intel(R) Iris(R) Xe Graphics", "AdapterRAM": 2147483648, "DriverVersion": "31.0.101.1"}]'
    provider = WindowsVideoControllerProvider()
    with patch.object(provider, "available", return_value=True), patch(
        "worker.capabilities.gpu.wmi.subprocess_run_powershell", return_value=payload
    ):
        gpus = provider.detect()
    assert len(gpus) == 1
    assert gpus[0].vendor == "intel"
    assert gpus[0].vram_mb == 2048
    assert gpus[0].source == "Win32_VideoController"


def test_unknown_provider_always_yields_record():
    gpus = UnknownProvider().detect()
    assert len(gpus) == 1
    assert gpus[0].vendor == "unknown"
    assert gpus[0].model == "undetected"
