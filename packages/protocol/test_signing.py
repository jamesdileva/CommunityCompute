"""Sprint 21: assignment integrity seal (HMAC, canonical JSON)."""

from packages.protocol.signing import (
    DEV_SIGNING_KEY,
    SEALED_FIELDS,
    canonical_payload,
    sign_manifest,
    verify_manifest,
)

ASSIGN = {
    "work_unit_id": "u1",
    "job_id": "j1",
    "workload_type": "hello_compute",
    "range_start": 1,
    "range_end": 100,
    "params": {"op": "sum"},
    "lease_id": "irrelevant-unsealed-field",
}


def test_sign_verify_roundtrip():
    sig = sign_manifest(ASSIGN, DEV_SIGNING_KEY)
    assert len(sig) == 64  # sha256 hex
    assert verify_manifest(ASSIGN, sig, DEV_SIGNING_KEY) is True


def test_tampered_range_breaks_seal():
    sig = sign_manifest(ASSIGN, DEV_SIGNING_KEY)
    tampered = {**ASSIGN, "range_end": 999}
    assert verify_manifest(tampered, sig, DEV_SIGNING_KEY) is False


def test_tampered_params_break_seal():
    sig = sign_manifest(ASSIGN, DEV_SIGNING_KEY)
    assert verify_manifest({**ASSIGN, "params": {"op": "hash"}}, sig,
                           DEV_SIGNING_KEY) is False


def test_wrong_key_rejected():
    sig = sign_manifest(ASSIGN, DEV_SIGNING_KEY)
    assert verify_manifest(ASSIGN, sig, "another-key") is False


def test_missing_or_empty_signature_rejected():
    assert verify_manifest(ASSIGN, None, DEV_SIGNING_KEY) is False
    assert verify_manifest(ASSIGN, "", DEV_SIGNING_KEY) is False
    assert verify_manifest(ASSIGN, 12345, DEV_SIGNING_KEY) is False


def test_unsealed_fields_do_not_affect_seal():
    a = sign_manifest(ASSIGN, DEV_SIGNING_KEY)
    b = sign_manifest({**ASSIGN, "lease_id": "different", "attempt_number": 9},
                      DEV_SIGNING_KEY)
    assert a == b  # only SEALED_FIELDS are covered


def test_key_order_irrelevant():
    shuffled = {k: ASSIGN[k] for k in reversed(list(ASSIGN))}
    assert sign_manifest(shuffled, DEV_SIGNING_KEY) == sign_manifest(ASSIGN,
                                                                     DEV_SIGNING_KEY)


def test_sealed_fields_cover_unit_identity():
    for field in ("work_unit_id", "job_id", "workload_type",
                  "range_start", "range_end", "params"):
        assert field in SEALED_FIELDS
    assert canonical_payload(ASSIGN)  # serializable, deterministic
    assert canonical_payload(ASSIGN) == canonical_payload(dict(ASSIGN))
