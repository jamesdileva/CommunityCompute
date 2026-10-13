"""WebSocket connection registry (Sprint 17).

Workers hold one persistent control socket. The registry maps worker_id →
(socket, loop) so sync HTTP handlers (pause, job submit) can push frames
back onto the event loop thread-safely.
"""

from __future__ import annotations

import asyncio
import threading

from fastapi import WebSocket


class ConnectionRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._conns: dict[str, tuple[WebSocket, asyncio.AbstractEventLoop]] = {}

    def register(self, worker_id: str, socket: WebSocket, loop: asyncio.AbstractEventLoop) -> None:
        with self._lock:
            self._conns[worker_id] = (socket, loop)

    def unregister(self, worker_id: str, socket: WebSocket | None = None) -> None:
        with self._lock:
            current = self._conns.get(worker_id)
            if current is not None and (socket is None or current[0] is socket):
                del self._conns[worker_id]

    def is_connected(self, worker_id: str) -> bool:
        with self._lock:
            return worker_id in self._conns

    def connected_workers(self) -> list[str]:
        with self._lock:
            return list(self._conns)

    def clear(self) -> None:
        """Drop all entries (tests + clean shutdown)."""
        with self._lock:
            self._conns.clear()

    async def send(self, worker_id: str, message: dict) -> bool:
        """Send from the event loop thread (e.g. inside the WS handler)."""
        with self._lock:
            entry = self._conns.get(worker_id)
        if entry is None:
            return False
        socket, _loop = entry
        try:
            await socket.send_json(message)
            return True
        except Exception:  # noqa: BLE001 - dead socket: treat as closed
            self.unregister(worker_id, socket)
            return False

    def send_from_thread(self, worker_id: str, message: dict) -> bool:
        """Thread-safe send for sync endpoints (FastAPI runs them in a threadpool)."""
        with self._lock:
            entry = self._conns.get(worker_id)
        if entry is None:
            return False
        socket, loop = entry
        try:
            asyncio.run_coroutine_threadsafe(self.send(worker_id, message), loop)
            return True
        except RuntimeError:  # loop closed
            self.unregister(worker_id, socket)
            return False

    def broadcast_from_thread(self, message: dict) -> int:
        """Fan-out to every connected worker (job submit → work_available).

        Returns the number of sockets the frame was queued for. Never raises:
        a dead socket simply unregisters on send failure.
        """
        with self._lock:
            targets = list(self._conns)
        queued = 0
        for worker_id in targets:
            if self.send_from_thread(worker_id, message):
                queued += 1
        return queued


registry = ConnectionRegistry()
