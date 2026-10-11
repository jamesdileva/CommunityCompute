"""Minimal Coordinator for Sprint 0.

Sprint 0 exit: repo can run a minimal coordinator process.
Sprint 1 will add: config, SQLite connection, SQLAlchemy models, logging, error handling.

Run:
    python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir apps/coordinator
"""

from fastapi import FastAPI

SERVICE = "coordinator"
VERSION = "0.1.0-sprint0"

app = FastAPI(title="CreatorLab Coordinator", version=VERSION)


@app.get("/health")
def health() -> dict:
    """Liveness probe. Sprint 1 extends with SQLite connectivity check."""
    return {"status": "ok", "service": SERVICE, "version": VERSION}
