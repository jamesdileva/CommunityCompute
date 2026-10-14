"""WebSocket control client (Sprint 17).

The socket is a control/notification channel: the worker holds one persistent
connection to ``/ws/worker/{id}`` in a background thread. The server pushes
``work_available`` (job submitted) so the work loop wakes immediately instead
of sleeping out the full ``--interval`` — the Sprint 17 exit condition.
Claim/execute/submit stay on HTTP.

Heartbeat discipline: while the socket is connected the *socket* carries the
heartbeat (same payload shape as HTTP POST); when it is down the main loop
falls back to HTTP POST. One heartbeat per interval, never both — the main
loop checks ``ws_connected`` before sending over HTTP.

Reconnect uses capped backoff (1s doubling, max 8s). Enforcement stays
server-side: ``pause``/``resume`` frames are logged locally only.
"""

from __future__ import annotations

import json
import ssl
import threading
import time
from pathlib import Path

from worker.heartbeat import build_heartbeat_payload

BACKOFF_START = 1.0
BACKOFF_CAP = 8.0


def build_ssl_context(
    ca_bundle: str | Path | None = None, insecure: bool = False
) -> ssl.SSLContext | None:
    """TLS context for `wss://` control sockets (Sprint 19).

    Returns None when no TLS customization is needed (plain `ws://` or default
    trust). `insecure=True` disables verification (dev self-signed only).
    Otherwise uses the `--ca-bundle` PEM or the platform trust store.
    """
    if insecure:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    if ca_bundle is not None:
        return ssl.create_default_context(cafile=str(ca_bundle))
    return None


def build_ws_url(coordinator_url: str, worker_id: str, token: str | None = None) -> str:
    """http(s):// → ws(s):// + /ws/worker/{id} (+ ?token= for AUTH_ENABLED).

    WebSocket clients can't reliably send Authorization headers, so the
    bearer token rides the query string (Sprint 20). No token → no param
    (anonymous flow when auth is disabled).
    """
    base = coordinator_url.rstrip("/")
    if base.startswith("https://"):
        base = "wss://" + base[len("https://"):]
    elif base.startswith("http://"):
        base = "ws://" + base[len("http://"):]
    elif not base.startswith(("ws://", "wss://")):
        base = "ws://" + base
    url = f"{base}/ws/worker/{worker_id}"
    if token:
        url += f"?token={token}"
    return url


def build_hello_message(worker_id: str) -> dict:
    return {"type": "hello", "worker_id": worker_id}


def build_heartbeat_message(worker_id: str, availability: dict | None = None) -> dict:
    """Socket heartbeat: same resources/availability shape as HTTP POST."""
    payload = build_heartbeat_payload(worker_id)
    msg: dict = {"type": "heartbeat", "worker_id": worker_id,
                 "resources": payload["resources"]}
    if availability is not None:
        msg["availability"] = availability
    return msg


def next_backoff(current: float, cap: float = BACKOFF_CAP) -> float:
    """Doubling backoff capped at `cap` (pure helper, tested)."""
    return min(current * 2.0, cap)


def dispatch_message(msg: dict, wake_event: threading.Event | None = None) -> str:
    """Handle one inbound server frame. Returns the action taken.

    `work_available` sets the wake event so the work loop ticks immediately.
    """
    mtype = msg.get("type") if isinstance(msg, dict) else None
    if mtype == "work_available":
        if wake_event is not None:
            wake_event.set()
        return "work_available"
    if mtype == "pause":
        print("[worker] control: paused by operator (server enforces claim freeze)", flush=True)
        return "pause"
    if mtype == "resume":
        print("[worker] control: resumed by operator", flush=True)
        return "resume"
    if mtype in ("hello_ack", "heartbeat_ack", "error"):
        return str(mtype)
    return "unknown"


def _ws_availability(policy_file: Path | None) -> dict:
    """Availability payload for socket heartbeats (same policy as the main loop)."""
    try:
        from worker.policy.engine import evaluate as evaluate_policy
        from worker.policy.state import collect_state
        from worker.policy.store import load_policy

        policy = load_policy(policy_file) if policy_file is not None else load_policy()
        state = collect_state()
        available, reason = evaluate_policy(policy, state)
        return {"available": available, "paused": policy.paused, "reason": reason}
    except Exception as exc:  # noqa: BLE001 - sampling must never kill the socket
        return {"available": True, "paused": False,
                "reason": f"ws sampling fallback ({exc})"}


def ws_loop(
    *,
    coordinator_url: str,
    worker_id: str,
    stop_event: threading.Event,
    ws_connected: threading.Event,
    wake_event: threading.Event,
    heartbeat_interval: float = 20.0,
    timeout: float = 5.0,
    policy_file: Path | None = None,
    ca_bundle: str | Path | None = None,
    insecure: bool = False,
    token: str | None = None,
) -> None:
    """Background thread: hold the control socket, dispatch frames, heartbeat.

    Sends `hello` on connect, then listens: `work_available` wakes the work
    loop, `pause`/`resume` log locally. Heartbeats go over the socket on
    `heartbeat_interval` while connected. Any failure → clear `ws_connected`
    (main loop falls back to HTTP) → capped-backoff reconnect.

    `token` (Sprint 20) places the bearer credential in the handshake URL.
    """
    from websockets.sync.client import connect

    backoff = BACKOFF_START
    ws_url = build_ws_url(coordinator_url, worker_id, token)
    ssl_context = (
        build_ssl_context(ca_bundle, insecure) if ws_url.startswith("wss://") else None
    )
    while not stop_event.is_set():
        try:
            ws = connect(ws_url, open_timeout=timeout, ssl=ssl_context)
        except Exception as exc:  # noqa: BLE001 - coordinator down: retry with backoff
            print(f"[worker {worker_id}] ws connect FAILED: {exc} (retry in {backoff}s)",
                  flush=True)
            stop_event.wait(backoff)
            backoff = next_backoff(backoff)
            continue
        try:
            ws_connected.set()
            backoff = BACKOFF_START
            ws.send(json.dumps(build_hello_message(worker_id)))
            next_hb = time.monotonic()  # heartbeat immediately, then on cadence
            while not stop_event.is_set():
                try:
                    raw = ws.recv(timeout=1.0)
                except TimeoutError:
                    raw = None
                except Exception:  # noqa: BLE001 - connection lost: reconnect
                    break
                if raw is not None:
                    try:
                        action = dispatch_message(json.loads(raw), wake_event)
                    except Exception:  # noqa: BLE001 - bad frame: ignore
                        action = "unknown"
                    if action == "heartbeat_ack":
                        pass  # quiet steady-state; failures surface as reconnects
                if time.monotonic() >= next_hb:
                    try:
                        ws.send(json.dumps(build_heartbeat_message(
                            worker_id, _ws_availability(policy_file))))
                        next_hb = time.monotonic() + heartbeat_interval
                    except Exception:  # noqa: BLE001 - send failed: reconnect
                        break
        except Exception as exc:  # noqa: BLE001 - hello rejected or loop failure
            # Notably: the socket can connect BEFORE this worker's HTTP
            # registration lands, so the server closes with 4404. That must
            # reconnect (registration is in flight), never kill this thread.
            print(f"[worker {worker_id}] ws FAILED: {exc} (reconnect in {backoff}s)",
                  flush=True)
        finally:
            ws_connected.clear()
            try:
                ws.close()
            except Exception:  # noqa: BLE001 - best-effort close
                pass
        if stop_event.is_set():
            break
        stop_event.wait(backoff)
        backoff = next_backoff(backoff)
    ws_connected.clear()
