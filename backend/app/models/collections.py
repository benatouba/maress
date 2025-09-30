# pyright: reportAny=false, reportUndefinedVariable=false, reportDeprecated=false
import uuid
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.items import Item
    from app.models.users import User


class CollectionBase(SQLModel):
    name: str = Field(max_length=64)


class Collection(CollectionBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    item_id: uuid.UUID = Field(foreign_key="item.id")
    item: Optional["Item"] = Relationship(back_populates="collections")
    owner_id: uuid.UUID = Field(foreign_key="user.id")
    owner: Optional["User"] = Relationship(back_populates="collections")


class CollectionCreate(CollectionBase):
    pass


# Properties to return via API, id is always required
class CollectionPublic(CollectionBase):
    id: uuid.UUID
    owner_id: uuid.UUID


class CollectionsPublic(SQLModel):
    data: list[CollectionPublic]
    count: int
