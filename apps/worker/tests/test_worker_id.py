"""Sprint 0: persistent worker-ID tests (UUID, stable, never hostname)."""

import socket
import uuid
from pathlib import Path

from worker.config import get_or_create_worker_id


def test_creates_uuid_and_persists(tmp_path: Path):
    f = tmp_path / "wid"
    wid = get_or_create_worker_id(f)
    uuid.UUID(wid)  # valid UUID
    assert f.read_text().strip() == wid
    assert get_or_create_worker_id(f) == wid  # stable across restarts


def test_id_is_not_hostname(tmp_path: Path):
    wid = get_or_create_worker_id(tmp_path / "wid")
    assert socket.gethostname() not in wid


def test_corrupt_file_regenerates(tmp_path: Path):
    f = tmp_path / "wid"
    f.write_text("not-a-uuid")
    wid = get_or_create_worker_id(f)
    uuid.UUID(wid)
