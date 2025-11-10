from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from celery import states
from sqlalchemy.orm import Session  # noqa: TC002

from app.celery_app import celery
from app.core.db import SessionLocal
from app.crud import create_study_site
from app.models.items import Item
from app.models.study_sites import StudySiteCreate
from app.nlp.find_my_home import StudySiteExtractor  # your extractor service

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


@celery.task(
    name="tasks.extract",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def extract_study_site_task(
    self: Task[Any],  # pyright: ignore[reportInvalidTypeArguments, reportUnknownParameterType]
    *,
    item_id: str,
    user_id: str,
    is_superuser: bool,
    force: bool = False,
) -> dict[str, str | int | list[str]]:
    """Extract study site from an item's PDF attachment.

    Steps:
    - Validates permissions
    - Runs StudySiteExtractor if needed
    - Creates new StudySite linked to Item via one-to-many relationship

    Returns:
        Dict with extraction results including study site IDs and metadata.
    """
    try:
        with SessionLocal() as session:
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
            created = create_study_site(session, primary_create)
            logger.info(
                "Created study site for item %s: %s",
                item_id,
                created.id,
            )

            study_sites = [
                StudySiteCreate(
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
                    # is_primary=False,
                )
                for site in result.coordinates
            ]

            study_site_ids = [str(created.id)]
            study_site_ids.extend(str(site.id) for site in study_sites)
            return {
                "item_id": item_id,
                "study_site_ids": study_site_ids,
                "count": len(study_site_ids),
                "status": "created",
                "message": f"Successfully created primary study site {created.id} study site(s)",
                "primary_site_id": str(created.id),
                "extraction_metadata": {
                    "validation_score": result.validation_score,
                    "extraction_method": primary.extraction_method,
                    "source_type": primary.source_type,
                },
            }

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
