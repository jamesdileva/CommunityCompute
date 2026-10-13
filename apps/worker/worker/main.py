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
import os
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
    get_tls_verify,
    get_worker_id_file,
)
from worker.registration import build_payload, register_worker  # noqa: E402
from worker.capabilities.discover import discover_capabilities  # noqa: E402
from worker.capabilities.client import report_capabilities  # noqa: E402
from worker.heartbeat import build_heartbeat_payload, send_heartbeat  # noqa: E402
from worker.execution.registry import run_unit  # noqa: E402
from worker.work import claim_work, submit_result  # noqa: E402
from worker.policy.schema import AvailabilityPolicy  # noqa: E402
from worker.policy.engine import evaluate as evaluate_policy  # noqa: E402
from worker.policy.state import MachineState, collect_state  # noqa: E402
from worker.policy.store import (  # noqa: E402
    load_policy,
    policy_path,
    save_policy,
    set_paused,
)
from worker.monitoring import build_report, report_resources  # noqa: E402
from worker.models.cache import default_cache_dir, ModelCache  # noqa: E402
from worker.capabilities.discover import cached_models  # noqa: E402
from worker.ws_client import ws_loop  # noqa: E402


def ping_coordinator(
    coordinator_url: str, worker_id: str, timeout: float = 5.0,
    verify: bool | str = True,
) -> dict:
    """GET /health on the coordinator. Diagnostic helper (Sprint 0); raises on failure."""
    url = f"{coordinator_url.rstrip('/')}/health"
    resp = httpx.get(url, timeout=timeout, headers={"X-Worker-Id": worker_id},
                     verify=verify)
    resp.raise_for_status()
    return resp.json()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="CommunityCompute worker (Sprint 2 registration)")
    p.add_argument("--coordinator-url", default=None, help="Coordinator base URL")
    p.add_argument("--worker-id-file", default=None, help="Persistent worker ID file")
    p.add_argument("--once", action="store_true", help="Register once and exit")
    p.add_argument("--loop", action="store_true", help="Register, then re-register on interval")
    p.add_argument("--interval", type=float, default=15.0,
                   help="Loop tick seconds (telemetry/policy/work per tick)")
    p.add_argument("--heartbeat-interval", type=float, default=20.0,
                   help="Heartbeat cadence seconds (>= --interval)")
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
    p.add_argument("--policy-file", default=None, help="Availability policy JSON path")
    p.add_argument("--model-cache-dir", default=None,
                   help="Model cache directory (default: MODEL_CACHE_DIR or <idfile-dir>/models)")
    p.add_argument("--no-ws", action="store_true",
                   help="Disable the WebSocket control socket (Sprint 17); "
                        "heartbeat stays on HTTP and work polls on --interval")
    p.add_argument("--ca-bundle", default=None,
                   help="TLS CA bundle PEM trusting the coordinator (Sprint 19); "
                        "default is the platform trust store")
    p.add_argument("--insecure", action="store_true",
                   help="DEV ONLY: skip TLS verification (self-signed certs). "
                        "Never use outside a test network.")
    pause = p.add_mutually_exclusive_group()
    pause.add_argument("--pause", action="store_true", help="Persist paused=true and exit")
    pause.add_argument("--resume", action="store_true", help="Persist paused=false and exit")
    return p.parse_args(argv)


def _attempt_register(coordinator_url: str, payload: dict, timeout: float,
                       verify: bool | str = True) -> dict | None:
    try:
        return register_worker(coordinator_url, payload, timeout=timeout, verify=verify)
    except Exception as exc:  # noqa: BLE001 — startup diagnostics, refined with logging later
        print(f"[worker {payload['worker_id']}] register FAILED: {exc}", flush=True)
        return None


