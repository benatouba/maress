import logging
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse
from magic import Magic
from sqlalchemy import BinaryExpression, ColumnElement
from sqlmodel import col, func, or_, select

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.models.items import (
    Item,
    ItemCreate,
    ItemPublic,
    ItemsPublic,
    ItemUpdate,
)
from app.models.messages import Message
from app.models.study_sites import StudySite
from app.models.tags import Tag
from app.models.tasks import TaskRef, TasksAccepted
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
    if current_user.is_superuser:
        count_statement = select(func.count()).select_from(Item)
        count = session.exec(count_statement).one()
        statement = select(Item).offset(skip).limit(limit)
        items = session.exec(statement).all()
    else:
        count_statement = (
            select(func.count()).select_from(Item).where(Item.owner_id == current_user.id)
        )
        count = session.exec(count_statement).one()
        statement = select(Item).where(Item.owner_id == current_user.id).offset(skip).limit(limit)
        items = session.exec(statement).all()
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
    item = session.get(Item, id)
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
    limit: int = 500,
    *,
    reload: bool = False,
    library_type: Literal["group", "user"] = "user",
):
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
        batch: ZoteroItemList = zot.collection_items("AQXEVQ8C", start=start)  # pyright: ignore[reportUnknownMemberType]
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
    new_items = [
        Item.model_validate(item, update={"owner_id": current_user.id})
        for item in zot_items_data
        if item["key"] not in local_keys and item["itemType"] not in ["note", "attachment"]
    ]
    # if not new_items:
    #     return Message(message="No new items to import from Zotero")
    session.add_all(new_items)
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


@router.get("/import_file_zotero/", response_model=ItemsPublic)
def import_files_from_zotero(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 10,
) -> Any:
    items, _ = read_db_items(session, current_user, skip, limit)
    for item in items:
        if item.attachment:
            continue
        if Path(item.attachment or "").is_file():
            continue
        db_item = import_file_from_zotero(
            session=session,
            current_user=current_user,
            id=item.id,
        )
        if not db_item:
            raise HTTPException(
                status_code=404,
                detail=f"Item {item.id} not found in Zotero",
            )
    items, count = read_db_items(session, current_user, skip, limit)
    return ItemsPublic(data=items, count=count)  # pyright: ignore[reportArgumentType]


@router.get("/files/{filename}")
async def get_file(filename: str) -> Any:  # noqa: ANN401
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
    id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 500,
    *,
    force: bool = False,
) -> TasksAccepted:
    items: list[Item] = []
    if id:
        item = read_item(session, current_user, id)
        items.append(item)
    else:
        items.extend(read_db_items(session, current_user, skip, limit)[0])

    if not force:
        # Only process items without a study site
        items = [item for item in items if not item.study_sites]

    # Enqueue tasks
    enqueued: list[TaskRef] = []
    for item in items:
        async_result = extract_study_site_task.delay(
            item_id=str(item.id),
            user_id=str(current_user.id),
            is_superuser=bool(current_user.is_superuser),
            force=bool(force),
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
    statement = select(StudySite).where(StudySite.owner_id == current_user.id)
    if not current_user.is_superuser:
        statement = statement.where(StudySite.owner_id == current_user.id)
    study_sites = session.exec(statement).all()
    if not study_sites:
        raise HTTPException(status_code=404, detail="No study sites found")
    return study_sites


@router.patch("/study_sites/{id}")
def patch_study_site(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,  # noqa: A002
    study_site_in: dict[str, Any],
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
