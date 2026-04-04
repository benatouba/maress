"""Centralized logging configuration for the Maress backend.

Call ``setup_logging()`` once at application startup (FastAPI and Celery)
to configure the root logger with:
- JSON format in staging/production (machine-parseable)
- Human-readable colored format in local development
- Consistent formatting across all modules
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from app.core.config import settings

# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

_JSON_FMT = (
    '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s",'
    '"message":"%(message)s"}'
)
_DEV_FMT = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
_DEV_DATE_FMT = "%H:%M:%S"


def _make_handler(*, json: bool) -> logging.Handler:
    handler = logging.StreamHandler(sys.stdout)
    if json:
        handler.setFormatter(logging.Formatter(_JSON_FMT))
    else:
        handler.setFormatter(logging.Formatter(_DEV_FMT, datefmt=_DEV_DATE_FMT))
    return handler


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_configured = False


def setup_logging() -> None:
    """Configure the root logger. Safe to call multiple times (idempotent)."""
    global _configured  # noqa: PLW0603
    if _configured:
        return
    _configured = True

    level = getattr(logging, settings.LOG_LEVEL, logging.INFO)
    use_json = settings.ENVIRONMENT != "local"

    root = logging.getLogger()
    root.setLevel(level)

    # Remove any pre-existing handlers (e.g. basicConfig defaults)
    root.handlers.clear()
    root.addHandler(_make_handler(json=use_json))

    # Quieten noisy third-party loggers
    for noisy in ("uvicorn.access", "httpx", "httpcore", "celery.worker.strategy"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
