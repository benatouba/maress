from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, SessionDep
from app.crud import create_tag, delete_tag, get_tag, get_tags, update_tag
from app.models import TagCreate, TagPublic, TagsPublic

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("/")
def read_tags(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> TagsPublic:
    if current_user.is_superuser:
        tags, total = get_tags(session, skip=skip, limit=limit)
    else:
        tags, total = get_tags(
            session, owner_id=current_user.id, skip=skip, limit=limit
        )
    public_tags = [TagPublic.model_validate(tag) for tag in tags]
    return TagsPublic(data=public_tags, count=total)


@router.get("/{id}", response_model=TagPublic)
def read_tag(id: int, session: SessionDep, current_user: CurrentUser):
    tag = get_tag(session, id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    if not current_user.is_superuser and tag.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return TagPublic.model_validate(tag)


@router.post("/", response_model=TagPublic)
def create_tag_endpoint(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    tag_in: TagCreate,
):
    tag = create_tag(session, tag_in, owner_id=current_user.id)
    return TagPublic.model_validate(tag)


@router.put("/{id}", response_model=TagPublic)
def update_tag_endpoint(
    *,
    id: int,
    session: SessionDep,
    current_user: CurrentUser,
    tag_in: TagCreate,
):
    try:
        tag = update_tag(session, id, tag_in, owner_id=current_user.id)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    return TagPublic.model_validate(tag)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag_endpoint(
    *,
    id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> None:
    try:
        success = delete_tag(session, id, owner_id=current_user.id)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    if not success:
        raise HTTPException(status_code=404, detail="Tag not found")
    return None
