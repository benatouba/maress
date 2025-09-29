import uuid
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


class CreatorBase(SQLModel):
    creatorType: str = Field(max_length=32)
    firstName: str = Field(max_length=64)
    lastName: str = Field(max_length=64)


class Creator(CreatorBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    item_id: uuid.UUID = Field(foreign_key="item.id")
    item: Optional["Item"] = Relationship(back_populates="creators")


class CreatorCreate(CreatorBase):
    pass


class CreatorPublic(CreatorBase):
    id: int
    item_id: uuid.UUID


class CreatorsPublic(SQLModel):
    data: list[CreatorPublic]
    count: int
