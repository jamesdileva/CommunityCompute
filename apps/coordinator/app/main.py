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
