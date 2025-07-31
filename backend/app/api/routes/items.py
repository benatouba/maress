import uuid
from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.models import Item, ItemCreate, ItemPublic, ItemsPublic, ItemUpdate, Message
from app.services import Zotero
from maress_types import ZoteroItemList

router = APIRouter(prefix="/items", tags=["items"])


def read_zotero_items(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 100
) -> tuple[Sequence[Item], int]:
    """Helper function to retrieve items with pagination."""
    if current_user.is_superuser:
        count_statement = select(func.count()).select_from(Item)
        count = session.exec(count_statement).one()
        statement = select(Item).offset(skip).limit(limit)
        items = session.exec(statement).all()
    else:
        count_statement = (
            select(func.count())
            .select_from(Item)
            .where(Item.owner_id == current_user.id)
        )
        count = session.exec(count_statement).one()
        statement = (
            select(Item)
            .where(Item.owner_id == current_user.id)
            .offset(skip)
            .limit(limit)
        )
        items = session.exec(statement).all()
    return items, count


@router.get("/")
def read_items(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 10
) -> ItemsPublic:
    """Retrieve items."""
    items, count = read_zotero_items(session, current_user, skip, limit)
    return ItemsPublic(data=items, count=count)  # pyright: ignore[reportArgumentType]


@router.get("/{id}", response_model=ItemPublic)
def read_item(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """Get item by ID."""
    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
    return item


@router.post("/", response_model=ItemPublic)
def create_item(
    *, session: SessionDep, current_user: CurrentUser, item_in: ItemCreate
) -> Any:
    """Create new item."""
    item = Item.model_validate(item_in, update={"owner_id": current_user.id})
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.get("/import_from_zotero/")
def import_zotero_items(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 10
):
    zot = Zotero(
        library_id=settings.ZOTERO_USER_ID,
        library_type=settings.ZOTERO_LIBRARY_TYPE,
        api_key=settings.ZOTERO_API_KEY,
    )
    # TODO: handle pagination properly and get all items, not just top-level
    zot_items: ZoteroItemList = zot.collection_items("AQXEVQ8C", limit=limit, start=skip)
    zot_items_data = [item["data"] for item in zot_items]
    local_items, _ = read_zotero_items(session, current_user, skip, limit)
    local_keys = [item.key for item in local_items]
    new_items = [
        Item.model_validate(item, update={"owner_id": current_user.id})
        for item in zot_items_data
        if item["key"] not in local_keys
    ]
    # if not new_items:
    #     return Message(message="No new items to import from Zotero")
    session.add_all(new_items)
    session.commit()
    for item in new_items:
        session.refresh(item)
    return ItemsPublic(data=new_items, count=len(new_items))  # pyright: ignore[reportArgumentType]

def import_file_from_zotero(
    session: SessionDep, current_user: CurrentUser, file_id: str
) -> ItemPublic:
    """Import a single item from Zotero by file ID."""
    zot = Zotero(
        library_id=settings.ZOTERO_USER_ID,
        library_type=settings.ZOTERO_LIBRARY_TYPE,
        api_key=settings.ZOTERO_API_KEY,
    )
    zot_item = zot.item(file_id)
    if not zot_item:
        raise HTTPException(status_code=404, detail="Zotero item not found")
    item_data = zot_item["data"]
    item = Item.model_validate(item_data, update={"owner_id": current_user.id})
    session.add(item)
    session.commit()
    session.refresh(item)
    return item

@router.put("/{id}", response_model=ItemPublic)
def update_item(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    item_in: ItemUpdate,
    create_item,
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
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
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
