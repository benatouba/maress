import logging
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Any, Literal

from celery.result import AsyncResult
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse
from magic import Magic
from sqlalchemy import BinaryExpression, ColumnElement
from sqlmodel import col, func, or_, select

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.celery_app import celery
from app.models import (
    Creator,
    ExtractionResult,
    ExtractionResultPublic,
    ExtractionResultsPublic,
    ExtractStudySitesRequest,
    Item,
    ItemCreate,
    ItemPublic,
    ItemsPublic,
    ItemUpdate,
    Message,
    StudySite,
    StudySiteUpdate,
    Tag,
    TaskRef,
    TasksAccepted,
)
from app.services import Zotero
from app.tasks.extract import extract_study_site_task
from maress_types import ZoteroItemList

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/items", tags=["items"])


def read_db_items(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 500,
) -> tuple[Sequence[Item], int]:
    """Helper function to retrieve items with pagination."""
    from sqlalchemy.orm import joinedload, selectinload

    if current_user.is_superuser:
        count_statement = select(func.count()).select_from(Item)
        count = session.exec(count_statement).one()
        statement = (
            select(Item)
            .offset(skip)
            .limit(limit)
            .options(
                joinedload(Item.study_sites).joinedload(StudySite.location),
                selectinload(Item.creators),
                selectinload(Item.tags),
            )
        )
        items = session.exec(statement).unique().all()
    else:
        count_statement = (
            select(func.count()).select_from(Item).where(Item.owner_id == current_user.id)
        )
        count = session.exec(count_statement).one()
        statement = (
            select(Item)
            .where(Item.owner_id == current_user.id)
            .offset(skip)
            .limit(limit)
            .options(
                joinedload(Item.study_sites).joinedload(StudySite.location),
                selectinload(Item.creators),
                selectinload(Item.tags),
            )
        )
        items = session.exec(statement).unique().all()

    return items, count


@router.get("/")
def read_items(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 10,
) -> ItemsPublic:
    """Retrieve items."""
    items, count = read_db_items(session, current_user, skip, limit)
    return ItemsPublic(data=items, count=count)  # pyright: ignore[reportArgumentType]


