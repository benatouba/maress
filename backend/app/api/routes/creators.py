from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.api.deps import SessionDep
from app.crud import (
    create_creator,
    delete_creator,
    get_creator,
    get_creators,
    update_creator,
)
from app.models.creators import CreatorCreate, CreatorPublic, CreatorsPublic

router = APIRouter(prefix="/creators", tags=["creators"])


@router.get("/", response_model=CreatorsPublic)
def read_creators(
    item_id: str | None = None,
    session: Session = Depends(SessionDep),
    skip: int = 0,
    limit: int = 100,
) -> CreatorsPublic:
    creators, total = get_creators(session, item_id=item_id, skip=skip, limit=limit)
    public_creators = [CreatorPublic.model_validate(c) for c in creators]
    return CreatorsPublic(data=public_creators, count=total)


@router.get("/{id}", response_model=CreatorPublic)
def read_creator(id: int, session: Session = Depends(SessionDep)) -> Any:
    creator = get_creator(session, id)
    if not creator:
        raise HTTPException(status_code=404, detail="Creator not found")
    return CreatorPublic.model_validate(creator)


@router.post("/", response_model=CreatorPublic)
def create_creator_endpoint(
    *,
    session: Session = Depends(SessionDep),
    creator_in: CreatorCreate,
    item_id: str,  # Typically passed as query param or in request body
) -> CreatorPublic:
    creator = create_creator(session, creator_in, item_id=item_id)
    return CreatorPublic.model_validate(creator)


@router.put("/{id}", response_model=CreatorPublic)
def update_creator_endpoint(
    *, id: int, session: Session = Depends(SessionDep), creator_in: CreatorCreate
) -> CreatorPublic:
    updated_creator = update_creator(session, id, creator_in)
    if not updated_creator:
        raise HTTPException(status_code=404, detail="Creator not found")
    return CreatorPublic.model_validate(updated_creator)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_creator_endpoint(id: int, session: Session = Depends(SessionDep)) -> None:
    success = delete_creator(session, id)
    if not success:
        raise HTTPException(status_code=404, detail="Creator not found")
