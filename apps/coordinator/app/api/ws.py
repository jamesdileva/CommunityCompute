"""Worker WebSocket control plane (Sprint 17).

The socket is a control/notification channel, NOT a work transport:
claim/execute/submit stay on HTTP (idempotent, proven since Sprint 6).
The socket carries:

- inbound ``{"type": "hello"}`` → liveness touch + ``hello_ack``
- inbound ``{"type": "heartbeat", "resources": ..., "availability": ...}``
  → the SAME handler as ``POST /workers/{id}/heartbeat`` (no duplicate logic)
- outbound ``{"type": "work_available"}`` on job submit (fan-out)
- outbound ``{"type": "pause" | "resume"}`` on operator action

Heartbeat discipline: one heartbeat per interval, never both channels at once.
The worker sends heartbeats over the socket while connected and falls back to
HTTP POST when the socket is down. Unknown worker IDs are refused with a
4404 close (the WS equivalent of the HTTP 404).
"""

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.api.heartbeats import apply_heartbeat
from app.db import get_db
from app.models.worker import Worker
from app.schemas.heartbeat import Heartbeat
from app.services.ws_registry import registry

log = logging.getLogger("coordinator")

router = APIRouter()


@router.websocket("/ws/worker/{worker_id}")
async def worker_socket(
    worker_id: str, websocket: WebSocket, db: Session = Depends(get_db)
) -> None:
    await websocket.accept()
    worker = db.get(Worker, worker_id)
    if worker is None:
        await websocket.close(code=4404)
        return
    loop = asyncio.get_running_loop()
    registry.register(worker_id, websocket, loop)
    peer = websocket.client.host if websocket.client else "?"
    log.info("ws connected id=%s peer=%s", worker_id, peer)
    try:
        while True:
            try:
                msg = await websocket.receive_json()
            except WebSocketDisconnect:
                break
            except Exception:  # noqa: BLE001 - bad frame / dead socket: drop the connection
                break
            if not isinstance(msg, dict):
                await websocket.send_json({"type": "error", "error": "message must be an object"})
                continue
            mtype = msg.get("type")
            if mtype == "hello":
                now = datetime.now(timezone.utc)
                worker.last_seen = now
                if not worker.paused_by_operator:
                    worker.status = "online"
                db.commit()
                await websocket.send_json({"type": "hello_ack", "server_time": now.isoformat()})
            elif mtype == "heartbeat":
                try:
                    payload = Heartbeat(
                        worker_id=worker_id,
                        resources=msg.get("resources") or {},
                        availability=msg.get("availability"),
                    )
                except Exception as exc:  # noqa: BLE001 - pydantic shape error, report it
                    await websocket.send_json({"type": "error", "error": f"bad heartbeat: {exc}"})
                    continue
                try:
                    resp = apply_heartbeat(worker_id, payload, db)
                except HTTPException as exc:
                    detail = exc.detail
                    await websocket.send_json({"type": "error", "error": str(detail)})
                    continue
                await websocket.send_json(
                    {"type": "heartbeat_ack", "status": resp.status,
                     "server_time": resp.server_time}
                )
            else:
                await websocket.send_json({"type": "error", "error": f"unknown message type {mtype!r}"})
    finally:
        registry.unregister(worker_id, websocket)
        log.info("ws disconnected id=%s", worker_id)
