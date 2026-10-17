"""Synthetic worker population for large-scale simulation (Sprint 32).

A *streaming* generator of lightweight, deterministic fake workers. Nothing is
persisted and nothing is spawned — a "node" here is a few-dozen-byte object
that exists only long enough to feed one scheduling decision, so a million of
them cost seconds and a flat few MB rather than a million DB rows or prcoesses.

Attribute mix mirrors the real prototype fleet plus the long tail the network
would meet at scale (constrained laptops → workstation GPUs), and includes the
Sprint-32 attributes: GPU/VRAM, CPU, RAM, bandwidth, availability, reliability,
location, and a small model cache.

Determinism: one seeded ``random.Random`` drawn sequentially, so the first N
workers of a run are identical no matter which (larger) scale is being measured.
"""

from __future__ import annotations

import random
from collections.abc import Iterator
from dataclasses import dataclass

# Hardware classes: (name, weight, vendor, vram_mb_range, cores_range,
# ram_gb_range, bandwidth_mbps_range, nominal_units_per_min). VRAM 0 == no GPU.
_CLASSES = (
    ("cpu_only", 0.45, "none", (0, 0), (2, 8), (4, 16), (10, 100), 25.0),
    ("igpu", 0.15, "intel", (0, 0), (4, 10), (8, 16), (20, 150), 35.0),
    ("consumer_gpu", 0.22, "nvidia", (4096, 12288), (6, 16), (16, 32), (50, 300), 90.0),
    ("amd_gpu", 0.08, "amd", (4096, 16384), (6, 16), (16, 32), (50, 400), 80.0),
    ("mid_gpu", 0.07, "nvidia", (12288, 24576), (8, 24), (32, 64), (100, 1000), 220.0),
    ("high_gpu", 0.03, "nvidia", (24576, 49152), (16, 64), (64, 128), (500, 10000), 600.0),
)

_LOCATIONS = (("na", 0.40), ("eu", 0.30), ("apac", 0.22), ("sa", 0.08))
_CACHEABLE_MODELS = ("llama3-8b", "sdxl", "whisper-large")


@dataclass(slots=True)
class SimulatedWorker:
    """One simulated node (lightweight: ``__slots__`` dataclass)."""

    id: str
    klass: str
    gpu_vendor: str
    vram_mb: int
    cores: int
    ram_mb: int
    bandwidth_mbps: float
    availability: float  # 0..1 fraction of wall-clock this node is online
    reliability: float   # 0..1 smoothed success rate (reputation-like)
    location: str
    cached: tuple[str, ...]
    units_per_min: float

    # --- shapes the real scheduler consumes ---------------------------------

    def profile(self) -> dict:
        """Capability-profile dict accepted by ``compat.check`` / ``scoring``."""
        gpus = [] if self.vram_mb <= 0 else [
            {"vendor": self.gpu_vendor, "model": self.gpu_vendor, "vram_mb": self.vram_mb}
        ]
        return {
            "cpu": {"logical_cores": self.cores, "physical_cores": self.cores},
            "ram": {"total_mb": self.ram_mb},
            "os": {"system": "Windows"},
            "gpus": gpus,
            "cached_models": [{"name": m} for m in self.cached],
            "location": self.location,
        }

    def score_context(self) -> dict:
        """Context dict accepted by ``scoring.score_with_context``."""
        return {
            "profile": self.profile(),
            "reliability": self.reliability,
            "mean_execution_ms": max(1.0, 60000.0 / self.units_per_min),
            "cpu_percent": 0.0,
            "gpu_percent": 0.0,
            "active_leases": 0,
            "max_leases": 1,
            "reported_cached_models": set(self.cached),
        }

    def is_online(self) -> bool:
        return self.availability >= 0.5


def _pick(rng: random.Random, weighted: tuple) -> tuple:
    roll = rng.random()
    acc = 0.0
    for item in weighted:
        acc += item[-1] if len(item) == 2 else item[1]
        if roll <= acc:
            return item
    return weighted[-1]


def make_workers(scale: int, *, seed: int = 32) -> Iterator[SimulatedWorker]:
    """Yield ``scale`` deterministic simulated workers, one at a time (O(1) memory)."""
    rng = random.Random(seed)
    for index in range(scale):
        name, _w, vendor, vram, cores, ram, bw, rate = _pick(rng, _CLASSES)
        vram_mb = rng.randrange(vram[0], vram[1] + 1) if vram[1] else 0
        cached: tuple[str, ...] = ()
        if rng.random() < 0.4:
            cached = (rng.choice(_CACHEABLE_MODELS),)
        yield SimulatedWorker(
            id=f"sim-{index:07d}",
            klass=name,
            gpu_vendor=vendor,
            vram_mb=vram_mb,
            cores=rng.randrange(cores[0], cores[1] + 1),
            ram_mb=rng.randrange(ram[0], ram[1] + 1) * 1024,
            bandwidth_mbps=round(rng.uniform(bw[0], bw[1]), 1),
            availability=round(rng.uniform(0.1, 1.0), 3),
            reliability=round(rng.uniform(0.3, 0.99), 3),
            location=_pick(rng, _LOCATIONS)[0],
            cached=cached,
            units_per_min=rate,
        )
