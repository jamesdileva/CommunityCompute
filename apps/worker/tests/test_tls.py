"""Sprint 19: TLS transport — verify selection, forwarding, wss context."""

import ssl

import httpx

from worker import ws_client
from worker.capabilities.client import report_capabilities
from worker.config import get_tls_verify
from worker.heartbeat import send_heartbeat
from worker.main import parse_args, ping_coordinator
from worker.monitoring import report_resources
from worker.registration import register_worker
from worker.work import claim_work, submit_result
from worker.ws_client import build_ssl_context, build_ws_url


def test_tls_verify_defaults_to_platform_store():
    assert get_tls_verify() is True


def test_tls_verify_ca_bundle_passthrough():
    assert get_tls_verify("dev-tls.pem") == "dev-tls.pem"


def test_tls_verify_insecure_wins():
    assert get_tls_verify("dev-tls.pem", insecure=True) is False
    assert get_tls_verify(insecure=True) is False


def test_parse_args_tls_flags():
    args = parse_args(["--loop"])
    assert args.ca_bundle is None and args.insecure is False
    args = parse_args(["--loop", "--ca-bundle", "dev-tls.pem", "--insecure"])
    assert args.ca_bundle == "dev-tls.pem" and args.insecure is True


def _capture(monkeypatch):
    seen: dict = {}

    def fake_post(url, json=None, timeout=None, verify=True):
        seen.update(url=url, json=json, timeout=timeout, verify=verify)
        request = httpx.Request("POST", url)
        return httpx.Response(200, json={"ok": True}, request=request)

    monkeypatch.setattr(httpx, "post", fake_post)
    return seen


def test_register_forwards_verify(monkeypatch):
    seen = _capture(monkeypatch)
    register_worker("https://h:8443", {"worker_id": "w"}, verify="ca.pem")
    assert seen["verify"] == "ca.pem" and seen["url"].startswith("https://")


def test_heartbeat_forwards_verify(monkeypatch):
    seen = _capture(monkeypatch)
    send_heartbeat("https://h:8443", {"worker_id": "w", "resources": {}}, verify=False)
    assert seen["verify"] is False


def test_claim_and_submit_forward_verify(monkeypatch):
    seen = _capture(monkeypatch)
    claim_work("https://h:8443", "w", verify="ca.pem")
    assert seen["verify"] == "ca.pem"
    submit_result("https://h:8443", "u", {"worker_id": "w"}, verify="ca.pem")
    assert seen["verify"] == "ca.pem"


def test_telemetry_and_capabilities_forward_verify(monkeypatch):
    seen = _capture(monkeypatch)
    report_resources("https://h:8443", "w", {}, verify="ca.pem")
    assert seen["verify"] == "ca.pem"

    class Profile:
        def model_dump(self):
            return {}

    report_capabilities("https://h:8443", "w", Profile(), verify="ca.pem")
    assert seen["verify"] == "ca.pem"


def test_ping_forwards_verify(monkeypatch):
    seen: dict = {}

    def fake_get(url, timeout=None, headers=None, verify=True):
        seen.update(verify=verify)
        request = httpx.Request("GET", url)
        return httpx.Response(200, json={"status": "ok"}, request=request)

    monkeypatch.setattr(httpx, "get", fake_get)
    ping_coordinator("https://h:8443", "w", verify="ca.pem")
    assert seen["verify"] == "ca.pem"


def test_ws_url_https_maps_to_wss():
    assert build_ws_url("https://h:8443", "w") == "wss://h:8443/ws/worker/w"


def test_ssl_context_default_is_none():
    assert build_ssl_context() is None


def test_ssl_context_insecure_disables_verification():
    ctx = build_ssl_context(insecure=True)
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.verify_mode == ssl.CERT_NONE
    assert ctx.check_hostname is False


def test_ssl_context_missing_bundle_raises():
    import pytest

    with pytest.raises(Exception):
        ws_client.build_ssl_context("no-such-bundle.pem")
