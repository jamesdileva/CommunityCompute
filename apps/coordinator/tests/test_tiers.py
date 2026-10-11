"""Sprint 10: hardware tier normalization per resource axis."""

from app.services.tiers import cpu_tier, gpu_tier, hardware_tiers, ram_tier

PROFILE = {
    "cpu": {"logical_cores": 12, "physical_cores": 6},
    "ram": {"total_mb": 16258},
    "gpus": [{"vendor": "amd", "model": "RX 6400", "vram_mb": 4080}],
}


def test_gpu_vram_bands():
    assert gpu_tier({"vram_mb": 2048, "vendor": "nvidia"}) == "H1"  # <4GB
    assert gpu_tier({"vram_mb": 4096, "vendor": "nvidia"}) == "H1"  # exactly 4GB is H1 floor
    assert gpu_tier({"vram_mb": 4097, "vendor": "nvidia"}) == "H2"
    assert gpu_tier({"vram_mb": 12288, "vendor": "nvidia"}) == "H2"  # 12GB boundary
    assert gpu_tier({"vram_mb": 12289, "vendor": "nvidia"}) == "H3"


def test_gpu_integrated_or_unknown_is_h1():
    assert gpu_tier({"vendor": "intel", "model": "Iris Xe", "vram_mb": None}) == "H1"
    assert gpu_tier({"vendor": "unknown", "model": "undetected", "vram_mb": None}) == "H1"


def test_no_gpu_is_none_not_unknown():
    assert gpu_tier(None) is None
    assert gpu_tier({}) is None


def test_cpu_core_bands():
    assert cpu_tier({"physical_cores": 4}) == "H1"
    assert cpu_tier({"physical_cores": 6}) == "H2"
    assert cpu_tier({"physical_cores": 8}) == "H2"
    assert cpu_tier({"physical_cores": 10}) == "H3"


def test_cpu_falls_back_to_logical_cores():
    assert cpu_tier({"logical_cores": 16}) == "H3"


def test_ram_bands():
    assert ram_tier({"total_mb": 8 * 1024}) == "H1"
    assert ram_tier({"total_mb": 16 * 1024}) == "H2"
    assert ram_tier({"total_mb": 64 * 1024}) == "H3"


def test_hardware_tiers_picks_best_gpu():
    tiers = hardware_tiers({
        "cpu": {"physical_cores": 12},
        "ram": {"total_mb": 32 * 1024},
        "gpus": [{"vendor": "intel", "model": "Iris Xe", "vram_mb": None},
                 {"vendor": "nvidia", "model": "RTX 4090", "vram_mb": 24576}],
    })
    assert tiers == {"gpu": "H3", "cpu": "H3", "ram": "H2"}


def test_hardware_tiers_empty_profile():
    # No profile axes reported at all -> no tiers (same as no profile).
    assert hardware_tiers(None) == {}
    assert hardware_tiers({}) == {}


def test_hardware_tiers_partial_profile_marks_missing_axes():
    tiers = hardware_tiers({"gpus": [{"vendor": "amd", "vram_mb": 8192}]})
    assert tiers == {"gpu": "H2", "cpu": "unknown", "ram": "unknown"}


def test_physical_profile_matches_prototype_machines():
    # This PC: RX 6400 (4GB → H1 floor), 6 physical cores, 16GB RAM
    assert hardware_tiers(PROFILE) == {"gpu": "H1", "cpu": "H2", "ram": "H2"}
    # Iris Xe laptop-class: integrated GPU, 2 cores, 8GB
    laptop = {
        "cpu": {"physical_cores": 2},
        "ram": {"total_mb": 8192},
        "gpus": [{"vendor": "intel", "model": "Iris Xe", "vram_mb": None}],
    }
    assert hardware_tiers(laptop) == {"gpu": "H1", "cpu": "H1", "ram": "H1"}
