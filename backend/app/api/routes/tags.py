"""API routes for managing tags."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, SessionDep
from app.crud import create_tag, delete_tag, get_tag, get_tags, update_tag
from app.models import TagCreate, TagPublic, TagsPublic

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("/", response_model=TagsPublic)
def read_tags(  # noqa: D103
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
):
    if current_user.is_superuser:
        tags, total = get_tags(session, skip=skip, limit=limit)
    else:
        tags, total = get_tags(
            session,
            owner_id=current_user.id,
            skip=skip,
            limit=limit,
        )
    public_tags = [TagPublic.model_validate(tag) for tag in tags]
    return TagsPublic(data=public_tags, count=total)


@router.get("/{tag_id}", response_model=TagPublic)
def read_tag(tag_id: int, session: SessionDep, current_user: CurrentUser) -> TagPublic:  # noqa: D103
    tag = get_tag(session, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    if not current_user.is_superuser and tag.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return TagPublic.model_validate(tag)


@router.post("/", response_model=TagPublic)
def create_tag_endpoint(  # noqa: D103
    *,
    session: SessionDep,
    current_user: CurrentUser,
    tag_in: TagCreate,
) -> TagPublic:
    tag = create_tag(session, tag_in, owner_id=current_user.id)
    return TagPublic.model_validate(tag)


@router.put("/{tag_id}", response_model=TagPublic)
def update_tag_endpoint(  # noqa: D103
    *,
    tag_id: int,
    session: SessionDep,
    current_user: CurrentUser,
    tag_in: TagCreate,
) -> TagPublic:
    try:
        tag = update_tag(session, tag_id, tag_in, owner_id=current_user.id)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    return TagPublic.model_validate(tag)


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag_endpoint(  # noqa: ANN201, D103
    *,
    tag_id: int,
    session: SessionDep,
    current_user: CurrentUser,
):
    try:
        success = delete_tag(session, tag_id, owner_id=current_user.id)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    if not success:
        raise HTTPException(status_code=404, detail="Tag not found")


@router.post("/{tag_id}/items/{item_id}", response_model=TagPublic)
def add_item_to_tag(  # noqa: D103
    *,
    tag_id: int,
    item_id: str,
    session: SessionDep,
    current_user: CurrentUser,
) -> TagPublic:
    """Add an item to a tag."""
    from uuid import UUID
    from app.crud import get_item

    tag = get_tag(session, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    if not current_user.is_superuser and tag.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    # Get the item
    try:
        item_uuid = UUID(item_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid item ID format")

    item = get_item(session, item_uuid)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and item.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    # Add item to tag if not already present
    if item not in tag.items:
        tag.items.append(item)
        session.add(tag)
        session.commit()
        session.refresh(tag)

    return TagPublic.model_validate(tag)


@router.delete("/{tag_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_item_from_tag(  # noqa: ANN201, D103
    *,
    tag_id: int,
    item_id: str,
    session: SessionDep,
    current_user: CurrentUser,
):
    """Remove an item from a tag."""
    from uuid import UUID
    from app.crud import get_item

    tag = get_tag(session, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    if not current_user.is_superuser and tag.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    # Get the item
    try:
        item_uuid = UUID(item_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid item ID format")

    item = get_item(session, item_uuid)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # Remove item from tag if present
    if item in tag.items:
        tag.items.remove(item)
        session.add(tag)
        session.commit()

    return None
