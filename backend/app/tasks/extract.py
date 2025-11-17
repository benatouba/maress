from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlmodel import Session

from app.celery_app import celery
from app.core.db import SessionLocal
from app.crud import create_study_site
from app.models import ExtractionResult, Item
from app.nlp.adapters import StudySiteResultAdapter, get_primary_study_site
from app.nlp.factories import PipelineFactory
from app.nlp.model_config import ModelConfig

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

    logger.info("Initializing extraction pipeline for item %s", item_id)
    # Create config from model_config.py (reads from .env and environment)
    config = ModelConfig()
    pipeline = PipelineFactory.create_pipeline_for_api(config=config)

    logger.info("Extracting study sites from %s", path.name)
    try:
        result = pipeline.extract_from_pdf(path, title=item.title or None)
    except RuntimeError as e:
        msg = f"Extraction failed for item {item.id}: {e}"
        logger.exception(msg)
        raise RuntimeError(msg) from e

    logger.info("Converting extraction results to database models")
    study_sites = StudySiteResultAdapter.to_study_sites(
        result=result,
        item_id=item.id,
        min_confidence=config.MIN_CONFIDENCE,
    )

    if not study_sites:
        logger.warning("No study sites found for item %s", item.id)
        return {
            "item_id": item_id,
            "study_site_ids": [],
            "count": 0,
            "status": "not_found",
            "message": "No study sites found in document",
        }

    # Phase 4: Save ALL extraction candidates to extraction_result table

    logger.info("Saving all %d extraction candidates to database", len(study_sites))
    extraction_result_ids = []

    for rank, study_site in enumerate(study_sites, start=1):
        # Determine if this will be saved as a StudySite (top 10)
        is_saved = rank <= 10

        extraction_result = ExtractionResult(
            item_id=item.id,
            name=study_site.name,
            latitude=study_site.latitude,
            longitude=study_site.longitude,
            context=study_site.context,
            confidence_score=study_site.confidence_score or 0.0,
            extraction_method=study_site.extraction_method,
            source_type=study_site.source_type,
            section=study_site.section,
            rank=rank,
            is_saved=is_saved,
        )
        session.add(extraction_result)
        extraction_result_ids.append(extraction_result.id)

    session.flush()  # Ensure IDs are generated
    logger.info("Saved %d extraction candidates", len(extraction_result_ids))

    # Limit to top 10 study sites for StudySite table
    top_study_sites = study_sites[:config.MAX_STUDY_SITES]

    if len(study_sites) > config.MAX_STUDY_SITES:
        logger.info(
            "Limiting study sites from %d to top %d results",
            len(study_sites),
            config.MAX_STUDY_SITES,
        )

    # Get primary study site (highest confidence from top results)
    primary_site = get_primary_study_site(top_study_sites)

    # Save top study sites to database
    study_site_ids = []
    primary_site_id = None

    for idx, study_site in enumerate(top_study_sites):
        created = create_study_site(session=session, study_site_data=study_site)
        study_site_ids.append(str(created.id))

        # Track primary site
        if primary_site and study_site == primary_site:
            primary_site_id = str(created.id)
            logger.info(
                "Created primary study site for item %s: %s (confidence: %.2f)",
                item_id,
                created.id,
                study_site.confidence_score,
            )
        else:
            logger.info(
                "Created additional study site %d for item %s: %s (confidence: %.2f)",
                idx + 1,
                item_id,
                created.id,
                study_site.confidence_score,
            )

    total_created = len(study_site_ids)

    # IMPORTANT: Commit all changes to database
    session.commit()

    logger.info(
        "Completed extraction for item %s: %d total study sites created",
        item_id,
        total_created,
    )

    extraction_metadata = result.extraction_metadata
    metadata_summary = {
        "total_entities": extraction_metadata.total_entities,
        "coordinates_found": extraction_metadata.coordinates,
        "clusters": extraction_metadata.clusters,
        "locations_geocoded": extraction_metadata.locations,
    }

    return {
        "item_id": item_id,
        "study_site_ids": study_site_ids,
        "count": len(study_site_ids),
        "status": "created",
        "message": f"Successfully created {total_created} study site(s) from {extraction_metadata.clusters} cluster(s)",
        "primary_site_id": primary_site_id,
        "extraction_metadata": metadata_summary,
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
