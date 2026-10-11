"""Sprint 1: coordinator settings defaults + env overrides."""

from app.config import Settings


def test_defaults():
    s = Settings(_env_file=None)
    assert s.coordinator_host == "127.0.0.1"
    assert s.coordinator_port == 8000
    assert s.database_url == "sqlite:///./communitycompute.db"
    assert s.log_level == "info"


def test_env_override(monkeypatch):
    monkeypatch.setenv("COORDINATOR_PORT", "9000")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./custom.db")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    s = Settings(_env_file=None)
    assert s.coordinator_port == 9000
    assert s.database_url == "sqlite:///./custom.db"
    assert s.log_level == "debug"
