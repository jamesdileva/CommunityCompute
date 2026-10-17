"""SQLite engine/session/Base (Sprint 1).

SQLite is the prototype store per architecture §16. Move to PostgreSQL only
when concurrency/availability measurably justify it (see AGENTS.md §7).

Schema evolution is additive-only in early sprints: `init_db()` runs
`create_all()` then best-effort `ALTER TABLE ADD COLUMN` for known new
columns, so an existing dev DB doesn't need manual surgery (Alembic lands
when data is worth migrating).
"""

from collections.abc import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all coordinator models."""


_settings = get_settings()
_connect_args = {"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {}
engine = create_engine(_settings.database_url, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

# Additive column migrations (table -> [(column, sqlite_type)]). Drop when Alembic lands.
_ADDITIVE_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "workers": [
        ("cpu_percent", "FLOAT"),
        ("ram_available_mb", "INTEGER"),
        ("gpu_percent", "FLOAT"),
        ("paused_by_operator", "BOOLEAN DEFAULT 0"),
    ],
    "work_units": [
        ("assigned_worker_id", "VARCHAR(36)"),
        ("dispatched_at", "TIMESTAMP"),
        ("lease_id", "VARCHAR(36)"),
        ("lease_worker_id", "VARCHAR(36)"),
        ("lease_started_at", "TIMESTAMP"),
        ("lease_expires_at", "TIMESTAMP"),
        ("attempt_number", "INTEGER DEFAULT 0"),
        ("verify_of", "VARCHAR(36)"),
    ],
    "jobs": [
        ("verify_sample", "FLOAT DEFAULT 0.0"),
        ("requirements", "JSON DEFAULT '{}'"),
        ("submitter_worker_id", "VARCHAR(36)"),
        ("customer_id", "VARCHAR(36)"),
        ("workload_version", "VARCHAR(16)"),
        ("isolation_scope", "VARCHAR(64)"),
    ],
    "results": [
        ("failure_kind", "VARCHAR(32)"),
        ("verified_by", "VARCHAR(36)"),
        ("metrics", "JSON"),
    ],
}


def init_db() -> None:
    """Create tables + apply additive column migrations (imports models to register them)."""
    from app import models  # noqa: F401 — side-effect import registers models

    Base.metadata.create_all(bind=engine)
    _apply_additive_columns()


def _apply_additive_columns() -> None:
    inspector = inspect(engine)
    for table, columns in _ADDITIVE_COLUMNS.items():
        if table not in inspector.get_table_names():
            continue
        existing = {col["name"] for col in inspector.get_columns(table)}
        for name, sqlite_type in columns:
            if name not in existing:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {sqlite_type}"))
                inspector.clear_cache()


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
