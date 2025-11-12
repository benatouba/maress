from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from magic import Magic
from sqlmodel import Session, select

from app.celery_app import celery
from app.core.db import SessionLocal
from app.models import Item, ItemUpdate

if TYPE_CHECKING:
    from celery import Task

logger = logging.getLogger(__name__)


def _download_attachments_impl(
    session: Session,
    user_id: str,
    is_superuser: bool,
    skip: int = 0,
    limit: int = 10000,
) -> dict[str, Any]:
    """Core download logic - separated for testability."""
    from app.services import Zotero
    from app.models import User

    user_uuid = uuid.UUID(user_id)

    # Get user
    user = session.get(User, user_uuid)
    if not user:
        msg = "User not found"
        raise ValueError(msg)

    # Initialize Zotero client
    zot = Zotero(user=user, library_type="group")

    # Get items that need attachments
    if is_superuser:
        statement = (
            select(Item)
            .where(Item.attachment.is_(None))
            .offset(skip)
            .limit(limit)
        )
    else:
        statement = (
            select(Item)
            .where(Item.owner_id == user_uuid)
            .where(Item.attachment.is_(None))
            .offset(skip)
            .limit(limit)
        )

    items = session.exec(statement).all()

    if not items:
        logger.info("No items need attachments")
        return {
            "status": "completed",
            "total": 0,
            "downloaded": 0,
            "skipped": 0,
            "failed": 0,
            "message": "No items need attachments",
        }

    total = len(items)
    downloaded = 0
    skipped = 0
    failed = 0
    failed_items = []

    logger.info("Processing %d items for attachment download", total)

    for idx, item in enumerate(items, 1):
        try:
            # Update task state with progress
            celery.current_task.update_state(
                state='PROGRESS',
                meta={
                    'current': idx,
                    'total': total,
                    'status': f'Processing item {idx}/{total}...',
                    'downloaded': downloaded,
                    'skipped': skipped,
                    'failed': failed,
                }
            )

            # Get Zotero item
            zot_item = zot.item(item.key)
            if not zot_item:
                logger.warning("Zotero item %s not found", item.key)
                failed += 1
                failed_items.append({"key": item.key, "reason": "Item not found in Zotero"})
                continue

            # Check for attachment link
            if "links" not in zot_item:
                logger.warning("Zotero item %s does not have links", item.key)
                skipped += 1
                continue

            if "attachment" not in zot_item["links"]:
                logger.warning("Zotero item %s does not have attachment link", item.key)
                skipped += 1
                continue

            if not zot_item["links"]["attachment"].get("href"):
                logger.warning("Zotero item %s has invalid attachment link", item.key)
                skipped += 1
                continue

            # Get file key
            file_key = str(zot_item["links"]["attachment"]["href"].split("/")[-1])
            file_path = Path.cwd() / "zotero_files" / (file_key + ".pdf")

            # Download file if it doesn't exist
            if not file_path.is_file():
                logger.info("Downloading file for item %s (%d/%d)", item.key, idx, total)
                try:
                    file_bytes = zot.file(file_key)

                    if not isinstance(file_bytes, bytes):
                        logger.error("Zotero file for %s is not valid bytes", item.key)
                        failed += 1
                        failed_items.append({"key": item.key, "reason": "Invalid file data"})
                        continue

                    if not file_bytes:
                        logger.error("Zotero file for %s is empty", item.key)
                        failed += 1
                        failed_items.append({"key": item.key, "reason": "Empty file"})
                        continue

                    # Verify it's a PDF
                    m = Magic(mime=True)
                    if m.from_buffer(file_bytes) != "application/pdf":
                        logger.warning("File for item %s is not a PDF, skipping", item.key)
                        skipped += 1
                        continue

                    # Write file
                    with file_path.open("wb") as f:
                        f.write(file_bytes)

                    logger.info("Downloaded file for item %s", item.key)

                except Exception as e:
                    logger.exception("Failed to download file for item %s: %s", item.key, e)
                    failed += 1
                    failed_items.append({"key": item.key, "reason": str(e)})
                    continue
            else:
                logger.info("File already exists for item %s, associating", item.key)

            # Update item with attachment path
            item.attachment = str(file_path)
            session.add(item)
            session.flush()

            downloaded += 1
            logger.info(
                "Successfully associated attachment for item %s (%d/%d)",
                item.key,
                idx,
                total,
            )

        except Exception as e:
            logger.exception("Error processing item %s: %s", item.key, e)
            failed += 1
            failed_items.append({"key": item.key, "reason": str(e)})
            continue

    # Commit all changes
    session.commit()

    logger.info(
        "Attachment download completed: %d total, %d downloaded/associated, %d skipped, %d failed",
        total,
        downloaded,
        skipped,
        failed,
    )

    return {
        "status": "completed",
        "total": total,
        "downloaded": downloaded,
        "skipped": skipped,
        "failed": failed,
        "failed_items": failed_items,
        "message": f"Completed: {downloaded} downloaded/associated, {skipped} skipped, {failed} failed",
    }


@celery.task(
    name="tasks.download_attachments",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=2,
)
def download_attachments_task(
    self: Task[Any],
    *,
    user_id: str,
    is_superuser: bool,
    skip: int = 0,
    limit: int = 10000,
    _test_session: Session | None = None,
) -> dict[str, Any]:
    """Download attachments from Zotero in the background.

    Args:
        user_id: User ID as string
        is_superuser: Whether user is superuser
        skip: Pagination offset
        limit: Max items to process
        _test_session: Optional session for testing (bypasses SessionLocal)
    """
    try:
        if _test_session is not None:
            # Test mode - use provided session
            return _download_attachments_impl(
                _test_session,
                user_id,
                is_superuser,
                skip,
                limit,
            )

        # Production mode - create new session
        with SessionLocal() as session:
            return _download_attachments_impl(
                session,
                user_id,
                is_superuser,
                skip,
                limit,
            )

    except ValueError as e:
        msg = f"Invalid parameters: {e!s}"
        logger.exception(msg)
        raise

    except Exception as e:
        msg = f"download_attachments_task failed: {e!s}"
        logger.exception(msg)
        raise
