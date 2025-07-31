from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.api.deps import SessionDep
from app.crud import (
    create_relation,
    delete_relation,
    get_relation,
    get_relations,
    update_relation,
)
from app.models import RelationCreate, RelationPublic, RelationsPublic

router = APIRouter(prefix="/relations", tags=["relations"])


@router.get("/", response_model=RelationsPublic)
def read_relations(
    item_id: str | None = None,
    session: Session = Depends(SessionDep),
    skip: int = 0,
    limit: int = 100,
) -> RelationsPublic:
    relations, total = get_relations(session, item_id=item_id, skip=skip, limit=limit)
    public_relations = [RelationPublic.model_validate(r) for r in relations]
    return RelationsPublic(data=public_relations, count=total)


@router.get("/{id}", response_model=RelationPublic)
def read_relation(id: int, session: Session = Depends(SessionDep)) -> Any:
    relation = get_relation(session, id)
    if not relation:
        raise HTTPException(status_code=404, detail="Relation not found")
    return RelationPublic.model_validate(relation)


@router.post("/", response_model=RelationPublic)
def create_relation_endpoint(
    *,
    session: Session = Depends(SessionDep),
    relation_in: RelationCreate,
    item_id: str,  # pass item_id via query or request body
) -> RelationPublic:
    relation = create_relation(session, relation_in, item_id=item_id)
    return RelationPublic.model_validate(relation)


@router.put("/{id}", response_model=RelationPublic)
def update_relation_endpoint(
    *,
    id: int,
    session: Session = Depends(SessionDep),
    relation_in: RelationCreate,
) -> RelationPublic:
    updated_relation = update_relation(session, id, relation_in)
    if not updated_relation:
        raise HTTPException(status_code=404, detail="Relation not found")
    return RelationPublic.model_validate(updated_relation)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_relation_endpoint(id: int, session: Session = Depends(SessionDep)) -> None:
    success = delete_relation(session, id)
    if not success:
        raise HTTPException(status_code=404, detail="Relation not found")
