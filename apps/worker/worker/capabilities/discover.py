"""Capability discovery assembly (Sprint 3; S15 cached models; S25 policy summary)."""

from __future__ import annotations

from pathlib import Path

from worker.capabilities.cpu import discover_cpu
from worker.capabilities.gpu.registry import detect_gpus
from worker.capabilities.os_info import discover_os
from worker.capabilities.ram import discover_ram
from worker.capabilities.schema import CapabilityProfile
from worker.execution.registry import supported_runtimes
from worker.models.cache import ModelCache, default_cache_dir
from worker.policy.store import load_policy, policy_path


def cached_models() -> list[dict]:
    """Verifiable artifacts currently on disk (best-effort)."""
    try:
        return ModelCache(default_cache_dir()).list_cached()
    except OSError:
        return []


def policy_summary(worker_id_file: Path | None = None) -> dict:
    """Contributor-visible limits (Sprint 25): what the dashboard shows.

    Secrets never appear here — only the limits a non-developer set.
    """
    try:
        if worker_id_file is None:
            from worker.config import get_worker_id_file

            worker_id_file = get_worker_id_file(None)
        policy = load_policy(policy_path(worker_id_file))
    except Exception:  # noqa: BLE001 - discovery must never crash
        return {}
    data = policy.model_dump()
    data.pop("paused", None)  # status already surfaces paused separately
    return data


def discover_capabilities(worker_id_file: Path | None = None) -> CapabilityProfile:
    """Auto-detect this machine's profile. No manual hardware entry anywhere."""
    return CapabilityProfile(
        cpu=discover_cpu(),
        ram=discover_ram(),
        os=discover_os(),
        gpus=detect_gpus(),
        runtimes=supported_runtimes(),
        cached_models=cached_models(),
        sandbox=_sandbox_available(),
        policy_summary=policy_summary(worker_id_file),
    )


def _sandbox_available() -> bool:
    try:
        from worker.sandbox import native

        return native.available()
    except Exception:  # noqa: BLE001 - discovery must never crash
        return False
