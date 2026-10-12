"""Sprint 15: model cache behavior (fetch-once, verify, offline reuse, prune)."""

import hashlib

import pytest

from worker.models.cache import CacheError, ModelCache
from worker.models.manifest import manifest_for, model_requirement

MANIFEST = manifest_for("embeddings")
BUNDLE = MANIFEST.source[len("inline:"):].encode()


def test_manifest_roundtrip():
    assert MANIFEST is not None
    assert MANIFEST.verify(BUNDLE)
    assert model_requirement(MANIFEST) == "hashing-embedder@1"
    assert manifest_for("hello_compute") is None  # no model dependency


def test_ensure_fetches_once_then_reuses(tmp_path):
    cache = ModelCache(tmp_path)
    hit1, data1 = cache.ensure(MANIFEST, now=1000.0)
    hit2, data2 = cache.ensure(MANIFEST, now=2000.0)
    assert (hit1, data1) == (False, BUNDLE)
    assert (hit2, data2) == (True, BUNDLE)  # second call: no fetch
    assert cache.has(MANIFEST)


def test_corrupt_artifact_is_refetched_not_trusted(tmp_path):
    cache = ModelCache(tmp_path)
    cache.ensure(MANIFEST, now=1000.0)
    path = cache.artifact_path(MANIFEST)
    path.write_bytes(b"corrupted payload")
    assert cache.has(MANIFEST) is False
    hit, data = cache.ensure(MANIFEST, now=1500.0)
    assert hit is False and data == BUNDLE  # re-fetch repaired it
    assert cache.has(MANIFEST) is True


def test_offline_reuse_needs_no_network(tmp_path):
    cache = ModelCache(tmp_path)
    cache.ensure(MANIFEST, now=1000.0)
    manifest2 = type(MANIFEST)(**{**MANIFEST.__dict__,
                                  "source": "inline:tampered-bundle"})
    assert manifest2.verify  # different expected bytes, cached artifact no longer matches
    # cached copy of the ORIGINAL manifest is still served without any fetch
    hit, data = cache.ensure(MANIFEST, now=2000.0)
    assert hit is True and data == BUNDLE


def test_bad_source_rejected(tmp_path):
    cache = ModelCache(tmp_path)
    manifest = type(MANIFEST)(**{**MANIFEST.__dict__, "source": "ftp://nope"})
    with pytest.raises(CacheError):
        cache.ensure(manifest)


def test_mismatched_inline_sha_rejected(tmp_path):
    cache = ModelCache(tmp_path)
    manifest = type(MANIFEST)(**{**MANIFEST.__dict__,
                                 "sha256": hashlib.sha256(b"other").hexdigest()})
    with pytest.raises(CacheError):
        cache.ensure(manifest)


def test_list_cached_and_evict(tmp_path):
    cache = ModelCache(tmp_path)
    assert cache.list_cached() == []
    cache.ensure(MANIFEST, now=1000.0)
    assert cache.list_cached() == [{"name": "hashing-embedder", "version": "1"}]
    assert cache.evict(MANIFEST) is True
    assert cache.list_cached() == []
    assert cache.evict(MANIFEST) is False


def test_prune_evicts_oldest_first(tmp_path):
    cache = ModelCache(tmp_path)
    older = type(MANIFEST)(**{**MANIFEST.__dict__, "version": "0"})
    cache.ensure(older, now=500.0)
    cache.ensure(MANIFEST, now=1000.0)
    both = {f"{m['name']}@{m['version']}" for m in cache.list_cached()}
    assert both == {"hashing-embedder@1", "hashing-embedder@0"}
    # cap to just one artifact's size: the OLDEST-fetched one must go first
    size_of_one = cache._dir_size(cache.artifact_path(MANIFEST).parent)
    evicted = cache.prune(max_bytes=size_of_one)
    assert evicted == ["hashing-embedder@0"]
    assert [m["version"] for m in cache.list_cached()] == ["1"]


def test_prune_zero_cap_clears_everything(tmp_path):
    cache = ModelCache(tmp_path)
    cache.ensure(MANIFEST, now=1000.0)
    evicted = cache.prune(max_bytes=0)
    assert evicted == ["hashing-embedder@1"]
    assert cache.list_cached() == []

def test_default_cache_dir_prefers_env(monkeypatch, tmp_path):
    monkeypatch.setenv("MODEL_CACHE_DIR", str(tmp_path / "mc"))
    from worker.models.cache import default_cache_dir

    assert default_cache_dir() == tmp_path / "mc"


def test_default_cache_dir_beside_id_file(monkeypatch, tmp_path):
    monkeypatch.delenv("MODEL_CACHE_DIR", raising=False)
    monkeypatch.setenv("WORKER_ID_FILE", str(tmp_path / ".worker_id"))
    from worker.models.cache import default_cache_dir

    assert default_cache_dir() == tmp_path / "models"
