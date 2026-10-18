"""Economics report (Sprint 34): measured inputs + assumptions -> one document.

`build_report` is pure composition: it takes a `Measurement` (measured),
a `CostAssumptions` (assumed), and produces a JSON-serializable dict that
states the cost-per-useful-compute model, a centralized comparison, a
break-even sensitivity grid, and an explicit list of what is *not* yet known.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.economics import model
from app.economics.measure import Measurement, measure

LIMITATIONS = (
    ("Workload execution times are from deterministic prototype stubs "
     "(hello_compute/stats_range/embeddings/image_generate), NOT real AI "
     "compute, so absolute per-unit costs are illustrative, not quotable."),
    ("Electricity price, hardware power/price/life, bandwidth, infrastructure, "
     "and centralized list prices are ASSUMPTIONS (see docs/economics.md), not "
     "measurements; only execution time, uptime, overhead, and volume are measured."),
    ("Utilization and availability are measured over a short prototype window "
     "with one GPU machine; a large fleet's utilization is unknown."),
    ("There is no customer willingness-to-pay data: credits are non-cash and "
     "priced 1:1 with useful units by construction (Sprint 28)."),
)


def build_report(db: Session, settings=None, *, measurement: Measurement | None = None,
                 assumptions: model.CostAssumptions | None = None,
                 **overrides) -> dict:
    settings = settings or get_settings()
    m = measurement if measurement is not None else measure(db, settings)
    base = assumptions if assumptions is not None else model.default_assumptions(settings)
    a = base.with_overrides(**overrides)

    utilization = m.utilization if m.utilization is not None else a.assumed_utilization
    utilization_source = "measured" if m.utilization is not None else "assumed"

    by_class = []
    contributor_total = 0.0
    for klass, busy_ms in sorted(m.busy_ms_by_class.items(), key=lambda kv: -kv[1]):
        row = model.class_busy_cost(klass, a, utilization, busy_ms)
        by_class.append(row)
        contributor_total += row["cost_usd"]

    useful_units = m.useful_units
    contributor_per_unit = (contributor_total / useful_units) if useful_units else None
    execution_hours = m.busy_ms / model.MS_PER_HOUR
    blended_useful_hour = (contributor_total / execution_hours) if execution_hours > 0 else None

    bandwidth_per_unit = model.bandwidth_cost_per_unit(a)
    monthly_units = None
    if useful_units and m.window_hours:
        monthly_units = useful_units / (m.window_hours / 24.0) * 30.0
    infra_per_unit = model.network_cost_per_unit(a, monthly_units)

    total_per_unit = None
    if contributor_per_unit is not None:
        total_per_unit = contributor_per_unit + bandwidth_per_unit + (infra_per_unit or 0.0)

    centralized = []
    for baseline in a.baselines:
        local_class, local_hour = _local_class_for_unit(baseline["unit"], by_class)
        hours = (m.mean_gpu_unit_ms / model.MS_PER_HOUR
                 if baseline["unit"] == "gpu_hour" and m.mean_gpu_unit_ms
                 else (m.mean_unit_ms / model.MS_PER_HOUR if m.mean_unit_ms else None))
        per_unit = model.centralized_cost(hours, baseline["usd_per_hour"])
        centralized.append({
            **baseline,
            "local_class": local_class,
            "local_useful_hour_usd": local_hour,
            "cost_per_useful_unit_usd": _round(per_unit),
            "ratio_local_to_centralized": _round(
                model.competitive_ratio(local_hour, baseline["usd_per_hour"]), 4),
            "cheaper_than_centralized": (
                local_hour is not None and local_hour < baseline["usd_per_hour"]),
        })

    gpu_class = _dominant_gpu_class(m)
    sensitivity = model.sensitivity(a, gpu_class) if gpu_class else []

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "measured": m.to_dict(),
        "assumptions": a.to_dict(),
        "utilization": {
            "value": round(utilization, 4),
            "source": utilization_source,
            "measured_value": _round(m.utilization, 6),
            "assumed_value": a.assumed_utilization,
        },
        "contributor": {
            "total_cost_usd": round(contributor_total, 9),
            "cost_per_useful_unit_usd": _round(contributor_per_unit),
            "blended_useful_hour_usd": _round(blended_useful_hour),
            "by_class": by_class,
            "gpu_class": gpu_class,
        },
        "bandwidth_usd_per_unit": round(bandwidth_per_unit, 9),
        "network": {
            "monthly_useful_units": round(monthly_units, 1) if monthly_units else None,
            "infra_usd_per_month": a.infra_usd_per_month,
            "infra_cost_per_useful_unit_usd": _round(infra_per_unit),
        },
        "total_network_cost_per_useful_unit_usd": _round(total_per_unit),
        "centralized": centralized,
        "sensitivity": sensitivity,
        "limitations": list(LIMITATIONS),
    }


def _dominant_gpu_class(m: Measurement) -> str | None:
    gpu_classes = [k for k in m.busy_ms_by_class if k in ("consumer_gpu", "amd_gpu",
                                                          "mid_gpu", "high_gpu")]
    if not gpu_classes:
        return None
    return max(gpu_classes, key=lambda k: m.busy_ms_by_class[k])


def _local_class_for_unit(unit: str, by_class: list[dict]) -> tuple[str | None, float | None]:
    """Pick the local class (by busy time) that a baseline unit compares against.

    A GPU-hour baseline is compared to the busiest GPU-class machine; a
    CPU-hour baseline to the busiest CPU-class machine. Returns
    (class, useful_hour_cost_usd) or (None, None) when no such class ran work.
    """
    gpu_classes = {"consumer_gpu", "amd_gpu", "mid_gpu", "high_gpu"}
    if unit == "gpu_hour":
        wanted = [r for r in by_class if r["class"] in gpu_classes]
    else:
        wanted = [r for r in by_class if r["class"] not in gpu_classes]
    if not wanted:
        return None, None
    row = max(wanted, key=lambda r: r["busy_ms"])
    return row["class"], row.get("useful_hour_cost_usd")


def _round(value: float | None, digits: int = 12) -> float | None:
    return round(value, digits) if value is not None else None


def format_report(report: dict) -> str:
    """Human-readable summary for the CLI."""
    m = report["measured"]
    lines = [
        f"Economics report  {report['generated_at']}",
        "",
        "MEASURED",
        f"  useful units        {m['useful_units']}",
        (f"  executions          {m['results_total']}  "
         f"(overhead x{m['verification_overhead']}, failure {m['failure_rate']})"),
        f"  busy time           {m['busy_ms']} ms  (cpu {m['cpu_time_ms']} / gpu {m['gpu_time_ms']})",
        f"  mean unit           {m['mean_unit_ms']} ms   mean gpu unit  {m['mean_gpu_unit_ms']} ms",
        (f"  workers             {m['workers_total']} ({m['workers_online']} online)  "
         f"classes {m['workers_by_class']}"),
        f"  availability        {m['mean_availability']}   window {m['window_hours']} h",
        f"  utilization         {report['utilization']['value']} ({report['utilization']['source']})",
        f"  credits             earned {m['credits_earned']} / spent {m['credits_spent']}",
        "",
        "COST OF ONE USEFUL UNIT (assumptions in docs/economics.md)",
        f"  contributor         ${report['contributor']['cost_per_useful_unit_usd']}",
        f"  bandwidth           ${report['bandwidth_usd_per_unit']}",
        (f"  infrastructure      ${report['network']['infra_cost_per_useful_unit_usd']} "
         f"(at {report['network']['monthly_useful_units']} units/mo)"),
        f"  TOTAL               ${report['total_network_cost_per_useful_unit_usd']}",
        f"  blended useful-hr   ${report['contributor']['blended_useful_hour_usd']}",
        "",
        "CENTRALIZED COMPARISON",
    ]
    for c in report["centralized"]:
        lines.append(f"  {c['name']:<38} ${c['usd_per_hour']}/hr  "
                     f"local {c['local_class']} ${c['local_useful_hour_usd']}/useful-hr  "
                     f"local/central x{c['ratio_local_to_centralized']}  "
                     f"{'CHEAPER' if c['cheaper_than_centralized'] else 'costlier'}")
    lines.append("")
    lines.append("LIMITATIONS")
    for item in report["limitations"]:
        lines.append(f"  - {item}")
    return "\n".join(lines)
