"""Traversal-safe path joins (Sprint 21).

Workload payloads must never address files outside the unit's work
directory. `safe_join` resolves symlinks/`..` and refuses escapes.
"""

from __future__ import annotations

import os
from pathlib import Path


class PathEscapeError(ValueError):
    """A payload path tried to leave the work directory."""


def safe_join(work_dir: str | Path, *parts: str) -> Path:
    """Join `parts` onto `work_dir`; raise PathEscapeError on escape.

    Resolution is lexical + real where possible: the work dir itself is
    resolved (symlinks), the joined path is normalized, and membership is
    checked before any file is touched.
    """
    base = Path(work_dir).resolve()
    target = base.joinpath(*parts)
    # `..` that stays inside is fine (normalized away); leaving is not.
    normalized = Path(os.path.normpath(target))
    try:
        normalized.relative_to(base)
    except ValueError:
        raise PathEscapeError(f"path escapes work directory: {target}") from None
    return normalized
