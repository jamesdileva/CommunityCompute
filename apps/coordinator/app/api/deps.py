"""Bearer-token auth (Sprint 20).

    Authorization: Bearer <token>

`authenticate` verifies the bearer credential and returns the authenticated
worker id (or None when auth is disabled — the pre-Sprint-20 LAN dev flow).
Every worker-facing route applies it, including the WebSocket socket (same
rules: 401 on missing/invalid/revoked; a token valid but for a *different*
worker id never claims as someone else). Revocation is per-call: a revoked
token stops working on its next request.

Routes that name the worker in the *body* (`POST /workers/register`,
`POST /work/{id}/result`) can't be checked from `path_params` alone, so a tiny
middleware (`CaptureBodyMiddleware`) stashes the parsed JSON body on
`request.state.body` — the dependency then compares the bearer's worker
against either the path param or the body's `worker_id`.
"""

import json

from fastapi import Depends, HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.services.auth import verify_credential


class CaptureBodyMiddleware(BaseHTTPMiddleware):
    """Cache parsed JSON bodies so `authenticate` can read `worker_id`.

    Reading the body in a dependency would consume the stream for FastAPI's
    own Pydantic parsing; the middleware re-wraps receive so both see it.
    """

    async def dispatch(self, request: Request, call_next):
        if request.method in ("POST", "PUT", "PATCH"):
            try:
                body = await request.body()
                request.state.body = json.loads(body) if body else {}
                sent = {"done": False}

                async def receive():
                    if sent["done"]:
                        return {"type": "http.disconnect"}
                    sent["done"] = True
                    return {"type": "http.request", "body": body, "more_body": False}

                request._receive = receive  # noqa: SLF001 - documented starlette seam
            except Exception:  # noqa: BLE001 - non-JSON bodies: FastAPI reports 422
                request.state.body = {}
        return await call_next(request)


def _unauthorized(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": "unauthorized", "message": message},
        headers={"WWW-Authenticate": "Bearer"},
    )


def extract_bearer(request: Request) -> str | None:
    """`Authorization: Bearer <token>` -> token or None."""
    header = request.headers.get("Authorization") or ""
    if not header.lower().startswith("bearer "):
        return None
    token = header[7:].strip()
    return token or None


def authenticate(request: Request, db: Session = Depends(get_db)) -> str | None:
    """Authenticated worker_id, or None when `AUTH_ENABLED=false`.

    Raises 401 for a missing/blank bearer, an unknown token, a revoked
    credential, or a token whose worker doesn't match the request's target
    worker (`worker_id` in the path params or JSON body).
    """
    if not get_settings().auth_enabled:
        return None
    token = extract_bearer(request)
    if not token:
        raise _unauthorized("missing bearer token")
    credential = verify_credential(db, token)
    if credential is None:
        raise _unauthorized("invalid or revoked token")
    target = request.path_params.get("worker_id")
    if not target:
        body = getattr(request.state, "body", None)
        if isinstance(body, dict):
            target = body.get("worker_id")
    if target and credential.worker_id != str(target):
        raise _unauthorized("token does not match this worker")
    return credential.worker_id