def _attempt_report_capabilities(coordinator_url: str, worker_id: str, timeout: float,
                                 verify: bool | str = True) -> None:
    """Discover + POST this machine's profile. Never fatal to the run (telemetry only)."""
    try:
        profile = discover_capabilities()
        report_capabilities(coordinator_url, worker_id, profile, timeout=timeout,
                            verify=verify)
        gpus = ", ".join(
            f"{g.vendor} {g.model} " + (f"{g.vram_mb}MB" if g.vram_mb else "vram?") for g in profile.gpus
        )
        print(f"[worker {worker_id}] capabilities reported: {gpus or 'no gpu'}", flush=True)
    except Exception as exc:  # noqa: BLE001 — telemetry failure must not stop the worker
        print(f"[worker {worker_id}] capabilities FAILED: {exc}", flush=True)


def _attempt_heartbeat(coordinator_url: str, worker_id: str, timeout: float,
                       policy: AvailabilityPolicy | None = None) -> None:
    try:
        payload = build_heartbeat_payload(worker_id)
        if policy is not None:
            available, _reason = _availability(policy)
            payload["available"] = available
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


def _attempt_heartbeat(coordinator_url: str, worker_id: str, timeout: float,
                       availability: dict | None = None,
                       verify: bool | str = True) -> None:
    try:
        payload = build_heartbeat_payload(worker_id)
        if availability is not None:
            payload["availability"] = availability
        body = send_heartbeat(coordinator_url, payload, timeout=timeout, verify=verify)
        r = payload["resources"]
        print(
            f"[worker {worker_id}] heartbeat ok: cpu={r['cpu_percent']}% "
            f"ram_free={r['ram_available_mb']}MB gpu={r['gpu_percent']}%",
            flush=True,
        )
        _ = body
    except Exception as exc:  # noqa: BLE001 — heartbeat failure must not stop the worker
        print(f"[worker {worker_id}] heartbeat FAILED: {exc}", flush=True)


def _policy_file(args: argparse.Namespace) -> Path:
    if args.policy_file:
        return Path(args.policy_file)
    return policy_path(get_worker_id_file(args.worker_id_file))


def _availability(policy: AvailabilityPolicy) -> tuple[tuple[bool, str], dict, dict]:
    """One sampling pass: (available, reason) + availability payload + telemetry report."""
    try:
        state = collect_state()
        available, reason = evaluate_policy(policy, state)
        availability = {"available": available, "paused": policy.paused, "reason": reason}
        return (available, reason), availability, build_report(state)
    except Exception as exc:  # noqa: BLE001 - sampling failure must not silence the worker
        reason = f"sampling failed ({exc}); defaulting to available"
        availability = {"available": True, "paused": policy.paused, "reason": reason}
        return (True, reason), availability, {}


def cached_model_names() -> list[str]:
    """`name@version` strings for the coordinator's cache-preference ordering."""
    return [f"{m['name']}@{m['version']}" for m in cached_models()]


def _attempt_work_cycle(coordinator_url: str, worker_id: str, timeout: float,
                        availability: tuple[bool, str] | None = None,
                        execution_delay: float = 0.0,
                        cached_models: list[str] | None = None,
                        verify: bool | str = True) -> None:
    """Claim one unit, execute, submit. All failures logged, never fatal.

    `cached_models` is sent with the claim so the coordinator can prefer
    units whose model this worker already has local (Sprint 15).
    """
    if availability is not None and not availability[0]:
        print(f"[worker {worker_id}] holding off work: {availability[1]}", flush=True)
        return
    try:
        assignment = claim_work(coordinator_url, worker_id,
                                cached_models=cached_models, timeout=timeout,
                                verify=verify)
    except Exception as exc:  # noqa: BLE001 - claim failure: retry next tick
        print(f"[worker {worker_id}] work claim FAILED: {exc}", flush=True)
        return
    if not assignment:
        return  # nothing queued
    unit_id = assignment.get("work_unit_id")
    if execution_delay > 0:
        time.sleep(execution_delay)  # simulated slow work (failure-test knob)
    result = run_unit(assignment)  # validates, computes, self-verifies (fail closed)
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
        "metrics": {**(result.metrics or {}), "execution_ms": result.execution_ms},
    }
    try:
        submitted = submit_result(coordinator_url, unit_id, body, timeout=timeout,
                                  verify=verify)
    except Exception as exc:  # noqa: BLE001 - rejected/lost: move on, sweep will requeue
        print(f"[worker {worker_id}] result submit FAILED: {exc}", flush=True)
        return
    if submitted.get("status") == "already_completed":
        print(f"[worker {worker_id}] unit {unit_id} already completed elsewhere", flush=True)


