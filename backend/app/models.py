import uuid
from typing import Optional

from pydantic import EmailStr
from sqlmodel import Field, Relationship, SQLModel


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=40)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=40)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore
    password: str | None = Field(default=None, min_length=8, max_length=40)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=40)
    new_password: str = Field(min_length=8, max_length=40)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    items: list["Item"] = Relationship(back_populates="owner", cascade_delete=True)
    tags: list["Tag"] = Relationship(back_populates="owner", cascade_delete=True)
    collections: list["Collection"] = Relationship(
        back_populates="owner", cascade_delete=True
    )


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


class TagBase(SQLModel):
    name: str = Field(max_length=64)


class Tag(TagBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    item_id: uuid.UUID = Field(foreign_key="item.id")
    item: Optional["Item"] = Relationship(back_populates="tags")
    owner_id: uuid.UUID = Field(foreign_key="user.id", nullable=True, ondelete="SET NULL")
    owner: User | None = Relationship(back_populates="tags")


class TagCreate(TagBase):
    pass


class TagPublic(TagBase):
    id: int
    item_id: uuid.UUID


class TagsPublic(SQLModel):
    data: list[TagPublic]
    count: int


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


class CollectionBase(SQLModel):
    name: str = Field(max_length=64)


class Collection(CollectionBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    item_id: uuid.UUID = Field(foreign_key="item.id")
    item: Optional["Item"] = Relationship(back_populates="collections")
    owner_id: uuid.UUID = Field(foreign_key="user.id", ondelete="CASCADE")
    owner: User | None = Relationship(back_populates="collections")


class CollectionCreate(CollectionBase):
    pass


# Properties to return via API, id is always required
class CollectionPublic(CollectionBase):
    id: uuid.UUID
    owner_id: uuid.UUID


class CollectionsPublic(SQLModel):
    data: list[CollectionPublic]
    count: int


class RelationBase(SQLModel):
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


# Shared properties
class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)
    version: int = Field(ge=1)
    itemType: str = Field(min_length=1, max_length=64)
    abstractNote: str = Field(default="", min_length=0, max_length=8192)
    publicationTitle: str = Field(default="", min_length=0, max_length=255)
    volume: str | None = Field(default=None, max_length=32)
    issue: str | None = Field(default=None, max_length=32)
    pages: str | None = Field(default=None, max_length=32)
    date: str | None = Field(default=None, min_length=4, max_length=10)
    series: str = Field(default="", max_length=128)
    seriesTitle: str = Field(default="", max_length=128)
    seriesText: str = Field(default="", max_length=255)
    journalAbbreviation: str | None = Field(default=None, max_length=64)
    language: str | None = Field(default=None, max_length=8)
    doi: str | None = Field(default=None, max_length=128, alias="DOI")
    issn: str | None = Field(default=None, max_length=32, alias="ISSN")
    shortTitle: str = Field(default="", max_length=255)
    url: str = Field(default="", max_length=512)
    archive: str = Field(default="", max_length=128)
    archiveLocation: str = Field(default="", max_length=255)
    libraryCatalog: str | None = Field(default=None, max_length=255)
    callNumber: str = Field(default="", max_length=64)
    rights: str | None = Field(default=None, max_length=255)
    extra: str = Field(default="", max_length=255)
    dateAdded: str = Field(min_length=20, max_length=32)
    dateModified: str = Field(min_length=20, max_length=32)
    key: str = Field(min_length=8, max_length=8, regex="^[A-Z0-9]{8}$", index=True)


# Properties to receive on item creation
class ItemCreate(ItemBase):
    pass


# Properties to receive on item update
class ItemUpdate(ItemBase):
    title: str | None = Field(default=None, min_length=1, max_length=255)  # type: ignore


# Database model, database table inferred from class name
class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="items")
    tags: list[Tag] = Relationship(back_populates="item")
    collections: list[Collection] = Relationship(back_populates="item")
    accessDate: str | None = Field(default=None, max_length=32)  # ISO-format
    creators: list[Creator] = Relationship(back_populates="item")
    relations: list[Relation] = Relationship(back_populates="item")


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=40)
