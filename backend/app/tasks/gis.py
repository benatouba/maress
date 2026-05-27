from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException

from app.celery_app import celery
from app.core.db import SessionLocal
from app.models import User

if TYPE_CHECKING:
    from sqlmodel import Session

logger = logging.getLogger(__name__)


def _load_user(session: Session, user_id: str) -> User:
    user = session.get(User, uuid.UUID(user_id))
    if user is None:
        msg = "User not found"
        raise ValueError(msg)
    return user


def _run_gis_operation_impl(
    session: Session,
    *,
    operation_id: str,
    payload: dict[str, Any],
    user_id: str,
    is_superuser: bool,  # noqa: ARG001
) -> dict[str, Any]:
    from app.api.routes.gis import execute_gis_operation

    user = _load_user(session, user_id)
    operation_result = execute_gis_operation(
        session=session,
        current_user=user,
        operation_id=operation_id,
        payload=payload,
    )

    return {
        "operation_id": operation_id,
        "status": "completed",
        "result": operation_result,
    }


@celery.task(
    name="tasks.gis.run_operation",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=2,
)
def run_gis_operation_task(
    self: Any,
    *,
    operation_id: str,
    payload: dict[str, Any],
    user_id: str,
    is_superuser: bool,
    _test_session: Session | None = None,
) -> dict[str, Any]:
    """Execute a GIS operation asynchronously and return operation result."""
    task_id = getattr(self.request, "id", "no-id")
    logger.info("Starting GIS task [task=%s] operation=%s", task_id, operation_id)

    try:
        if _test_session is not None:
            return _run_gis_operation_impl(
                _test_session,
                operation_id=operation_id,
                payload=payload,
                user_id=user_id,
                is_superuser=is_superuser,
            )

        with SessionLocal() as session:
            result = _run_gis_operation_impl(
                session,
                operation_id=operation_id,
                payload=payload,
                user_id=user_id,
                is_superuser=is_superuser,
            )
        logger.info("Finished GIS task [task=%s] operation=%s", task_id, operation_id)
        return result
    except HTTPException as exc:
        logger.exception("GIS task failed with HTTPException: %s", exc.detail)
        raise ValueError(str(exc.detail)) from exc
    except Exception as exc:
        logger.exception("GIS task failed: %s", exc)
        raise
