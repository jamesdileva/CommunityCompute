"""Worker process (Sprint 2: startup sequence + registration + graceful shutdown).

Startup sequence (implementation-guide §5):
    load config -> persistent worker ID -> register -> loop (re-register) until stopped.

Usage:
    python apps/worker/worker/main.py --coordinator-url http://127.0.0.1:8000 --once
    python apps/worker/worker/main.py --coordinator-url http://192.168.4.68:8000 --loop --interval 15

Second PC: same command with the coordinator's LAN URL; use a separate
--worker-id-file per machine (each PC keeps its own persistent UUID).
"""

from __future__ import annotations

import argparse
import signal
import sys
import threading
from pathlib import Path

# Allow direct execution: `python apps/worker/worker/main.py` (adds apps/worker to sys.path).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

from worker.config import (  # noqa: E402
    get_coordinator_url,
    get_or_create_worker_id,
    get_worker_id_file,
)
from worker.registration import build_payload, register_worker  # noqa: E402


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
    return p.parse_args(argv)


def _attempt_register(coordinator_url: str, payload: dict, timeout: float) -> dict | None:
    try:
        return register_worker(coordinator_url, payload, timeout=timeout)
    except Exception as exc:  # noqa: BLE001 — startup diagnostics, refined with logging later
        print(f"[worker {payload['worker_id']}] register FAILED: {exc}", flush=True)
        return None


def run_worker(args: argparse.Namespace, stop_event: threading.Event) -> int:
    """Startup sequence + optional re-register loop. Returns process exit code."""
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
        print(f"[worker {worker_id}] registered: {result}", flush=True)
        return 0

    print(f"[worker {worker_id}] loop every {args.interval}s (Ctrl+C to stop)", flush=True)
    try:
        while not stop_event.is_set():
            result = _attempt_register(coordinator_url, payload, args.timeout)
            if result is not None:
                print(f"[worker {worker_id}] registered ok (id={result.get('id')})", flush=True)
            else:
                print(f"[worker {worker_id}] retry in {args.interval}s", flush=True)
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
