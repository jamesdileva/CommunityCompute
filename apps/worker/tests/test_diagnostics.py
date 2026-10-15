"""Sprint 26: --diagnostics redacted support bundle."""

import json

from worker.credentials import Credential, save_credential
from worker.main import _print_diagnostics, parse_args


def test_diagnostics_redacts_credential(tmp_path, capsys):
    save_credential(tmp_path / ".worker_id",
                    Credential(worker_id="w-1", token="SECRET-TOKEN-XYZ"))
    (tmp_path / ".worker_id").write_text("x", encoding="utf-8")
    (tmp_path / "policy.json").write_text(json.dumps({"paused": False}), encoding="utf-8")
    args = parse_args(["--diagnostics", "--worker-id-file", str(tmp_path / ".worker_id")])
    assert _print_diagnostics(args) == 0
    out = capsys.readouterr().out
    assert "SECRET-TOKEN-XYZ" not in out  # the secret never appears
    assert "present (value redacted)" in out
    assert "worker id      : w-1" in out
    assert "sandbox layer" in out


def test_diagnostics_anonymous_worker(tmp_path, capsys):
    (tmp_path / ".worker_id").write_text("y", encoding="utf-8")
    args = parse_args(["--diagnostics", "--worker-id-file", str(tmp_path / ".worker_id")])
    assert _print_diagnostics(args) == 0
    out = capsys.readouterr().out
    assert "credential     : absent" in out


def test_diagnostics_shows_log_tail(tmp_path, capsys):
    (tmp_path / ".worker_id").write_text("z", encoding="utf-8")
    log = tmp_path / "worker.log"
    log.write_text("\n".join(f"line {i}" for i in range(30)), encoding="utf-8")
    args = parse_args(["--diagnostics", "--worker-id-file", str(tmp_path / ".worker_id"),
                       "--log-file", str(log)])
    assert _print_diagnostics(args) == 0
    out = capsys.readouterr().out
    assert "line 29" in out  # tail included
    assert "line 0" not in out  # head excluded (last 15 only)
