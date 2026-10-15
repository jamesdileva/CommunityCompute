"""First-run setup wizard (Sprint 24).

`--setup` walks a new contributor through the three things the worker
needs — where the coordinator lives, how to prove identity, and when the
machine may contribute — then persists everything and prints what happens
next. Every answer has a safe default; Enter accepts it. Nothing here
requires elevation.
"""

from __future__ import annotations

import sys
from pathlib import Path

from worker.policy.schema import AvailabilityPolicy
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


def run_setup(
    worker_id_file: Path,
    coordinator_url: str | None = None,
    input_fn=input,
    print_fn=print,
) -> dict:
    """Interactive setup. Returns what was configured (for tests/logs)."""
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
    idle_only = _ask_yes_no("Contribute only while the machine is idle?", True, input_fn)
    max_cpu = _ask("Maximum CPU percent while contributing (0-100)", "80", input_fn)
    try:
        max_cpu_percent = float(max_cpu)
    except ValueError:
        max_cpu_percent = 80.0
    autostart = _ask_yes_no("Start the worker automatically at login?", False, input_fn)

    policy_file = policy_path(worker_id_file)
    policy = load_policy(policy_file)
    policy = policy.model_copy(
        update={"idle_only": idle_only, "max_cpu_percent": max_cpu_percent}
    )
    save_policy(policy_file, policy)

    configured = {
        "coordinator_url": url.rstrip("/"),
        "enrollment_token": token or None,
        "policy_file": str(policy_file),
        "idle_only": idle_only,
        "max_cpu_percent": max_cpu_percent,
        "autostart": autostart,
    }
    print_fn("")
    print_fn(f"Policy saved to {policy_file} (edit it any time; changes apply "
             f"within one worker tick).")
    if token:
        print_fn("Next: enroll this machine with")
        print_fn(f"  worker --enroll {token} --coordinator-url {url.rstrip('/')}")
    else:
        print_fn("Next: start contributing with")
        print_fn(f"  worker --coordinator-url {url.rstrip('/')} --loop")
    print_fn("Privacy: see docs/privacy.md — pausing, logs, and uninstall are yours.")
    return configured


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
