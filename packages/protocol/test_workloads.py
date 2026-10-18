"""Sprint 30: signed workload definitions (catalog, sealing, tamper detection)."""

from packages.protocol.workloads import (
    WORKLOAD_CATALOG,
    attach_signed_definition,
    canonical_definition,
    definition_for,
    sign_definition,
    verify_definition,
)

KEY = "test-workload-key"


def test_catalog_covers_known_workloads():
    assert set(WORKLOAD_CATALOG) == {
        "hello_compute", "stats_range", "embeddings", "image_generate",
    }
    assert definition_for("hello_compute").version == "1"
    assert definition_for("does-not-exist") is None


def test_image_generate_is_gpu_gated():
    """Sprint 33: the GPU requirement is what routes it to a GPU class."""
    defn = definition_for("image_generate")
    assert defn.version == "1"
    assert defn.requirements.get("gpu") is True
    assert defn.requirements.get("min_vram_mb") == 2048


def test_canonical_is_order_independent():
    a = {"name": "x", "version": "1", "params": {"b": 2, "a": 1}}
    b = {"version": "1", "params": {"a": 1, "b": 2}, "name": "x"}
    assert canonical_definition(a) == canonical_definition(b)


def test_sign_and_verify_roundtrip():
    manifest = definition_for("hello_compute").to_manifest()
    sig = sign_definition(manifest, KEY)
    assert verify_definition(manifest, sig, KEY) is True
    assert verify_definition(manifest, sig, "other-key") is False
    assert verify_definition(manifest, None, KEY) is False
    assert verify_definition(manifest, "", KEY) is False


def test_tampered_definition_refused():
    manifest = definition_for("hello_compute").to_manifest()
    sig = sign_definition(manifest, KEY)
    tampered = {**manifest, "version": "999"}
    assert verify_definition(tampered, sig, KEY) is False


def test_attach_signed_definition_fills_fields():
    assignment = {"workload_type": "stats_range", "work_unit_id": "u1"}
    signed = attach_signed_definition(assignment, KEY)
    assert signed["workload_version"] == "1"
    assert verify_definition(
        definition_for("stats_range").to_manifest(),
        signed["workload_signature"], KEY,
    )


def test_attach_signed_definition_noop_for_unknown():
    assignment = {"workload_type": "mystery", "work_unit_id": "u1"}
    assert attach_signed_definition(assignment, KEY) == assignment
