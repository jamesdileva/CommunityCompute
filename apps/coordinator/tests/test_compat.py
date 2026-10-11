"""Sprint 9: compatibility matrix (requirements x capability profile)."""

from app.services.compat import check

PROFILE = {
    "cpu": {"arch": "AMD64", "logical_cores": 12, "physical_cores": 6},
    "ram": {"total_mb": 16258, "available_mb": 5000},
    "os": {"system": "Windows", "release": "11"},
    "gpus": [{"vendor": "amd", "model": "RX 6400", "vram_mb": 4080}],
    "runtimes": ["hello_compute"],
}


def test_empty_requirements_run_anywhere():
    assert check({}, PROFILE)[0] is True
    assert check({}, None)[0] is True  # unrestricted jobs fit legacy workers too
    assert check(None, None)[0] is True


def test_requirements_without_profile_rejected():
    ok, reason = check({"cpu_cores": 1}, None)
    assert ok is False
    assert "no capabilities" in reason


def test_cpu_match_and_shortfall():
    assert check({"cpu_cores": 8}, PROFILE)[0] is True
    ok, reason = check({"cpu_cores": 64}, PROFILE)
    assert ok is False
    assert "cpu_cores" in reason


def test_ram_match_and_shortfall():
    assert check({"ram_mb": 2048}, PROFILE)[0] is True
    ok, reason = check({"ram_mb": 10**9}, PROFILE)
    assert ok is False
    assert "ram_mb" in reason


def test_os_match_case_insensitive_and_mismatch():
    assert check({"os": "windows"}, PROFILE)[0] is True
    ok, reason = check({"os": "Linux"}, PROFILE)
    assert ok is False
    assert "os" in reason


def test_runtime_advertised_and_missing():
    assert check({"runtime": "hello_compute"}, PROFILE)[0] is True
    ok, reason = check({"runtime": "cuda_beast"}, PROFILE)
    assert ok is False
    assert "runtime" in reason


def test_gpu_required_present():
    ok, reason = check({"gpu": True}, PROFILE)
    assert ok is True, reason


def test_gpu_vendor_match_and_mismatch():
    assert check({"gpu": True, "gpu_vendor": "amd"}, PROFILE)[0] is True
    assert check({"gpu": True, "gpu_vendor": "AMD"}, PROFILE)[0] is True
    ok, reason = check({"gpu": True, "gpu_vendor": "nvidia"}, PROFILE)
    assert ok is False
    assert "compatible gpu" in reason


def test_gpu_vram_match_and_shortfall():
    assert check({"gpu": True, "min_vram_mb": 3000}, PROFILE)[0] is True
    ok, reason = check({"gpu": True, "min_vram_mb": 8000}, PROFILE)
    assert ok is False
    assert "compatible gpu" in reason


def test_gpu_required_but_worker_has_none():
    bare = {**PROFILE, "gpus": []}
    ok, reason = check({"gpu": True}, bare)
    assert ok is False
    assert "compatible gpu" in reason


def test_cpu_only_job_fits_gpu_machine():
    # gpu:false means "no GPU needed" — runs anywhere, no scoring yet (S31).
    assert check({"gpu": False, "cpu_cores": 2}, PROFILE)[0] is True


def test_odd_shapes_reject_not_crash():
    assert check({"cpu_cores": 2}, {})[0] is False
    assert check({"gpu": True}, {"gpus": None})[0] is False
    assert check({"os": "Windows"}, {"os": {}})[0] is False
