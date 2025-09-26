# app/tasks/extract.py
from __future__ import annotations

import logging
import uuid
from pathlib import Path

from celery import states
from sqlalchemy.orm import Session

from app.celery_app import celery
from app.core.db import SessionLocal
from app.models import Item, StudySite
from app.nlp.find_my_home import StudySiteExtractor  # your extractor service

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
    self,
    *,
    item_id: str,
    user_id: str,
    is_superuser: bool,
    force: bool = False,
) -> dict[str, str | None]:
    """Extract study site from an item's PDF attachment.

    Steps:
    - Validates permissions
    - Runs StudySiteExtractor if needed
    - Persists StudySite and updates Item.study_site_id

    Returns:
        Minimal result to track progress and outcome.

    """
    try:
        with SessionLocal() as session:
            item_uuid = uuid.UUID(item_id)
            user_uuid = uuid.UUID(user_id)

            # Read and authorise
            item = _read_item(session, user_uuid, item_uuid, is_superuser=is_superuser)

            # Skip if already present and not forced
            if item.study_site_id and not force:
                return {
                    "item_id": item_id,
                    "study_site_id": str(item.study_site_id),
                    "status": "skipped",
                }

            if not item.attachment:
                logger.warning("Item %s has no attachment", item.id)
                return {"item_id": item_id, "study_site_id": None, "status": "no_attachment"}

            path = Path(item.attachment)
            if not path.exists():
                msg = f"Attachment path {path} does not exist for item {item.id}"
                raise FileNotFoundError(msg)

            extractor = StudySiteExtractor()
            result = extractor.extract_study_site(path, title=item.title or None)

            if not result or not result.primary_study_site:
                logger.warning("Study site not found for item %s", item.id)
                return {"item_id": item_id, "study_site_id": None, "status": "not_found"}

            primary = result.primary_study_site
            study_site = StudySite(
                validation_score=result.validation_score,
                latitude=primary.latitude,
                longitude=primary.longitude,
                confidence_score=primary.confidence_score,
                source_type=primary.source_type,
                context=primary.context,
                section=primary.section,
                name=primary.name,
                extraction_method=primary.extraction_method,
                owner_id=user_uuid,
            )

            session.add(study_site)
            session.flush()  # to get study_site.id without committing yet

            item.study_site_id = study_site.id
            session.add(item)
            session.commit()
            session.refresh(item)

            return {
                "item_id": item_id,
                "study_site_id": str(item.study_site_id),
                "status": "created",
            }
    except PermissionError as e:
        self.update_state(state=states.FAILURE, meta={"reason": "permission_denied"})
        raise e
    except Exception as e:
        logger.exception("extract_study_site_task failed for item %s", item_id)
        raise e
