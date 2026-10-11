"""Worker process (Sprint 2+; Sprint 6: work loop — claim, execute, submit).

Startup sequence (implementation-guide §5):
    load config -> persistent worker ID -> register -> heartbeat -> poll/execute.

Usage:
    python apps/worker/worker/main.py --coordinator-url http://127.0.0.1:8000 --once
    python apps/worker/worker/main.py --coordinator-url http://127.0.0.1:8000 --loop --interval 3
    python apps/worker/worker/main.py --coordinator-url http://192.168.4.68:8000 --loop

Second PC: same command with the coordinator's LAN URL; use a separate
--worker-id-file per machine (each PC keeps its own persistent UUID).
"""

from __future__ import annotations

import argparse
import signal
import sys
import threading
import time
from pathlib import Path

# Allow direct execution: `python apps/worker/worker/main.py`. Adds both
# apps/worker (package imports) and the repo root (packages.protocol).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import httpx  # noqa: E402

from worker.config import (  # noqa: E402
    get_coordinator_url,
    get_or_create_worker_id,
    get_worker_id_file,
)
from worker.registration import build_payload, register_worker  # noqa: E402
from worker.capabilities.discover import discover_capabilities  # noqa: E402
from worker.capabilities.client import report_capabilities  # noqa: E402
from worker.heartbeat import build_heartbeat_payload, send_heartbeat  # noqa: E402
from worker.execution.hello_compute import execute_unit  # noqa: E402
from worker.work import claim_work, submit_result  # noqa: E402


def ping_coordinator(coordinator_url: str, worker_id: str, timeout: float = 5.0) -> dict:
    """GET /health on the coordinator. Diagnostic helper (Sprint 0); raises on failure."""
    url = f"{coordinator_url.rstrip('/')}/health"
    resp = httpx.get(url, timeout=timeout, headers={"X-Worker-Id": worker_id})
    resp.raise_for_status()
    return resp.json()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="CommunityCompute worker (Sprint 2 registration)")
    p.add_argument("--coordinator-url", default=None, help="Coordinator base URL")
    p.add_argument("--worker-id-file", default=None, help="Persistent worker ID file")
    p.add_argument("--once", action="store_true", help="Register once and exit")
    p.add_argument("--loop", action="store_true", help="Register, then re-register on interval")
    p.add_argument("--interval", type=float, default=15.0, help="Loop interval seconds")
    p.add_argument("--timeout", type=float, default=5.0, help="HTTP timeout seconds")
    p.add_argument(
        "--no-capabilities",
        action="store_true",
        help="Skip hardware capability discovery/reporting",
    )
    p.add_argument("--no-work", action="store_true", help="Skip work polling/execution")
    p.add_argument(
        "--execution-delay",
        type=float,
        default=0.0,
        help="Simulate slow work: seconds to sleep before computing (failure tests)",
    )
    return p.parse_args(argv)


def _attempt_register(coordinator_url: str, payload: dict, timeout: float) -> dict | None:
    try:
        return register_worker(coordinator_url, payload, timeout=timeout)
    except Exception as exc:  # noqa: BLE001 — startup diagnostics, refined with logging later
        print(f"[worker {payload['worker_id']}] register FAILED: {exc}", flush=True)
        return None


def _attempt_report_capabilities(coordinator_url: str, worker_id: str, timeout: float) -> None:
    """Discover + POST this machine's profile. Never fatal to the run (telemetry only)."""
    try:
        profile = discover_capabilities()
        report_capabilities(coordinator_url, worker_id, profile, timeout=timeout)
        gpus = ", ".join(
            f"{g.vendor} {g.model} " + (f"{g.vram_mb}MB" if g.vram_mb else "vram?") for g in profile.gpus
        )
        print(f"[worker {worker_id}] capabilities reported: {gpus or 'no gpu'}", flush=True)
    except Exception as exc:  # noqa: BLE001 — telemetry failure must not stop the worker
        print(f"[worker {worker_id}] capabilities FAILED: {exc}", flush=True)


def _attempt_heartbeat(coordinator_url: str, worker_id: str, timeout: float) -> None:
    try:
        payload = build_heartbeat_payload(worker_id)
        body = send_heartbeat(coordinator_url, payload, timeout=timeout)
        r = payload["resources"]
        print(
            f"[worker {worker_id}] heartbeat ok: cpu={r['cpu_percent']}% "
            f"ram_free={r['ram_available_mb']}MB gpu={r['gpu_percent']}%",
            flush=True,
        )
        _ = body
    except Exception as exc:  # noqa: BLE001 — heartbeat failure must not stop the worker
        print(f"[worker {worker_id}] heartbeat FAILED: {exc}", flush=True)


