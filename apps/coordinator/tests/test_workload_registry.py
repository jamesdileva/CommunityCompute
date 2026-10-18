"""Sprint 13: coordinator workload registry dispatch (verification stays generic)."""

import pytest
from app.services.workloads import expected
from app.services.workloads import output_hash as workload_hash


def test_expected_hello_compute_ops():
    assert expected("hello_compute", "sum", 1, 100) == 5050
    import hashlib

    assert expected("hello_compute", "hash", 1, 100) == hashlib.sha256(b"1:100").hexdigest()


def test_expected_stats_range():
    assert expected("stats_range", "sum", 1, 10) == {
        "count": 10, "sum": 55, "max": 10, "min": 1,
    }
    assert expected("stats_range", "sum", 7, 7) == {
        "count": 1, "sum": 7, "max": 7, "min": 7,
    }


def test_unknown_type_raises_value_error():
    with pytest.raises(ValueError):
        expected("totally_unknown", "sum", 1, 10)


def test_hash_of_both_workloads():
    hello = workload_hash("hello_compute", "sum", 5050)
    stats = workload_hash("stats_range", "sum", {"count": 100, "sum": 5050})
    assert isinstance(hello, str) and len(hello) == 64
    assert isinstance(stats, str) and len(stats) == 64
    assert hello != stats


def test_expected_embeddings_batch():
    batch = expected("embeddings", "sum", 1, 3, {"dim": 32})
    assert batch["dim"] == 32
    assert len(batch["vectors"]) == 3
    assert all(len(v) == 32 for v in batch["vectors"])


def test_expected_embeddings_default_dim():
    batch = expected("embeddings", "sum", 1, 1)
    assert batch["dim"] == 128 and len(batch["vectors"][0]) == 128


def test_hash_of_unknown_type_raises():
    with pytest.raises(ValueError):
        workload_hash("totally_unknown", "sum", 1)


def test_hash_of_embeddings():
    h = workload_hash("embeddings", "sum", {"vectors": [[0.1]]}, {"dim": 8})
    assert isinstance(h, str) and len(h) == 64


def test_expected_image_generate():
    value = expected("image_generate", "sum", 0, 3, {"size": 8})
    assert value["tiles"] == 4 and value["size"] == 8 and len(value["checksum"]) == 64


def test_image_generate_params_default_and_bad():
    default = expected("image_generate", "sum", 0, 1)
    assert default["size"] == 32 and default["tiles"] == 2
    with pytest.raises(ValueError):
        expected("image_generate", "sum", 0, 1, {"size": -1})


def test_hash_of_image_generate():
    h = workload_hash("image_generate", "sum", {"size": 8, "tiles": 1, "checksum": "x"})
    assert isinstance(h, str) and len(h) == 64
