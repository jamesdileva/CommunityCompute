"""Test-scoped settings override (Sprint 20 auth tests).

`get_settings` is `lru_cache`d and reads env at first call; env changes after
that wouldn't be visible. This context manager clears the cache, applies the
given overrides, and restores the original cache afterward.
"""

import contextlib
import os
from collections.abc import Iterator


@contextlib.contextmanager
def override_settings(**overrides) -> Iterator[None]:
    from app.config import get_settings

    get_settings.cache_clear()  # drop the pre-env snapshot
    saved = {k: os.environ.get(k) for k in set(_ENV_KEYS) | set(overrides)}
    try:
        os.environ.update(overrides)
        yield
    finally:
        get_settings.cache_clear()
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


_ENV_KEYS = {"AUTH_ENABLED": "AUTH_ENABLED"}


def auth_enabled() -> dict:
    return {"AUTH_ENABLED": "true"}


def auth_disabled() -> dict:
    return {"AUTH_ENABLED": "false"}