@router.get("/{id}", response_model=ItemPublic)
def read_item(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Item:
    """Get item by ID."""
    from sqlalchemy.orm import joinedload, selectinload

    statement = (
        select(Item)
        .where(Item.id == id)
        .options(
            joinedload(Item.study_sites).joinedload(StudySite.location),
            selectinload(Item.creators),
            selectinload(Item.tags),
        )
    )
    item = session.exec(statement).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
    return item


@router.get("/search/")
def search_items(
    session: SessionDep,
    current_user: CurrentUser,
    title: Annotated[str | None, Query(description="Search by title")] = None,
    tag: Annotated[str | None, Query(description="Search by tag")] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> ItemsPublic:
    """Search items by title or tag."""
    # Base query
    statement = select(Item)

    # Apply user permission filter
    if not current_user.is_superuser:
        statement = statement.where(Item.owner_id == current_user.id)

    filters: list[BinaryExpression[bool] | ColumnElement[bool]] = []
    if title:
        filters.append(col(Item.title).ilike(f"%{title}%"))
    if tag:
        # Assuming relationship with tags
        filters.append(col(Item.tags).any(col(Tag.name).ilike(f"%{tag}%")))

    # Apply OR condition if multiple filters
    if filters:
        if len(filters) == 1:
            statement = statement.where(filters[0])
        else:
            statement = statement.where(or_(*filters))

    # Apply pagination
    statement = statement.offset(skip).limit(limit)

    # Execute query
    items = session.exec(statement).all()

    count = len(items)

    return ItemsPublic(data=items, count=count)  # pyright: ignore[reportArgumentType]


@router.post("/", response_model=ItemPublic)
def create_item(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    item_in: ItemCreate,
) -> Any:
    """Create new item."""
    item = Item.model_validate(item_in, update={"owner_id": current_user.id})
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.get("/zotero_collections/{library_type}")
def get_zotero_collections(
    session: SessionDep,
    current_user: CurrentUser,
    library_type: Literal["group", "user"],
) -> Any:
    db_user = crud.get_user_by_email(session=session, email=current_user.email)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    zot = Zotero(
        user=db_user,
        library_type=library_type,
    )
    return zot.collections()


@router.get("/import_from_zotero/")
def import_zotero_items(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 20000, # FIXME: This should be properly handled. High value to effectvely remove this
    *,
    reload: bool = False,
    library_type: Literal["group", "user"] = "group",
    collection_id: str | None = None,
):
    """Import items from Zotero library or specific collection.

    Args:
        collection_id: Optional Zotero collection ID. If provided, imports only from that collection.
                      If None, imports all items from the library.
    """
    db_user = crud.get_user_by_email(session=session, email=current_user.email)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    zot = Zotero(
        user=db_user,
        library_type=library_type,
    )
    # if not limit or limit is greater than 100, repeat until all items are fetched
    zot_items: ZoteroItemList = []
    start = skip
    while True:
        if collection_id:
            # Fetch items from specific collection
            batch: ZoteroItemList = zot.collection_items(collection_id, start=start)  # pyright: ignore[reportUnknownMemberType]
        else:
            # Fetch all items from library
            batch: ZoteroItemList = zot.items(start=start, limit=100)  # pyright: ignore[reportUnknownMemberType]

        if not batch:
            break
        zot_items.extend(batch)
        if len(batch) < 100:
            break
        start += 100
    # apply limit to the total items fetched
    if limit:
        zot_items = zot_items[:limit]
    zot_items_data = [item["data"] for item in zot_items]
    local_items: Sequence[Item] = []
    local_items, _ = read_db_items(session, current_user, skip, limit)
    if reload:
        [delete_item(session, current_user, id=item.id) for item in local_items]
        local_items = []
    local_keys = [item.key for item in local_items]
    new_items = []
    i =0
    for item_data in zot_items_data:
        if item_data["key"] in local_keys or item_data.get("parentItem", None) is not None:
            continue
        i += 1
        logger.info("Processing Zotero item %d/%d: %s", i, len(zot_items_data), item_data.get("title", "No Title"))

        # Extract creators before validating the item
        creators_data = item_data.pop("creators", [])

        # Create the item (without creators in the data)
        item = Item.model_validate(item_data, update={"owner_id": current_user.id})
        session.add(item)
        session.flush()  # Flush to get item.id

        # Create creator records
        for creator_data in creators_data:
            creator = Creator(
                item_id=item.id,
                creatorType=creator_data.get("creatorType", "author"),
                firstName=creator_data.get("firstName", ""),
                lastName=creator_data.get("lastName", ""),
            )
            session.add(creator)

        new_items.append(item)

    session.commit()
    for item in new_items:
        session.refresh(item)
    return ItemsPublic(data=new_items, count=len(new_items))  # pyright: ignore[reportArgumentType]


@router.get("/import_file_zotero/{id}", response_model=ItemPublic)
def import_file_from_zotero(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    library_type: Literal["group", "user"] = "group",
) -> Any:
    """Import a single item from Zotero by file ID."""
    db_user = crud.get_user_by_email(session=session, email=current_user.email)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    zot = Zotero(
        user=db_user,
        library_type=library_type,
    )

    item: Item = read_item(session, current_user, id)
    zot_item = zot.item(item.key)
    if not zot_item:
        raise HTTPException(status_code=404, detail="Zotero item not found")
    if "links" not in zot_item:
        logger.warning(
            f"Zotero item {item.key} does not have links. The item is: {zot_item}",
        )
        return item
    if "attachment" not in zot_item["links"]:
        logger.warning(
            f"Zotero item {item.key} does not have an attachment link. The item links are: {zot_item['links']}",
        )
        return item
    if not zot_item["links"]["attachment"].get("href"):
        logger.warning(
            f"Zotero item {item.key} does not have a valid attachment link. The item links are: {zot_item['links']}",
        )
        return item
    file_key = str(zot_item["links"]["attachment"]["href"].split("/")[-1])
    file_path: Path = Path.cwd() / "zotero_files" / (file_key + ".pdf")
    if not file_path.is_file():
        with file_path.open("wb") as f:
            file: bytes = zot.file(file_key)
            if not isinstance(file, bytes):
                raise HTTPException(
                    status_code=400,
                    detail="Zotero file is not a valid byte stream",
                )
            if not file:
                raise HTTPException(status_code=404, detail="Zotero file not found")
            m = Magic(mime=True)
            if not m.from_buffer(file) == "application/pdf":
                logger.warning("Only PDF files can be imported from Zotero")
                return item
            # TODO: More malware checking should be done here (e.g. yara rules, and )
            f.write(file)

    updated_item = ItemUpdate(attachment=str(file_path))
    item = update_item(
        session=session,
        current_user=current_user,
        id=id,
        item_in=updated_item,
    )
    return item


@router.post("/import_file_zotero/", response_model=TasksAccepted)
def import_files_from_zotero(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 10000,
) -> Any:
    """Start background task to download attachments from Zotero.

    Returns immediately with task ID. Use /tasks/{task_id} to check status.
    """
    from app.tasks.download import download_attachments_task

    # Start background task
    task = download_attachments_task.delay(
        user_id=str(current_user.id),
        is_superuser=current_user.is_superuser,
        skip=skip,
        limit=limit,
    )
    # NOTE: random uuid for item_id since this is a batch task
    return TasksAccepted(
        data=[
            TaskRef(
                task_id=task.id,
                item_id=uuid.uuid4(),
                status="queued",
                message="Attachment download task queued",
            )
        ],
        count=1,
    )


@router.get("/files/{filename}")
async def get_file(filename: str) -> Any:
    file_path = Path.cwd() / "zotero_files" / filename
    if file_path.exists():
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="File not found")


@router.put("/{id}", response_model=ItemPublic)
def update_item(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    item_in: ItemUpdate,
) -> Any:
    """Update an item."""
    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
    update_dict = item_in.model_dump(exclude_unset=True)
    item.sqlmodel_update(update_dict)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.delete("/{id}")
def delete_item(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
) -> Message:
    """Delete an item."""
    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
    session.delete(item)
    session.commit()
    return Message(message="Item deleted successfully")


@router.post("/study_sites/", status_code=status.HTTP_202_ACCEPTED)
def start_extract_study_site(
    session: SessionDep,
    current_user: CurrentUser,
    request: ExtractStudySitesRequest,
    skip: int = 0,
    limit: int = 500,
) -> TasksAccepted:
    items: list[Item] = []
    if request.item_ids:
        # Process only the specified items
        for item_id in request.item_ids:
            item = read_item(session, current_user, item_id)
            items.append(item)
            logger.info("Queued item %s by %s for study site extraction", item.id, item.owner_id)
    else:
        # No specific items requested - fetch all items
        items.extend(read_db_items(session, current_user, skip, limit)[0])

    # Determine force behavior based on number of items
    # Single item: Always force re-extraction (delete existing and reprocess)
    # Multiple items: Skip items with existing study sites (unless explicit force=True)
    is_single_item = request.item_ids is not None and len(request.item_ids) == 1
    should_force = request.force or is_single_item

    if not should_force:
        # Only process items without a study site
        items_with_sites = [item for item in items if item.study_sites]
        items = [item for item in items if not item.study_sites]
        if items_with_sites:
            logger.info("Skipping %d items that already have study sites", len(items_with_sites))

    # Enqueue tasks
    enqueued: list[TaskRef] = []
    for item in items:
        logger.info("Enqueuing extraction task for item %s (force=%s)", item.id, should_force)
        async_result = extract_study_site_task.delay(
            item_id=str(item.id),
            user_id=str(current_user.id),
            is_superuser=bool(current_user.is_superuser),
            force=bool(should_force),
        )
        enqueued.append(
            TaskRef(
                item_id=item.id,
                task_id=async_result.id,
                status="queued",
                message="Task is queued",
            ),
        )

    return TasksAccepted(data=enqueued, count=len(enqueued))  # type: ignore


@router.get("/study_sites/{id}")
def get_study_site(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,  # noqa: A002
) -> StudySite:
    """Get study site by item ID."""
    study_site = session.get(StudySite, id)
    if not study_site:
        raise HTTPException(status_code=404, detail="StudySite not found")
    if not current_user.is_superuser and (study_site.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
    return study_site


@router.get("/study_sites/")
def get_study_sites(
    session: SessionDep,
    current_user: CurrentUser,
) -> Sequence[StudySite]:
    """Get all study sites."""
    # NOTE: Anyone can view all study sites for now
    statement = select(StudySite)
    study_sites = session.exec(statement).all()
    if not study_sites:
        raise HTTPException(status_code=404, detail="No study sites found")
    return study_sites


@router.patch("/study_sites/{id}")
def patch_study_site(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,  # noqa: A002
    study_site_in: StudySiteUpdate,
) -> StudySite:
    """Get study site by item ID."""
    study_site = session.get(StudySite, id)
    if not study_site:
        raise HTTPException(status_code=404, detail="StudySite not found")
    if not current_user.is_superuser and (study_site.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
    return crud.update_study_site(
        session=session,
        db_study_site=study_site,
        study_site_in=study_site_in,
    )


# Task Status Endpoints


@router.get("/tasks/{task_id}")
def get_task_status(
    task_id: str,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Get Celery task status by ID.

    Returns task state, progress, and result/error information.
    """
    result = AsyncResult(task_id, app=celery)

    response: dict[str, Any] = {
        "task_id": task_id,
        "state": result.state,  # Changed from 'status' to 'state' for frontend compatibility
        "status": result.status,  # Keep for backward compatibility
        "ready": result.ready(),
        "successful": result.successful() if result.ready() else None,
        "failed": result.failed() if result.ready() else None,
    }

    # Add result data if task is complete or in progress
    if result.ready():
        if result.successful():
            response["result"] = result.result
        else:
            # Task failed - include error info
            error_info = result.info
            if isinstance(error_info, dict):
                response["error"] = error_info
            else:
                response["error"] = {
                    "message": str(error_info),
                    "type": type(error_info).__name__,
                }
    else:
        # Task is still running - check for progress info
        if hasattr(result, "info") and isinstance(result.info, dict):
            response["result"] = result.info  # Progress metadata

    # Add task metadata if available
    if hasattr(result, "info") and isinstance(result.info, dict):
        response["metadata"] = result.info

    return response


@router.get("/tasks/batch/")
def get_batch_task_status(
    task_ids: Annotated[str, Query(description="Comma-separated task IDs")],
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Get status of multiple tasks.

    Provide task IDs as comma-separated query parameter. Returns
    individual task statuses and summary statistics.
    """
    ids = [tid.strip() for tid in task_ids.split(",") if tid.strip()]

    if not ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No task IDs provided",
        )

    if len(ids) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 100 tasks can be queried at once",
        )

    results: dict[str, Any] = {}

    for task_id in ids:
        result = AsyncResult(task_id, app=celery)
        task_info: dict[str, Any] = {
            "status": result.status,
            "ready": result.ready(),
        }

        # Add minimal result info
        if result.ready():
            task_info["successful"] = result.successful()
            if result.successful():
                # Include only essential result data
                task_result = result.result
                if isinstance(task_result, dict):
                    task_info["item_id"] = task_result.get("item_id")
                    task_info["study_site_count"] = task_result.get("count", 0)
                    task_info["extraction_status"] = task_result.get("status")
            else:
                task_info["error"] = "Task failed"

        results[task_id] = task_info

    # Calculate summary statistics
    statuses = [r["status"] for r in results.values()]
    ready_tasks = [r for r in results.values() if r.get("ready")]

    summary = {
        "total": len(results),
        "pending": statuses.count("PENDING"),
        "started": statuses.count("STARTED"),
        "success": statuses.count("SUCCESS"),
        "failure": statuses.count("FAILURE"),
        "retry": statuses.count("RETRY"),
        "ready": len(ready_tasks),
        "successful": sum(1 for r in ready_tasks if r.get("successful")),
        "failed": sum(1 for r in ready_tasks if not r.get("successful")),
    }

    return {
        "tasks": results,
        "summary": summary,
    }


@router.get("/tasks/summary/")
def get_extraction_summary(
    session: SessionDep,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Get summary statistics of study site extractions for current user."""
    # Total study sites for user's items
    total_sites = session.exec(
        select(func.count(StudySite.id))
        .join(Item, StudySite.item_id == Item.id)
        .where(Item.owner_id == current_user.id),
    ).one()

    # Count by extraction method
    by_method_results = session.exec(
        select(
            StudySite.extraction_method,
            func.count(StudySite.id),
        )
        .join(Item, StudySite.item_id == Item.id)
        .where(Item.owner_id == current_user.id)
        .group_by(StudySite.extraction_method),
    ).all()

    # Average confidence
    avg_confidence = session.exec(
        select(func.avg(StudySite.confidence_score))
        .join(Item, StudySite.item_id == Item.id)
        .where(Item.owner_id == current_user.id),
    ).one()

    # Average validation score
    avg_validation = session.exec(
        select(func.avg(StudySite.validation_score))
        .join(Item, StudySite.item_id == Item.id)
        .where(Item.owner_id == current_user.id),
    ).one()

    # Total items with study sites
    items_with_sites = session.exec(
        select(func.count(func.distinct(StudySite.item_id)))
        .join(Item, StudySite.item_id == Item.id)
        .where(Item.owner_id == current_user.id),
    ).one()

    # Total items owned by user
    total_items = session.exec(
        select(func.count(Item.id)).where(Item.owner_id == current_user.id),
    ).one()

    return {
        "total_study_sites": total_sites or 0,
        "total_items": total_items or 0,
        "items_with_study_sites": items_with_sites or 0,
        "coverage_percentage": round(
            (items_with_sites / total_items * 100) if total_items > 0 else 0,
            1,
        ),
        "average_confidence": round(avg_confidence or 0, 3),
        "average_validation_score": round(avg_validation or 0, 3),
        "by_extraction_method": {str(method): count for method, count in by_method_results},
    }


@router.delete("/tasks/{task_id}")
def cancel_task(
    task_id: str,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Cancel/revoke a Celery task.

    Args:
        task_id: The Celery task ID to cancel
        current_user: The authenticated user

    Returns:
        Confirmation message with task cancellation status
    """
    try:
        # Revoke the task
        # terminate=True will kill the worker process if task is running
        # signal='SIGTERM' is more graceful than SIGKILL
        celery.control.revoke(task_id, terminate=True, signal="SIGTERM")

        # Check if task was actually running or pending
        result = AsyncResult(task_id, app=celery)
        task_status = result.status

        return {
            "task_id": task_id,
            "message": "Task cancellation requested",
            "previous_status": task_status,
            "cancelled": True,
        }
    except Exception as e:
        logger.error(f"Error cancelling task {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel task: {e!s}",
        )


@router.post("/tasks/batch/cancel")
def cancel_batch_tasks(
    task_ids: Annotated[str, Query(description="Comma-separated task IDs to cancel")],
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Cancel multiple Celery tasks at once.

    Args:
        task_ids: Comma-separated list of task IDs
        current_user: The authenticated user

    Returns:
        Summary of cancellation results
    """
    ids = [tid.strip() for tid in task_ids.split(",") if tid.strip()]

    if not ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No task IDs provided",
        )

    if len(ids) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 100 tasks can be cancelled at once",
        )

    cancelled_tasks = []
    failed_tasks = []

    for task_id in ids:
        try:
            celery.control.revoke(task_id, terminate=True, signal="SIGTERM")
            cancelled_tasks.append(task_id)
        except Exception as e:
            logger.error(f"Error cancelling task {task_id}: {e}")
            failed_tasks.append({"task_id": task_id, "error": str(e)})

    return {
        "cancelled_count": len(cancelled_tasks),
        "failed_count": len(failed_tasks),
        "cancelled_tasks": cancelled_tasks,
        "failed_tasks": failed_tasks,
    }


@router.get("/{id}/extraction-results", response_model=ExtractionResultsPublic)
def get_extraction_results(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
) -> Any:
    """Get all extraction results (candidates) for an item.

    This returns ALL entities that were detected during extraction, not
    just the top 10 that were saved as StudySites.
    """
    item = session.get(Item, id)
    if not item:
        raise HTTPException(
            status_code=404,
            detail="Item not found",
        )

    # Check ownership
    if item.owner_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Not enough permissions",
        )

    # Get all extraction results ordered by rank
    statement = (
        select(ExtractionResult)
        .where(ExtractionResult.item_id == id)
        .order_by(ExtractionResult.rank)
    )
    results = session.exec(statement).all()

    # Count how many were saved as StudySites (top 10)
    top_10_count = sum(1 for r in results if r.is_saved)

    return ExtractionResultsPublic(
        data=[ExtractionResultPublic.model_validate(r) for r in results],
        count=len(results),
        top_10_count=top_10_count,
    )
