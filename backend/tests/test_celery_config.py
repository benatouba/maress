from __future__ import annotations

import importlib
import os
import uuid
from collections.abc import MutableMapping
from typing import TYPE_CHECKING

from celery.result import AsyncResult

if TYPE_CHECKING:
    import pytest


def test_normalize_celery_connection_env_strips_wrapping_quotes() -> None:
    from app.core.config import normalize_celery_connection_env

    env: MutableMapping[str, str] = {
        "CELERY_BROKER_URL": ' "redis://localhost:6379/0" ',
        "CELERY_RESULT_BACKEND": "'redis://localhost:6379/1'",
        "CELERY_BROKER_READ_URL": '"redis://localhost:6379/2"',
        "CELERY_BROKER_WRITE_URL": " 'redis://localhost:6379/3' ",
    }

    normalize_celery_connection_env(env)

    assert env["CELERY_BROKER_URL"] == "redis://localhost:6379/0"
    assert env["CELERY_RESULT_BACKEND"] == "redis://localhost:6379/1"
    assert env["CELERY_BROKER_READ_URL"] == "redis://localhost:6379/2"
    assert env["CELERY_BROKER_WRITE_URL"] == "redis://localhost:6379/3"


def test_celery_app_bootstrap_normalizes_quoted_connection_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quoted_broker = '"redis://localhost:6379/0"'
    quoted_backend = '"redis://localhost:6379/1"'

    monkeypatch.setenv("CELERY_BROKER_URL", quoted_broker)
    monkeypatch.setenv("CELERY_RESULT_BACKEND", quoted_backend)

    config_module = importlib.reload(importlib.import_module("app.core.config"))
    celery_module = importlib.reload(importlib.import_module("app.celery_app"))

    assert os.environ["CELERY_BROKER_URL"] == "redis://localhost:6379/0"
    assert os.environ["CELERY_RESULT_BACKEND"] == "redis://localhost:6379/1"
    assert config_module.settings.CELERY_BROKER_URL == "redis://localhost:6379/0"
    assert config_module.settings.CELERY_RESULT_BACKEND == "redis://localhost:6379/1"

    celery_app = celery_module.celery
    assert celery_app.conf.broker_url == "redis://localhost:6379/0"
    assert celery_app.conf.result_backend == "redis://localhost:6379/1"

    AsyncResult(str(uuid.uuid4()), app=celery_app)
