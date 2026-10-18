"""Cost-per-useful-compute model (Sprint 34).

Pure, deterministic math — no database, no settings import. Every function
takes its inputs explicitly so the model can be unit-tested with worked
examples and reused by the report builder and the CLI.

Two ideas keep this honest (roadmap: "no assumptions about profitability
should survive this sprint without data"):

1. **Measured vs assumed are separate types.** `HardwareCost` and
   `CostAssumptions` are *assumptions*; the measured quantities live in
   `measure.Measurement`. The report never mixes them silently.
2. **Cost per *useful* hour, not per load hour.** A contributor pays for
   electricity and depreciation whether or not the machine is busy, so the
   honest denominator is utilization: `useful_hour_cost = wall_hour_cost / u`.
   That is the term that decides whether idle consumer hardware ever competes
   with a cloud GPU billed only while running.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

MS_PER_HOUR = 3_600_000.0

# Default cost assumptions, per hardware class. These are *assumptions* (see
# docs/economics.md for the reasoning and sources); they are deliberately easy
# to override so the model can be re-run with measured power/price data.
#
# watts: idle (desktop on, nothing leased) and load (one saturated workload).
# acquisition_usd: whole-machine purchase price, not just the GPU.
# life_hours: useful life in powered-on wall-clock hours.
_DEFAULT_HARDWARE = (
    ("cpu_only", 35.0, 90.0, 600.0, 43_800.0),
    ("igpu", 40.0, 110.0, 800.0, 43_800.0),
    ("consumer_gpu", 70.0, 300.0, 1200.0, 35_040.0),
    ("amd_gpu", 60.0, 250.0, 900.0, 35_040.0),
    ("mid_gpu", 90.0, 450.0, 2500.0, 35_040.0),
    ("high_gpu", 120.0, 700.0, 12000.0, 43_800.0),
)

# Cited on-demand list prices for centralized compute. Public list prices move;
# these were captured on the collection date and must be re-checked before any
# number here is quoted. Each entry carries its own `source` string.
_DEFAULT_BASELINES = (
    {
        "name": "cloud GPU (T4-class, on-demand)",
        "usd_per_hour": 0.53,
        "unit": "gpu_hour",
        "source": "AWS g4dn.xlarge on-demand list, captured 2026-10-17",
    },
    {
        "name": "cloud GPU (A100-class, on-demand)",
        "usd_per_hour": 3.06,
        "unit": "gpu_hour",
        "source": "AWS p3.2xlarge on-demand list, captured 2026-10-17",
    },
    {
        "name": "cloud CPU (vCPU-hour, on-demand)",
        "usd_per_hour": 0.032,
        "unit": "cpu_hour",
        "source": "GCP n1 vCPU on-demand list, captured 2026-10-17",
    },
)


@dataclass(frozen=True)
class HardwareCost:
    """Assumed cost profile for one hardware class."""

    name: str
    idle_watts: float
    load_watts: float
    acquisition_usd: float
    life_hours: float

    def electricity_per_hour(self, usd_per_kwh: float, utilization: float) -> float:
        """Electricity cost of one wall-clock hour at a given utilization."""
        u = _clamp(utilization)
        watts = self.idle_watts + (self.load_watts - self.idle_watts) * u
        return watts / 1000.0 * usd_per_kwh

    def depreciation_per_hour(self) -> float:
        return self.acquisition_usd / self.life_hours if self.life_hours > 0 else 0.0

    def wall_hour_cost(self, usd_per_kwh: float, utilization: float) -> float:
        """Total cost of one *wall* hour (electricity + depreciation)."""
        return self.electricity_per_hour(usd_per_kwh, utilization) + self.depreciation_per_hour()

    def useful_hour_cost(self, usd_per_kwh: float, utilization: float) -> float:
        """Cost of one *useful* hour: you pay the wall hour, you only bill u of it."""
        return self.wall_hour_cost(usd_per_kwh, utilization) / max(_clamp(utilization), 0.01)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class CostAssumptions:
    electricity_usd_per_kwh: float
    bandwidth_usd_per_gb: float
    transfer_mb_per_unit: float
    infra_usd_per_month: float
    assumed_utilization: float
    hardware: dict[str, HardwareCost]
    baselines: tuple[dict, ...]

    def with_overrides(self, **overrides) -> CostAssumptions:
        """Return a copy with selected scalar fields replaced (CLI/report)."""
        data = {
            "electricity_usd_per_kwh": self.electricity_usd_per_kwh,
            "bandwidth_usd_per_gb": self.bandwidth_usd_per_gb,
            "transfer_mb_per_unit": self.transfer_mb_per_unit,
            "infra_usd_per_month": self.infra_usd_per_month,
            "assumed_utilization": self.assumed_utilization,
            "hardware": self.hardware,
            "baselines": self.baselines,
        }
        data.update({k: v for k, v in overrides.items() if v is not None})
        return CostAssumptions(**data)

    def to_dict(self) -> dict:
        return {
            "electricity_usd_per_kwh": self.electricity_usd_per_kwh,
            "bandwidth_usd_per_gb": self.bandwidth_usd_per_gb,
            "transfer_mb_per_unit": self.transfer_mb_per_unit,
            "infra_usd_per_month": self.infra_usd_per_month,
            "assumed_utilization": self.assumed_utilization,
            "hardware": {k: v.to_dict() for k, v in self.hardware.items()},
            "baselines": list(self.baselines),
        }


def default_assumptions(settings) -> CostAssumptions:
    """Build the assumption set from settings (JSON overrides allowed).

    Settings expose scalars directly and two optional JSON strings
    (`economics_hardware_classes`, `economics_cloud_baselines`) so an operator
    can substitute measured power/price data without a code change.
    """
    hardware = {name: HardwareCost(name, i, w, price, life)
                for name, i, w, price, life in _DEFAULT_HARDWARE}
    if getattr(settings, "economics_hardware_classes", ""):
        for name, row in json.loads(settings.economics_hardware_classes).items():
            hardware[name] = HardwareCost(
                name=name,
                idle_watts=float(row["idle_watts"]),
                load_watts=float(row["load_watts"]),
                acquisition_usd=float(row["acquisition_usd"]),
                life_hours=float(row["life_hours"]),
            )
    baselines = _DEFAULT_BASELINES
    if getattr(settings, "economics_cloud_baselines", ""):
        baselines = tuple(json.loads(settings.economics_cloud_baselines))
    return CostAssumptions(
        electricity_usd_per_kwh=settings.economics_electricity_usd_per_kwh,
        bandwidth_usd_per_gb=settings.economics_bandwidth_usd_per_gb,
        transfer_mb_per_unit=settings.economics_transfer_mb_per_unit,
        infra_usd_per_month=settings.economics_infra_usd_per_month,
        assumed_utilization=settings.economics_assumed_utilization,
        hardware=hardware,
        baselines=baselines,
    )


def cost_for_ms(useful_hour_cost: float, ms: float | None) -> float:
    """Cost of `ms` milliseconds of useful machine time."""
    if not ms or ms <= 0:
        return 0.0
    return useful_hour_cost * ms / MS_PER_HOUR


def class_busy_cost(klass: str, assumptions: CostAssumptions, utilization: float,
                    busy_ms: float) -> dict:
    """Contributor cost to run `busy_ms` on a machine of class `klass`."""
    hw = assumptions.hardware.get(klass)
    if hw is None:
        return {"class": klass, "known": False, "cost_usd": 0.0}
    useful_hourly = hw.useful_hour_cost(assumptions.electricity_usd_per_kwh, utilization)
    return {
        "class": klass,
        "known": True,
        "useful_hour_cost_usd": round(useful_hourly, 6),
        "wall_hour_cost_usd": round(hw.wall_hour_cost(assumptions.electricity_usd_per_kwh,
                                                      utilization), 6),
        "electricity_per_hour_usd": round(hw.electricity_per_hour(
            assumptions.electricity_usd_per_kwh, utilization), 6),
        "depreciation_per_hour_usd": round(hw.depreciation_per_hour(), 6),
        "busy_ms": round(busy_ms, 3),
        "cost_usd": round(cost_for_ms(useful_hourly, busy_ms), 9),
    }


def bandwidth_cost_per_unit(assumptions: CostAssumptions) -> float:
    return assumptions.transfer_mb_per_unit / 1024.0 * assumptions.bandwidth_usd_per_gb


def network_cost_per_unit(assumptions: CostAssumptions, monthly_useful_units: float | None) -> float | None:
    """Amortize monthly infrastructure cost across measured monthly volume."""
    if not monthly_useful_units or monthly_useful_units <= 0:
        return None
    return assumptions.infra_usd_per_month / monthly_useful_units


def centralized_cost(hours: float | None, usd_per_hour: float) -> float:
    if not hours or hours <= 0:
        return 0.0
    return hours * usd_per_hour


def competitive_ratio(local_usd: float | None, centralized_usd: float | None) -> float | None:
    """local/centralized. <1 means the community network is cheaper."""
    if local_usd is None or centralized_usd is None or centralized_usd <= 0:
        return None
    return local_usd / centralized_usd


def sensitivity(assumptions: CostAssumptions, klass: str,
                electricity_prices: tuple[float, ...] = (0.05, 0.10, 0.17, 0.30),
                utilizations: tuple[float, ...] = (0.10, 0.25, 0.50, 0.90)) -> list[dict]:
    """Break-even grid: useful-hour cost vs cloud GPU price across price/utilization."""
    hw = assumptions.hardware.get(klass)
    if hw is None:
        return []
    cloud = assumptions.baselines[0]["usd_per_hour"] if assumptions.baselines else None
    grid = []
    for price in electricity_prices:
        for u in utilizations:
            useful = hw.useful_hour_cost(price, u)
            grid.append({
                "class": klass,
                "electricity_usd_per_kwh": price,
                "utilization": u,
                "useful_hour_cost_usd": round(useful, 4),
                "cloud_gpu_usd_per_hour": cloud,
                "ratio_to_cloud": round(useful / cloud, 3) if cloud else None,
                "cheaper_than_cloud": (cloud is not None and useful < cloud),
            })
    return grid


def _clamp(value: float) -> float:
    return min(max(value, 0.0), 1.0)
