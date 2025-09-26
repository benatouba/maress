import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from pydantic import EmailStr, field_serializer, field_validator
from pydantic_extra_types.coordinate import Latitude, Longitude
from sqlmodel import Column, DateTime, Enum, Field, Relationship, SQLModel, func

from app.core.security import cipher_suite
from maress_types import (
    CeleryState,
    CoordinateExtractionMethod,
    CoordinateSourceType,
    InitialTaskState,
    PaperSections,
)

if TYPE_CHECKING:
    from app.models import Item  # Avoid circular import issues for type hints


class StudySiteBase(SQLModel):
    """Database model for study site extraction results."""

    validation_score: float = 0.0
    latitude: Latitude
    longitude: Longitude  # validates -180 <= value <= 180
    confidence_score: float
    source_type: CoordinateSourceType = Field(
        description="Type of source from which the study site was extracted",
    )
    context: str
    section: PaperSections = Field(
        default=PaperSections.OTHER,
        description="Section of the paper where the study site was mentioned",
        sa_column=Column(Enum(PaperSections)),
    )
    name: str | None = Field(
        default=None,
        description="Name of the study site, if available",
        max_length=255,
    )
    extraction_method: CoordinateExtractionMethod
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), onupdate=func.now()),
    )


class StudySite(StudySiteBase, table=True):
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
    )
    item: Optional["Item"] = Relationship(  # pyright: ignore[reportDeprecated]
        back_populates="study_site",
        sa_relationship_kwargs={"uselist": False},
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id",
        nullable=True,
        ondelete="SET NULL",
    )


class StudySiteUpdate(StudySiteBase):
    validation_score: float = 0.0
    latitude: Latitude
    longitude: Longitude  # validates -180 <= value <= 180
    confidence_score: float
    source_type: CoordinateSourceType = Field(
        description="Type of source from which the study site was extracted",
    )
    context: str
    section: PaperSections
    extraction_method: CoordinateExtractionMethod


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)
    zotero_id: str | None = Field(default=None, max_length=32)
    enc_zotero_api_key: str | None = Field(
        default=None,
        alias="zotero_api_key",
        description="Your Zotero API key. It will be encrypted for security",
    )

    @field_validator("enc_zotero_api_key", mode="before")
    @classmethod
    def encrypt_api_key(cls, v: str | None) -> str | None:
        """Encrypt API key before storing."""
        if v is None or v == "":
            return None
        if v.startswith("gAAAAAB"):  # Not already encrypted
            return cipher_suite.encrypt(v.encode()).decode()
        return v

    @field_serializer("enc_zotero_api_key", when_used="json")
    def serialize_api_key(self, value: str | None) -> str | None:
        """Return masked value in JSON responses."""
        return "****" if value else None

    def get_zotero_api_key(self) -> str | None:
        """Decrypt and return the actual API key."""
        if not self.enc_zotero_api_key:
            return None
        try:
            return cipher_suite.decrypt(self.enc_zotero_api_key.encode()).decode()
        except Exception:
            return None


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=40)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=40)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # pyright: ignore[reportIncompatibleVariableOverride]
    password: str | None = Field(default=None, min_length=8, max_length=40)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)
    zotero_id: str | None = Field(default=None, max_length=32)
    enc_zotero_api_key: str | None = Field(default=None)


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
        back_populates="owner",
        cascade_delete=True,
    )


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


class ItemTagLink(SQLModel, table=True):
    item_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="item.id",
        primary_key=True,
    )
    tag_id: int | None = Field(default=None, foreign_key="tag.id", primary_key=True)


class TagBase(SQLModel):
    name: str = Field(max_length=64)


class Tag(TagBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, max_length=64)
    items: list["Item"] = Relationship(back_populates="tags", link_model=ItemTagLink)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id",
        nullable=True,
        ondelete="SET NULL",
    )
    owner: User | None = Relationship(back_populates="tags")


class TagCreate(TagBase):
    item_ids: list[uuid.UUID] = Field(default_factory=list)


class TagPublic(TagBase):
    id: int
    owner_id: uuid.UUID
    items: list["ItemSummary"] | None = None


class TagsPublic(SQLModel):
    data: list[TagPublic]
    count: int


class ItemSummary(SQLModel):
    id: uuid.UUID
    name: str  # or whatever fields you want to expose


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


# class AuthorBase(SQLModel):
#     full_name: str = Field(min_length=3, max_length=255)
#     initials: str = Field(min_length=2, max_length=32)
#     institutions: list[str] = Field(sa_column=Column(postgresql.ARRAY(String())))
#
#
# class ItemAuthorLink(SQLModel, table=True):
#     item_id: uuid.UUID | None = Field(
#         default=None,
#         foreign_key="item.id",
#         primary_key=True,
#     )
#     author_id: uuid.UUID | None = Field(
#         default=None,
#         foreign_key="author.id",
#         primary_key=True,
#     )
#
#
# class AuthorCreate(SQLModel):
#     full_name: str = Field(min_length=3, max_length=255)
#     institutions: list[str] = Field(sa_column=Column(postgresql.ARRAY(String())))
#
#
# class Author(AuthorBase, table=True):
#     id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
#     items: list["Item"] = Relationship(
#         back_populates="authors",
#         link_model=ItemAuthorLink,
#     )


