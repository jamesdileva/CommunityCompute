"""First-run setup wizard (Sprint 24; Sprint 25: full onboarding chain).

`--setup` walks the roadmap's onboarding flow: coordinator → identity →
hardware scan → capability estimate → contribution policy → autostart →
join. Every answer has a safe default; Enter accepts it. Nothing here
requires elevation.
"""

from __future__ import annotations

import sys
from pathlib import Path

from worker.capabilities.discover import discover_capabilities
from worker.capability_estimate import plain_language_summary, workload_fit_note
from worker.gpu_stats import query_gpu
from worker.policy.store import load_policy, policy_path, save_policy


def _ask(prompt: str, default: str, input_fn=input) -> str:
    raw = input_fn(f"{prompt} [{default}]: ").strip()
    return raw or default


def _ask_yes_no(prompt: str, default: bool, input_fn=input) -> bool:
    hint = "Y/n" if default else "y/N"
    raw = input_fn(f"{prompt} [{hint}]: ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes")


def _ask_float(prompt: str, default: float, input_fn=input) -> float:
    try:
        return float(_ask(prompt, str(default), input_fn))
    except ValueError:
        return default


def _tiers_of(profile) -> dict:
    """Coordinator tiers if importable, else a local fallback (never crash)."""
    try:
        from app.services.tiers import hardware_tiers

        return hardware_tiers(profile.model_dump())
    except Exception:  # noqa: BLE001 - worker must not depend on the coordinator
        return _local_tiers(profile)


def _local_tiers(profile) -> dict:
    """Coarse local fallback mirroring the coordinator bands (documented)."""
    gpus = profile.gpus or []
    vram = max((g.vram_mb or 0 for g in gpus), default=0)
    gpu = "H1" if vram <= 4096 else ("H2" if vram <= 12288 else "H3")
    cores = profile.cpu.physical_cores or profile.cpu.logical_cores or 0
    cpu = "H1" if cores <= 4 else ("H2" if cores <= 8 else "H3")
    total_gb = (profile.ram.total_mb or 0) / 1024
    ram = "H1" if total_gb <= 8 else ("H2" if total_gb <= 32 else "H3")
    return {"gpu": gpu if gpus else None, "cpu": cpu, "ram": ram}


