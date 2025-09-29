import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep
from app.models.collections import (
    Collection,
    CollectionCreate,
    CollectionPublic,
    CollectionsPublic,
)

router = APIRouter(prefix="/collections", tags=["collections"])

@router.get("/")
def read_collections(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 100
) -> CollectionsPublic:
    """Retrieve collections."""
    if current_user.is_superuser:
        count_statement = select(func.count()).select_from(Collection)
        count = session.exec(count_statement).one()
        statement = select(Collection).offset(skip).limit(limit)
        items = session.exec(statement).all()
    else:
        count_statement = (
            select(func.count())
            .select_from(Collection)
            .where(Collection.owner_id == current_user.id)
        )
        count = session.exec(count_statement).one()
        statement = (
            select(Collection)
            .where(Collection.owner_id == current_user.id)
            .offset(skip)
            .limit(limit)
        )
        items = session.exec(statement).all()
    return CollectionsPublic(data=items, count=count)  # pyright: ignore[reportArgumentType]


@router.get("/{id}", response_model=CollectionPublic)
def read_collection(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """Get collection by ID."""
    item = session.get(Collection, id)
    if not item:
        raise HTTPException(status_code=404, detail="Collection not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
    return item


@router.post("/")
def create_collection(
    *, session: SessionDep, current_user: CurrentUser, item_in: CollectionCreate
) -> CollectionPublic:
    """Create new collection."""
    item = Collection.model_validate(item_in, update={"owner_id": current_user.id})
    session.add(item)
    session.commit()
    session.refresh(item)
    return item
