import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from app.models.links import ItemTagLink

from .factories import timestamp_field

if TYPE_CHECKING:
    from app.models.items import Item, ItemSummary
    from app.models.users import User


class TagBase(SQLModel):
    name: str = Field(max_length=64)


class Tag(TagBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, max_length=64)
    items: list["Item"] = Relationship(back_populates="tags", link_model=ItemTagLink)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id",
    )
    owner: "User" = Relationship(back_populates="tags")
    created_at: datetime = timestamp_field()
    updated_at: datetime = timestamp_field(onupdate_now=True)


class TagCreate(TagBase):
    item_ids: list[uuid.UUID] = Field(default_factory=list)


class TagPublic(TagBase):
    id: int
    owner_id: uuid.UUID
    items: list["ItemSummary"] | None = None


class TagsPublic(SQLModel):
    data: list[TagPublic]
    count: int
