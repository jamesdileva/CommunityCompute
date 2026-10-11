"""Sprint 1: Worker model CRUD round-trip against throwaway SQLite."""

import uuid
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.worker import Worker


def _session(tmp_path: Path):
    engine = create_engine(
        f"sqlite:///{tmp_path}/model.db", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_worker_insert_and_read(tmp_path: Path):
    db = _session(tmp_path)
    wid = str(uuid.uuid4())
    db.add(Worker(id=wid, worker_version="0.1.0-sprint1", hostname="PC-A"))
    db.commit()

    row = db.get(Worker, wid)
    assert row is not None
    assert row.hostname == "PC-A"
    assert row.status == "unknown"  # default until heartbeats land (Sprint 4)
    assert row.first_seen is not None
    assert row.last_seen is None
    db.close()


def test_worker_ids_are_unique_primary_keys(tmp_path: Path):
    db = _session(tmp_path)
    db.add(Worker(id="22222222-2222-2222-2222-222222222222"))
    db.commit()
    assert db.query(Worker).count() == 1
    db.close()
