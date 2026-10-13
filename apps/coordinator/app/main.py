"""Coordinator entrypoint (Sprint 1: config + SQLite + Worker table + logging + error envelope).

Run:
    python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir apps/coordinator
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.health import VERSION, router as health_router
from app.api.heartbeats import router as heartbeats_router
from app.api.jobs import router as jobs_router
from app.api.network import router as network_router
from app.api.resources import router as resources_router
from app.api.workers import router as workers_router
from app.api.work import router as work_router
from app.api.ws import router as ws_router
from app.config import get_settings
from app.db import init_db

settings = get_settings()
logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("coordinator")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    log.info("coordinator up db=%s", settings.database_url)
    yield


app = FastAPI(title="CommunityCompute Coordinator", version=VERSION, lifespan=lifespan)
app.include_router(health_router)
app.include_router(workers_router)
app.include_router(heartbeats_router)
app.include_router(jobs_router)
app.include_router(work_router)
app.include_router(resources_router)
app.include_router(network_router)
app.include_router(ws_router)


def _envelope(code: int, message: object) -> dict:
    return {"error": {"code": code, "message": message}}


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=_envelope(exc.status_code, exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(status_code=422, content=_envelope(422, exc.errors()))


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error: %s", exc)
    return JSONResponse(status_code=500, content=_envelope(500, "internal server error"))
