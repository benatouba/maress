"""Celery task for enriching item metadata via CrossRef."""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

from sqlmodel import Session

from app.celery_app import celery
from app.core.db import SessionLocal
from app.crossref import enrich_item
from app.models import Item

if TYPE_CHECKING:
    from celery import Task

logger = logging.getLogger(__name__)


def _read_item(
    session: Session,
    current_user_id: uuid.UUID,
    item_id: uuid.UUID,
    *,
    is_superuser: bool,
) -> Item:
    item = session.get(Item, item_id)
    if not item:
        msg = "Item not found"
        raise ValueError(msg)
    if not is_superuser and item.owner_id != current_user_id:
        msg = "Not enough permissions"
        raise PermissionError(msg)
    return item


def _enrich_item_impl(
    session: Session,
    item_id: str,
    user_id: str,
    is_superuser: bool,
    email: str,
) -> dict[str, str | int | dict]:
    """Core enrichment logic - separated for testability."""
    item_uuid = uuid.UUID(item_id)
    user_uuid = uuid.UUID(user_id)

    item = _read_item(session, user_uuid, item_uuid, is_superuser=is_superuser)

    # Check if item already has all fields
    if item.title and item.abstractNote and item.doi:
        return {
            "item_id": item_id,
            "status": "skipped",
            "message": "Item already has title, abstract, and DOI",
        }

    updated_fields = enrich_item(item, email=email)

    if not updated_fields:
        return {
            "item_id": item_id,
            "status": "not_found",
            "message": "No enrichment data found via CrossRef",
        }

    session.add(item)
    session.commit()

    logger.info(
        "Enriched item %s: updated fields %s",
        item_id,
        list(updated_fields.keys()),
    )

    return {
        "item_id": item_id,
        "status": "enriched",
        "updated_fields": updated_fields,
        "message": f"Updated {', '.join(updated_fields.keys())} via CrossRef",
    }


@celery.task(
    name="tasks.enrich",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def enrich_item_task(
    self: Task[Any],
    *,
    item_id: str,
    user_id: str,
    is_superuser: bool,
    email: str,
    _test_session: Session | None = None,
) -> dict[str, str | int | dict]:
    """Enrich an item's metadata via CrossRef API.

    Args:
        item_id: UUID of the item to enrich.
        user_id: UUID of the requesting user.
        is_superuser: Whether the user is a superuser.
        email: Contact email for CrossRef polite pool.
        _test_session: Optional session for testing (bypasses SessionLocal).
    """
    task_id = getattr(self.request, "id", "no-id")
    logger.info("Starting enrich task [task=%s] for item %s", task_id, item_id)

    try:
        if _test_session is not None:
            result = _enrich_item_impl(
                _test_session, item_id, user_id, is_superuser, email,
            )
        else:
            with SessionLocal() as session:
                result = _enrich_item_impl(
                    session, item_id, user_id, is_superuser, email,
                )
        logger.info("Finished enrich task [task=%s] for item %s: %s", task_id, item_id, result.get("status"))
        return result

    except PermissionError:
        msg = f"Permission denied for item {item_id}"
        logger.exception(msg)
        raise

    except Exception as e:
        msg = f"enrich_item_task failed for item {item_id}: {e!s}"
        logger.exception(msg)
        raise
