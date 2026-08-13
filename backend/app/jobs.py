import os
from collections.abc import Callable
from typing import Any


def run_job(function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Inline fallback; Celery can be enabled without changing callers."""
    if os.getenv("CELERY_BROKER_URL"):
        # The academic local build deliberately keeps execution deterministic.
        # Production wiring can dispatch the same callable through a Celery task.
        return function(*args, **kwargs)
    return function(*args, **kwargs)

