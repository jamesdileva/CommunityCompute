"""Local model cache (Sprint 15): fetch once, verify always, reuse forever.

Layout: <cache_dir>/<name>/<version>/artifact (+ `fetched_at` marker for LRU)
- `ensure()` fetches on miss and sha256-verifies the artifact; a corrupted
  file is re-fetched, never trusted.
- Offline behavior: a cached artifact is reused with zero network access.
- `prune()` evicts least-recently-fetched artifacts until under the cap.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import time
from pathlib import Path

from worker.models.manifest import ModelManifest

FETCH_MARKER = "fetched_at"  # mtime of last (re)fetch, used for LRU


class CacheError(RuntimeError):
    """Fetch/verify failure; callers decide whether work can proceed."""


class ModelCache:
    def __init__(self, cache_dir: str | Path) -> None:
        self.cache_dir = Path(cache_dir)

    # ---- paths ------------------------------------------------------------
    def artifact_path(self, manifest: ModelManifest) -> Path:
        return self.cache_dir / manifest.name / manifest.version / "artifact"

    def _fetch_marker(self, manifest: ModelManifest) -> Path:
        return self.cache_dir / manifest.name / manifest.version / FETCH_MARKER

    # ---- lookup ------------------------------------------------------------
    def has(self, manifest: ModelManifest) -> bool:
        path = self.artifact_path(manifest)
        if not path.exists():
            return False
        try:
            return manifest.verify(path.read_bytes())
        except OSError:
            return False

    def list_cached(self) -> list[dict]:
        """[{name, version}] for every verifiable artifact on disk."""
        out: list[dict] = []
        if not self.cache_dir.exists():
            return out
        for name_dir in sorted(self.cache_dir.iterdir()):
            if not name_dir.is_dir():
                continue
            for version_dir in sorted(name_dir.iterdir()):
                artifact = version_dir / "artifact"
                if not artifact.is_file():
                    continue
                out.append({"name": name_dir.name, "version": version_dir.name})
        return out

    # ---- fetch -------------------------------------------------------------
    def ensure(self, manifest: ModelManifest, now: float | None = None) -> tuple[bool, bytes]:
        """Return (cache_hit, artifact_bytes). Fetches on miss; verifies always."""
        path = self.artifact_path(manifest)
        if path.exists():
            try:
                data = path.read_bytes()
                if manifest.verify(data):
                    return True, data
            except OSError:
                pass  # unreadable → treat as miss and re-fetch
            self._remove(manifest)
        data = self._fetch(manifest)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self._touch(manifest, now if now is not None else time.time())
        return False, data

    def evict(self, manifest: ModelManifest) -> bool:
        if self.artifact_path(manifest).exists():
            self._remove(manifest)
            return True
        return False

    def prune(self, max_bytes: int) -> list[str]:
        """Evict oldest-fetched artifacts until the cache fits; returns evicted keys."""
        entries = self._entries_with_sizes()  # (fetched_at, key, size, path)
        total = sum(size for _at, _key, size, _path in entries)
        entries.sort(key=lambda e: e[0])  # oldest fetch time first
        evicted: list[str] = []
        for _at, key, size, path in entries:
            if total <= max_bytes:
                break
            shutil.rmtree(path.parent, ignore_errors=True)
            total -= size
            evicted.append(key)
        return evicted

    # ---- internals ---------------------------------------------------------
    def _entries_with_sizes(self) -> list[tuple[float, str, int, Path]]:
        entries: list[tuple[float, str, int, Path]] = []
        if not self.cache_dir.exists():
            return entries
        for artifact in self.cache_dir.glob("*/*/artifact"):
            name, version = artifact.parent.parent.name, artifact.parent.name
            fetched_at = self._fetch_time(artifact.parent)
            size = self._dir_size(artifact.parent)
            entries.append((fetched_at, f"{name}@{version}", size, artifact))
        return entries

    def _fetch_time(self, version_dir: Path) -> float:
        """Marker file (explicit fetch time) when written, else artifact mtime."""
        marker = version_dir / FETCH_MARKER
        try:
            value = float(marker.read_text(encoding="utf-8").strip())
            if value > 0:
                return value
        except (OSError, ValueError):
            pass
        try:
            return (version_dir / "artifact").stat().st_mtime
        except OSError:
            return 0.0

    def _remove(self, manifest: ModelManifest) -> None:
        shutil.rmtree(self.artifact_path(manifest).parent, ignore_errors=True)

    def _touch(self, manifest: ModelManifest, when: float) -> None:
        marker = self._fetch_marker(manifest)
        try:
            marker.write_text(str(when), encoding="utf-8")
        except OSError:
            pass  # marker is an LRU nicety, not correctness

    def _fetch(self, manifest: ModelManifest) -> bytes:
        source = manifest.source
        if source.startswith("inline:"):
            data = source[len("inline:"):].encode()
        elif source.startswith("file:"):
            data = Path(source[len("file:"):]).read_bytes()
        elif source.startswith("http://") or source.startswith("https://"):
            import httpx

            response = httpx.get(source, timeout=30.0, follow_redirects=True)
            response.raise_for_status()
            data = response.content
        else:
            raise CacheError(f"unsupported source {source!r}")
        if not manifest.verify(data):
            raise CacheError(
                f"artifact for {manifest.key} failed sha256 verification "
                f"(got {hashlib.sha256(data).hexdigest()[:12]}..., "
                f"want {manifest.sha256[:12]}...)"
            )
        return data

    @staticmethod
    def _dir_size(path: Path) -> int:
        return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def default_cache_dir() -> Path:
    """MODEL_CACHE_DIR wins; else <id-file-dir>/models, else ./models."""
    env = os.environ.get("MODEL_CACHE_DIR")
    if env:
        return Path(env)
    id_file = os.environ.get("WORKER_ID_FILE")
    if id_file:
        return Path(id_file).resolve().parent / "models"
    return Path("models")