def _wait_for_next_tick(stop_event: threading.Event, wake_event: threading.Event,
                        interval: float) -> None:
    """Sleep until the next tick, a `work_available` wake, or stop.

    One `wake_event.wait(interval)` per tick: the wake doubles as the sleep, so
    a notification interrupts even a long `--interval 30` immediately (Sprint 17
    exit condition — claim within ~1s, no aggressive polling). A consumed wake
    is cleared. A non-blocking `stop_event.wait(0)` preserves the per-tick
    stop-event poll cadence from Sprint 12. The signal handler sets both events,
    so Ctrl+C always breaks the sleep promptly.
    """
    if stop_event.is_set():
        return
    if wake_event.wait(interval):
        wake_event.clear()
    stop_event.wait(0)


def run_worker(args: argparse.Namespace, stop_event: threading.Event,
               wake_event: threading.Event | None = None,
               ws_connected: threading.Event | None = None,
               ws_loop_fn=None) -> int:
    """Startup: register + capabilities (once). Then loop: heartbeat → work (Sprints 4/6).

    Policy gate (Sprint 11): each work cycle consults the contributor's
    availability policy first; when it denies, no work is claimed.

    Control socket (Sprint 17): when `ws_loop_fn` is given (production passes
    `ws_loop`) and `--no-ws` is not set, a background thread holds
    `/ws/worker/{id}`. `work_available` frames set `wake_event` (immediate
    tick via `_wait_for_next_tick`); while `ws_connected` is set the socket
    owns the heartbeat cadence and the HTTP POST is skipped (never both).
    Unit tests omit `ws_loop_fn` → no thread, pure HTTP behavior.
    """
    if wake_event is None:
        wake_event = threading.Event()
    if ws_connected is None:
        ws_connected = threading.Event()
    if args.model_cache_dir:
        os.environ["MODEL_CACHE_DIR"] = args.model_cache_dir
    coordinator_url = get_coordinator_url(args.coordinator_url)
    tls_verify = get_tls_verify(args.ca_bundle, args.insecure)
    worker_id = get_or_create_worker_id(get_worker_id_file(args.worker_id_file))
    payload = build_payload(worker_id)
    print(
        f"[worker {worker_id}] v{payload['worker_version']} -> {coordinator_url} "
        f"(id file: {get_worker_id_file(args.worker_id_file)})",
        flush=True,
    )
    if args.insecure:
        print("[worker] WARNING: --insecure skips TLS verification "
              "(dev self-signed certs only, never across the open internet)", flush=True)

    policy_file = _policy_file(args)
    if args.pause:
        set_paused(policy_file, True)
        print(f"[worker] paused in {policy_file}", flush=True)
        return 0
    if args.resume:
        set_paused(policy_file, False)
        print(f"[worker] resumed in {policy_file}", flush=True)
        return 0
    policy = load_policy(policy_file)
    if policy.paused:
        print(f"[worker {worker_id}] policy: paused (pass --resume to unpause)", flush=True)

    if not args.loop:
        result = _attempt_register(coordinator_url, payload, args.timeout,
                                   verify=tls_verify)
        if result is None:
            return 1
        if not args.no_capabilities:
            _attempt_report_capabilities(coordinator_url, worker_id, args.timeout,
                                         verify=tls_verify)
        print(f"[worker {worker_id}] registered: {result}", flush=True)
        return 0

    print(f"[worker {worker_id}] loop every {args.interval}s (Ctrl+C to stop)", flush=True)
    heartbeat_interval = max(args.heartbeat_interval, args.interval)
    next_heartbeat = 0.0
    _last_cached = cached_models()  # re-report capabilities when this changes
    ws_thread = None
    if args.loop and ws_loop_fn is not None and not args.no_ws:
        ws_thread = threading.Thread(
            target=ws_loop_fn,
            kwargs={
                "coordinator_url": coordinator_url,
                "worker_id": worker_id,
                "stop_event": stop_event,
                "ws_connected": ws_connected,
                "wake_event": wake_event,
                "heartbeat_interval": heartbeat_interval,
                "timeout": args.timeout,
                "policy_file": policy_file,
                "ca_bundle": args.ca_bundle,
                "insecure": args.insecure,
            },
            daemon=True,
        )
        ws_thread.start()
        print(f"[worker {worker_id}] control socket on (ws); --no-ws to disable", flush=True)
    try:
        registered = False
        while not stop_event.is_set():
            now = time.monotonic()
            if not registered:
                result = _attempt_register(coordinator_url, payload, args.timeout,
                                           verify=tls_verify)
                if result is None:
                    print(f"[worker {worker_id}] retry in {args.interval}s", flush=True)
                    stop_event.wait(args.interval)
                    continue
                if not args.no_capabilities:
                    _attempt_report_capabilities(coordinator_url, worker_id, args.timeout,
                                                 verify=tls_verify)
                registered = True
                print(f"[worker {worker_id}] registered: {result.get('id')}", flush=True)
                next_heartbeat = now  # heartbeat immediately after registration
            else:
                # Policy is re-read each tick: contributor edits apply within one tick
                # (cheap JSON read; a corrupt file falls back to defaults).
                policy = load_policy(policy_file)
                # One sampling pass per tick: telemetry + policy gate + heartbeat payload
                verdict, availability, report = _availability(policy)
                report_resources(coordinator_url, worker_id, report, args.timeout,
                                 verify=tls_verify)
                if now >= next_heartbeat:
                    if ws_connected.is_set():
                        # Socket owns the heartbeat cadence while connected
                        # (Sprint 17: one heartbeat per interval, never both).
                        next_heartbeat = now + heartbeat_interval
                    else:
                        _attempt_heartbeat(coordinator_url, worker_id, args.timeout,
                                           availability=availability,
                                           verify=tls_verify)
                        next_heartbeat = now + heartbeat_interval
                    # Capability refresh incl. cached_models when the cache changed
                    cached = cached_models()
                    if cached != _last_cached:
                        _last_cached = cached
                        if not args.no_capabilities:
                            _attempt_report_capabilities(
                                coordinator_url, worker_id, args.timeout,
                                verify=tls_verify,
                            )
                if not args.no_work:
                    _attempt_work_cycle(
                        coordinator_url, worker_id, args.timeout,
                        availability=verdict, execution_delay=args.execution_delay,
                        cached_models=cached_model_names(), verify=tls_verify,
                    )
            _wait_for_next_tick(stop_event, wake_event, args.interval)
    except KeyboardInterrupt:
        print(f"[worker {worker_id}] interrupted", flush=True)
    print(f"[worker {worker_id}] stopped", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    stop_event = threading.Event()
    wake_event = threading.Event()
    ws_connected = threading.Event()

    def _handle_signal(signum: int, _frame: object) -> None:
        print(f"[worker] signal {signum} - shutting down", flush=True)
        stop_event.set()
        wake_event.set()  # break the tick sleep immediately

    signal.signal(signal.SIGINT, _handle_signal)
    for sig_name in ("SIGTERM", "SIGBREAK"):
        sig = getattr(signal, sig_name, None)
        if sig is not None:
            try:
                signal.signal(sig, _handle_signal)
            except (OSError, ValueError):
                pass  # not deliverable on this platform

    return run_worker(args, stop_event, wake_event, ws_connected, ws_loop_fn=ws_loop)


if __name__ == "__main__":
    sys.exit(main())
