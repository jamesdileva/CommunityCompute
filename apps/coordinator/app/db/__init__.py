"""SQLite engine/session/Base (Sprint 1).

SQLite is the prototype store per architecture §16. Move to PostgreSQL only
when concurrency/availability measurably justify it (see AGENTS.md §7).
"""

from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all coordinator models."""


_settings = get_settings()
_connect_args = {"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {}
engine = create_engine(_settings.database_url, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Create tables (imports models so they register on Base.metadata)."""
    from app import models  # noqa: F401 — side-effect import registers models

    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database(db: Session) -> bool:
    """True when a round-trip query succeeds. Never raises (health-probe safe)."""
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 — connectivity probe, caller decides
        return False
