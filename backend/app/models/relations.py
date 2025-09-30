import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

from .factories import timestamp_field

if TYPE_CHECKING:
    from app.models.items import Item


class RelationBase(SQLModel):
    created_at: datetime = timestamp_field()
    updated_at: datetime = timestamp_field(onupdate_now=True)
    key: str = Field(max_length=255)
    value: str = Field(max_length=255)


class Relation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    item_id: uuid.UUID = Field(foreign_key="item.id")
    item: Optional["Item"] = Relationship(back_populates="relations")


class RelationCreate(RelationBase):
    pass


class RelationPublic(RelationBase):
    id: int
    item_id: uuid.UUID


class RelationsPublic(SQLModel):
    data: list[RelationPublic]
    count: int