# Shared properties
class ItemBase(SQLModel):
    title: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=255)
    version: int | None = Field(default=None, ge=1)
    itemType: str = Field(min_length=1, max_length=64)
    abstractNote: str = Field(default="", min_length=0, max_length=8192)
    publicationTitle: str = Field(default="", min_length=0, max_length=255)
    volume: str | None = Field(default=None, max_length=32)
    issue: str | None = Field(default=None, max_length=32)
    pages: str | None = Field(default=None, max_length=32)
    date: str | None = Field(default=None, max_length=20)
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
    dateAdded: datetime | None = Field(default_factory=lambda: datetime.now(UTC))
    dateModified: datetime | None = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column(DateTime(timezone=True), onupdate=func.now()),
    )
    attachment: str | None = Field(default=None, max_length=512)

    # get datetime of string if type of dateAdded or dateModified is str
    @classmethod
    def model_validate(cls, obj, **kwargs):
        if isinstance(obj, dict):
            if "dateAdded" in obj and isinstance(obj["dateAdded"], str):
                obj["dateAdded"] = datetime.fromisoformat(obj["dateAdded"])
            if "dateModified" in obj and isinstance(obj["dateModified"], str):
                obj["dateModified"] = datetime.fromisoformat(obj["dateModified"])
        return super().model_validate(obj, **kwargs)


# Properties to receive on item creation
class ItemCreate(ItemBase):
    key: str = Field(min_length=8, max_length=8, regex="^[A-Z0-9]{8}$", index=True)


class ItemUpdate(SQLModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)
    abstractNote: str | None = Field(default=None, min_length=0, max_length=8192)
    publicationTitle: str | None = Field(default=None, min_length=0, max_length=255)
    volume: str | None = Field(default=None, max_length=32)
    issue: str | None = Field(default=None, max_length=32)
    pages: str | None = Field(default=None, max_length=32)
    date: str | None = Field(default=None, max_length=20)
    series: str | None = Field(default=None, max_length=128)
    seriesTitle: str | None = Field(default=None, max_length=128)
    seriesText: str | None = Field(default=None, max_length=255)
    journalAbbreviation: str | None = Field(default=None, max_length=64)
    language: str | None = Field(default=None, max_length=8)
    doi: str | None = Field(default=None, max_length=128, alias="DOI")
    issn: str | None = Field(default=None, max_length=32, alias="ISSN")
    shortTitle: str | None = Field(default=None, max_length=255)
    url: str | None = Field(default=None, max_length=512)
    archive: str | None = Field(default=None, max_length=128)
    archiveLocation: str | None = Field(default=None, max_length=255)
    libraryCatalog: str | None = Field(default=None, max_length=255)
    callNumber: str | None = Field(default=None, max_length=64)
    rights: str | None = Field(default=None, max_length=255)
    extra: str | None = Field(default=None, max_length=255)
    attachment: str | None = Field(default=None, max_length=512)
    model_config = {
        "extra": "forbid",  # reject unapproved keys
        "populate_by_name": True,  # accept either alias or field name (e.g., DOI or doi)
    }


# Database model, database table inferred from class name
class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id",
        nullable=False,
        ondelete="CASCADE",
    )
    owner: User | None = Relationship(back_populates="items")
    tags: list[Tag] = Relationship(back_populates="items", link_model=ItemTagLink)
    # authors: list[Author] = Relationship(
    #     back_populates="items",
    #     link_model=ItemAuthorLink,
    # )
    collections: list[Collection] = Relationship(back_populates="item")
    accessDate: str | None = Field(default=None, max_length=32)  # ISO-format
    creators: list[Creator] = Relationship(back_populates="item")
    relations: list[Relation] = Relationship(back_populates="item")
    study_site_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="studysite.id",
        unique=True,
    )
    study_site: StudySite | None = Relationship(back_populates="item")
    key: str = Field(min_length=8, max_length=8, regex="^[A-Z0-9]{8}$", index=True)


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    study_site_id: uuid.UUID | None
    study_site: StudySite | None


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


class TaskRef(SQLModel):
    """Model representing a reference to an asynchronous task.

    The task will be autodiscovered and handled by celery workers.
    """

    # Target domain entity the task operates on
    item_id: uuid.UUID = Field(description="Target Item ID")
    # Celery AsyncResult.id
    task_id: str = Field(description="Celery task identifier")
    # Initial server-side assessment at enqueue time
    status: InitialTaskState = Field(
        default="queued",
        description="Initial enqueue assessment for 202 responses",
    )
    # Optional per-task note (e.g., reason when skipped)
    message: str | None = Field(default=None, description="Optional reason")


class TasksAccepted(SQLModel):
    """Model representing a batch of accepted tasks."""

    data: list[TaskRef]
    count: int


class TaskStatus(SQLModel):
    """Model representing the status of an asynchronous task."""

    task_id: str = Field(description="Celery task identifier")
    task_status: CeleryState = Field(description="Celery task state")
    task_result: ItemPublic | None = Field(
        default=None,
        description="Result payload if available; omitted/None in most states",
    )
