"""Sprint 20: worker credential store + enrollment client."""

import json
from pathlib import Path

import httpx
import pytest

from worker.credentials import (
    Credential,
    auth_headers,
    credential_path,
    enroll,
    load_credential,
    save_credential,
)


def test_save_load_roundtrip(tmp_path: Path):
    cred = Credential(worker_id="w-1", token="tok-abc")
    save_credential(tmp_path / ".worker_id", cred)
    assert (tmp_path / "credential.json").exists()
    assert load_credential(tmp_path / ".worker_id") == cred


def test_missing_credential_returns_none(tmp_path: Path):
    assert load_credential(tmp_path / ".worker_id") is None


def test_corrupt_credential_returns_none(tmp_path: Path):
    (tmp_path / "credential.json").write_text("{not json", encoding="utf-8")
    assert load_credential(tmp_path / ".worker_id") is None


def test_incomplete_credential_returns_none(tmp_path: Path):
    (tmp_path / "credential.json").write_text(
        json.dumps({"worker_id": "w-1"}), encoding="utf-8"
    )  # no token
    assert load_credential(tmp_path / ".worker_id") is None


def test_credential_path_beside_id_file(tmp_path: Path):
    assert credential_path(tmp_path / ".worker_id") == tmp_path / "credential.json"


def test_auth_headers_shape():
    assert auth_headers(None) == {}
    assert auth_headers(Credential("w", "t")) == {"Authorization": "Bearer t"}


def test_enroll_success(monkeypatch):
    def fake_post(url, json=None, timeout=None, verify=True):
        assert url.endswith("/auth/enroll")
        assert json["enrollment_token"] == "enroll-tok"
        request = httpx.Request("POST", url)
        return httpx.Response(
            201,
            json={"worker_id": "w-9", "token": "raw-cred", "status": "enrolled"},
            request=request,
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    cred = enroll("http://127.0.0.1:8000", "enroll-tok")
    assert cred == Credential(worker_id="w-9", token="raw-cred")


def test_enroll_rejects_bad_token(monkeypatch):
    """401 must surface (CLI reports the coordinator's reason, saves nothing)."""

    def fake_post(url, json=None, timeout=None, verify=True):
        raise httpx.HTTPStatusError(
            "401", request=httpx.Request("POST", url), response=httpx.Response(401)
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(httpx.HTTPStatusError):
        enroll("http://127.0.0.1:8000", "bad-token")


def test_is_unauthorized_helper():
    import worker.main as main_mod

    assert main_mod._is_unauthorized(None) is False
    exc = httpx.HTTPStatusError(
        "401",
        request=httpx.Request("POST", "http://x"),
        response=httpx.Response(401),
    )
    assert main_mod._is_unauthorized(exc) is True
    other = httpx.HTTPStatusError(
        "500",
        request=httpx.Request("POST", "http://x"),
        response=httpx.Response(500),
    )
    assert main_mod._is_unauthorized(other) is False