def run_setup(
    worker_id_file: Path,
    coordinator_url: str | None = None,
    input_fn=input,
    print_fn=print,
    gpu_probe=query_gpu,
) -> dict:
    """Interactive setup. Returns what was configured (for tests/logs).

    `gpu_probe` reports the machine's live GPU metrics (default nvidia-smi);
    it is injectable so the wizard's metering-aware defaults can be tested
    deterministically.
    """
    print_fn("CommunityCompute worker setup")
    print_fn("============================")
    print_fn("Defaults are safe: answer with Enter to accept them.")
    print_fn("")

    url = _ask(
        "Coordinator URL (this PC: http://127.0.0.1:8000, "
        "second PC: http://<pc-a-lan-ip>:8000)",
        coordinator_url or "http://127.0.0.1:8000",
        input_fn,
    )
    token = _ask(
        "Enrollment token from your operator (blank = anonymous mode; "
        "required when the coordinator enforces auth)",
        "",
        input_fn,
    )

    # Hardware scan: real discovery, shown before any policy question.
    print_fn("")
    print_fn("Hardware scan (auto-detected — nothing typed by hand):")
    profile = discover_capabilities(worker_id_file)
    tiers = _tiers_of(profile)
    for line in plain_language_summary(profile.model_dump(), tiers):
        print_fn(f"  {line}")
    print_fn("  What this means for each workload:")
    for workload in ("hello_compute", "stats_range", "embeddings"):
        print_fn(f"    {workload_fit_note(workload, tiers)}")

    # Metering awareness: a GPU cap or temperature ceiling that the machine
    # cannot measure can never be enforced -- and the policy engine fails
    # closed on unknown signals, so imposing one would leave this machine
    # contributing nothing. Only offer limits we can actually honour.
    gpu = gpu_probe()
    gpu_metered = gpu.get("utilization_gpu") is not None
    temp_metered = gpu.get("temperature_gpu") is not None

    # Contribution policy: every roadmap setting, all with safe defaults.
    print_fn("")
    print_fn("Contribution policy (change any time in policy.json):")
    idle_only = _ask_yes_no("Contribute only while the machine is idle?", True, input_fn)
    max_cpu_percent = _ask_float("Maximum CPU percent while contributing (0-100)", 80.0,
                                 input_fn)
    if gpu_metered:
        max_gpu_percent = _ask_float("Maximum GPU percent while contributing (0-100)",
                                     80.0, input_fn)
    else:
        max_gpu_percent = None
        print_fn("  GPU usage is not measurable on this machine (no nvidia-smi),")
        print_fn("  so no GPU cap is set -- it could not be enforced. Add")
        print_fn('  "max_gpu_percent" to policy.json if your driver becomes measurable.')
    if temp_metered:
        temp = _ask("GPU temperature ceiling in C (blank = no ceiling)", "", input_fn)
        temperature_ceiling_c = float(temp) if temp.replace(".", "", 1).isdigit() else None
    else:
        temperature_ceiling_c = None
        print_fn("  GPU temperature is not measurable here; no temperature ceiling set.")
    battery = _ask("Battery policy (allow / plugged_only)", "allow", input_fn)
    battery_policy = battery if battery in ("allow", "plugged_only") else "allow"
    schedule = _ask("Allowed hours as start-end, 24h local (blank = always)", "", input_fn)
    allowed_hours = _parse_hours(schedule)
    bandwidth = _ask("Upload cap in Mbps (blank = no cap; payloads are KB-scale)", "",
                     input_fn)
    bandwidth_mbps = float(bandwidth) if bandwidth.replace(".", "", 1).isdigit() else None
    autostart = _ask_yes_no("Start the worker automatically at login?", False, input_fn)

    policy = load_policy(policy_path(worker_id_file))
    policy = policy.model_copy(update={
        "idle_only": idle_only,
        "max_cpu_percent": max_cpu_percent,
        "max_gpu_percent": max_gpu_percent,
        "temperature_ceiling_c": temperature_ceiling_c,
        "battery_policy": battery_policy,
        "allowed_hours": allowed_hours,
        "bandwidth_mbps": bandwidth_mbps,
    })
    save_policy(policy_path(worker_id_file), policy)

    configured = {
        "coordinator_url": url.rstrip("/"),
        "enrollment_token": token or None,
        "policy_file": str(policy_path(worker_id_file)),
        "idle_only": idle_only,
        "max_cpu_percent": max_cpu_percent,
        "max_gpu_percent": max_gpu_percent,
        "temperature_ceiling_c": temperature_ceiling_c,
        "battery_policy": battery_policy,
        "bandwidth_mbps": bandwidth_mbps,
        "autostart": autostart,
    }
    print_fn("")
    print_fn(f"Policy saved to {policy_path(worker_id_file)} (edit it any time; "
             f"changes apply within one worker tick).")
    if token:
        print_fn("Next: enroll this machine with")
        print_fn(f"  worker --enroll {token} --coordinator-url {url.rstrip('/')}")
    else:
        print_fn("Next: start contributing with")
        print_fn(f"  worker --coordinator-url {url.rstrip('/')} --loop")
    print_fn("Privacy: see docs/privacy.md — pausing, logs, and uninstall are yours.")
    return configured


def _parse_hours(text: str) -> dict | None:
    """'9-17' -> schedule window dict; blank/invalid -> None (always)."""
    if "-" not in text:
        return None
    try:
        start_s, end_s = text.split("-", 1)
        start, end = int(start_s.strip()), int(end_s.strip())
    except ValueError:
        return None
    if not (0 <= start <= 23 and 0 <= end <= 23):
        return None
    return {"start_hour": start, "end_hour": end, "days": []}


def main(argv: list[str] | None = None) -> int:
    """Entry used by `--setup` (wired in worker/main.py)."""
    from worker.config import get_coordinator_url, get_worker_id_file

    args = _parse_setup_args(argv or [])
    configured = run_setup(
        get_worker_id_file(args.worker_id_file),
        coordinator_url=args.coordinator_url or get_coordinator_url(None),
    )
    if configured["autostart"]:
        from worker.autostart import install as install_autostart

        where = install_autostart()
        print(f"Auto-start installed ({where}); disable any time with --remove-autostart.")
    return 0


def _parse_setup_args(argv: list[str]):
    import argparse

    parser = argparse.ArgumentParser(prog="worker --setup")
    parser.add_argument("--coordinator-url", default=None)
    parser.add_argument("--worker-id-file", default=None)
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
