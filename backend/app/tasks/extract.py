from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

from app.celery_app import celery
from app.core.db import SessionLocal
from app.crud import create_study_site
from app.models.items import Item
from app.models.study_sites import StudySiteCreate
from app.nlp.find_my_home import StudySiteExtractor

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


def _extract_study_site_impl(
    session: Session,
    item_id: str,
    user_id: str,
    is_superuser: bool,
    force: bool = False,
) -> dict[str, str | int | list[str]]:
    """Core extraction logic - separated for testability."""
    item_uuid = uuid.UUID(item_id)
    user_uuid = uuid.UUID(user_id)

    # Read and authorise
    item = _read_item(session, user_uuid, item_uuid, is_superuser=is_superuser)

    # Skip if already present and not forced
    if item.study_sites and not force:
        existing_ids = [str(site.id) for site in item.study_sites]
        return {
            "item_id": item_id,
            "study_site_ids": existing_ids,
            "count": len(existing_ids),
            "status": "skipped",
            "message": f"Item already has {len(existing_ids)} study site(s)",
        }

    if not item.attachment:
        logger.warning("Item %s has no attachment", item.id)
        return {
            "item_id": item_id,
            "study_site_ids": [],
            "count": 0,
            "status": "no_attachment",
            "message": "Item has no PDF attachment",
        }

    path = Path(item.attachment).resolve(strict=True)

    extractor = StudySiteExtractor()
    result = extractor.extract_study_sites(path, title=item.title or None)

    if not result or not result.primary_study_site:
        logger.warning("Study site not found for item %s", item.id)
        return {
            "item_id": item_id,
            "study_site_ids": [],
            "count": 0,
            "status": "not_found",
            "message": "No study sites found in document",
        }

    # Handle primary study site
    primary = result.primary_study_site
    primary_create = StudySiteCreate(
        name=primary.name,
        latitude=primary.latitude,
        longitude=primary.longitude,
        confidence_score=primary.confidence_score,
        context=primary.context,
        extraction_method=primary.extraction_method,
        section=primary.section,
        source_type=primary.source_type,
        validation_score=result.validation_score,
        item_id=item.id,
    )
    created_primary = create_study_site(session, primary_create)
    logger.info(
        "Created primary study site for item %s: %s",
        item_id,
        created_primary.id,
    )

    # Collect all study site IDs
    study_site_ids = [str(created_primary.id)]

    # Save all additional study sites
    additional_sites_created = 0
    for site in result.coordinates:
        # Skip the primary site
        if (
            site.latitude == primary.latitude
            and site.longitude == primary.longitude
            and site.context == primary.context
        ):
            continue

        additional_site = StudySiteCreate(
            name=site.name,
            latitude=site.latitude,
            longitude=site.longitude,
            confidence_score=site.confidence_score,
            context=site.context,
            extraction_method=site.extraction_method,
            section=site.section,
            source_type=site.source_type,
            validation_score=result.validation_score,
            item_id=item.id,
        )
        created_additional = create_study_site(session, additional_site)
        study_site_ids.append(str(created_additional.id))
        additional_sites_created += 1
        logger.info(
            "Created additional study site %s for item %s",
            created_additional.id,
            item_id,
        )

    total_created = 1 + additional_sites_created
    logger.info(
        "Completed extraction for item %s: %d total study sites created",
        item_id,
        total_created,
    )

    return {
        "item_id": item_id,
        "study_site_ids": study_site_ids,
        "count": len(study_site_ids),
        "status": "created",
        "message": f"Successfully created {total_created} study site(s) (1 primary + {additional_sites_created} additional)",
        "primary_site_id": str(created_primary.id),
        "extraction_metadata": {
            "validation_score": result.validation_score,
            "extraction_method": primary.extraction_method,
            "source_type": primary.source_type,
        },
    }


@celery.task(
    name="tasks.extract",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def extract_study_site_task(
    self: Task[Any],
    *,
    item_id: str,
    user_id: str,
    is_superuser: bool,
    force: bool = False,
    _test_session: Session | None = None,
) -> dict[str, str | int | list[str]]:
    """Extract study site from an item's PDF attachment.

    Args:
        _test_session: Optional session for testing (bypasses SessionLocal)
    """
    try:
        if _test_session is not None:
            # Test mode - use provided session
            return _extract_study_site_impl(
                _test_session,
                item_id,
                user_id,
                is_superuser,
                force,
            )
        # Production mode - create new session
        with SessionLocal() as session:
            return _extract_study_site_impl(
                session,
                item_id,
                user_id,
                is_superuser,
                force,
            )

    except FileNotFoundError as e:
        msg = f"Attachment file not found for item {item_id}"
        logger.exception(msg)
        raise FileNotFoundError(msg) from e

    except PermissionError:
        msg = f"Permission denied for item {item_id}"
        logger.exception(msg)
        raise

    except Exception as e:
        msg = f"extract_study_site_task failed for item {item_id}: {e!s}"
        logger.exception(msg)
        raise