def _attempt_work_cycle(coordinator_url: str, worker_id: str, timeout: float,
                        execution_delay: float = 0.0) -> None:
    """Claim one unit, execute, submit. All failures logged, never fatal."""
    try:
        assignment = claim_work(coordinator_url, worker_id, timeout=timeout)
    except Exception as exc:  # noqa: BLE001 - claim failure: retry next tick
        print(f"[worker {worker_id}] work claim FAILED: {exc}", flush=True)
        return
    if not assignment:
        return  # nothing queued
    unit_id = assignment.get("work_unit_id")
    if execution_delay > 0:
        time.sleep(execution_delay)  # simulated slow work (failure-test knob)
    result = execute_unit(assignment)  # validates, then computes (fail closed)
    print(
        f"[worker {worker_id}] unit {unit_id} {assignment.get('range_start')}.."
        f"{assignment.get('range_end')} -> {result.status}"
        + (f" value={result.value}" if result.status == "completed" else f" ({result.error})"),
        flush=True,
    )
    body = {
        "protocol_version": assignment.get("protocol_version", ""),
        "worker_id": worker_id,
        "status": result.status,
        "value": result.value,
        "output_hash": result.output_hash,
        "error": result.error,
        "metrics": {"execution_ms": result.execution_ms},
    }
    try:
        submitted = submit_result(coordinator_url, unit_id, body, timeout=timeout)
    except Exception as exc:  # noqa: BLE001 - rejected/lost: move on, sweep will requeue
        print(f"[worker {worker_id}] result submit FAILED: {exc}", flush=True)
        return
    if submitted.get("status") == "already_completed":
        print(f"[worker {worker_id}] unit {unit_id} already completed elsewhere", flush=True)


def run_worker(args: argparse.Namespace, stop_event: threading.Event) -> int:
    """Startup: register + capabilities (once). Then loop: heartbeat → work (Sprints 4/6)."""
    coordinator_url = get_coordinator_url(args.coordinator_url)
    worker_id = get_or_create_worker_id(get_worker_id_file(args.worker_id_file))
    payload = build_payload(worker_id)
    print(
        f"[worker {worker_id}] v{payload['worker_version']} -> {coordinator_url} "
        f"(id file: {get_worker_id_file(args.worker_id_file)})",
        flush=True,
    )

    if not args.loop:
        result = _attempt_register(coordinator_url, payload, args.timeout)
        if result is None:
            return 1
        if not args.no_capabilities:
            _attempt_report_capabilities(coordinator_url, worker_id, args.timeout)
        print(f"[worker {worker_id}] registered: {result}", flush=True)
        return 0

    print(f"[worker {worker_id}] loop every {args.interval}s (Ctrl+C to stop)", flush=True)
    try:
        registered = False
        while not stop_event.is_set():
            if not registered:
                result = _attempt_register(coordinator_url, payload, args.timeout)
                if result is None:
                    print(f"[worker {worker_id}] retry in {args.interval}s", flush=True)
                    stop_event.wait(args.interval)
                    continue
                if not args.no_capabilities:
                    _attempt_report_capabilities(coordinator_url, worker_id, args.timeout)
                registered = True
                print(f"[worker {worker_id}] registered: {result.get('id')}", flush=True)
            else:
                _attempt_heartbeat(coordinator_url, worker_id, args.timeout)
                if not args.no_work:
                    _attempt_work_cycle(
                        coordinator_url, worker_id, args.timeout,
                        execution_delay=args.execution_delay,
                    )
            stop_event.wait(args.interval)
    except KeyboardInterrupt:
        print(f"[worker {worker_id}] interrupted", flush=True)
    print(f"[worker {worker_id}] stopped", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    stop_event = threading.Event()

    def _handle_signal(signum: int, _frame: object) -> None:
        print(f"[worker] signal {signum} - shutting down", flush=True)
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_signal)
    for sig_name in ("SIGTERM", "SIGBREAK"):
        sig = getattr(signal, sig_name, None)
        if sig is not None:
            try:
                signal.signal(sig, _handle_signal)
            except (OSError, ValueError):
                pass  # not deliverable on this platform

    return run_worker(args, stop_event)


if __name__ == "__main__":
    sys.exit(main())
