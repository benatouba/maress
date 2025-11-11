import uuid
from datetime import datetime
from typing import Optional, Self

from pydantic import ConfigDict, EmailStr, computed_field, field_serializer, field_validator  # noqa: TC002
from pydantic_extra_types.coordinate import Latitude, Longitude  # noqa: TC002
from sqlmodel import Column, Enum, Field, Relationship, SQLModel

from app.core.security import cipher_suite
from app.model_factories.factories import timestamp_field
from maress_types import (
    CeleryState,
    CoordinateExtractionMethod,
    CoordinateSourceType,
    InitialTaskState,
    PaperSections,
)


class ItemTagLink(SQLModel, table=True):
    item_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="item.id",
        primary_key=True,
    )
    tag_id: int | None = Field(default=None, foreign_key="tag.id", primary_key=True)


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
    dateAdded: datetime = timestamp_field()
    dateModified: datetime = timestamp_field(onupdate_now=True)
    attachment: str | None = Field(default=None, max_length=512)

    # get datetime of string if type of dateAdded or dateModified is str
    @classmethod
    def model_validate(cls, obj, **kwargs) -> SQLModel:  # noqa: ANN001, ANN003  # pyright: ignore[reportUnknownParameterType, reportMissingParameterType, reportImplicitOverride]
        """Convert dateAdded and dateModified from string to datetime."""
        if isinstance(obj, dict):
            if "dateAdded" in obj and isinstance(obj["dateAdded"], str):
                obj["dateAdded"] = datetime.fromisoformat(obj["dateAdded"])
            if "dateModified" in obj and isinstance(obj["dateModified"], str):
                obj["dateModified"] = datetime.fromisoformat(obj["dateModified"])
        return super().model_validate(obj, **kwargs)  # pyright: ignore[reportUnknownArgumentType]


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
    model_config = {  # pyright: ignore[reportUnannotatedClassAttribute, reportAssignmentType]
        "extra": "forbid",  # reject unapproved keys
        "populate_by_name": True,  # accept either alias or field name (e.g., DOI or doi)
    }


class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id",
        nullable=False,
        ondelete="CASCADE",
    )
    owner: "User" = Relationship(back_populates="items")
    tags: list["Tag"] = Relationship(back_populates="items", link_model=ItemTagLink)
    # authors: list["Author"] = Relationship(
    #     back_populates="items",
    #     link_model=ItemAuthorLink,
    # )
    collections: list["Collection"] = Relationship(back_populates="item")
    accessDate: str | None = Field(default=None, max_length=32)  # ISO-format
    creators: list["Creator"] = Relationship(back_populates="item")
    relations: list["Relation"] = Relationship(back_populates="item")
    study_sites: list["StudySite"] | None = Relationship(
        back_populates="item",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    extraction_results: list["ExtractionResult"] | None = Relationship(
        back_populates="item",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    key: str = Field(min_length=8, max_length=8, regex="^[A-Z0-9]{8}$", index=True)


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    study_sites: list["StudySitePublic"] | None

    @field_serializer("study_sites")
    def serialize_study_sites(self, study_sites: list["StudySite"] | None, _info):
        """Serialize study sites with location data."""
        if not study_sites:
            return None
        # Pydantic computed fields automatically handle lat/lon from location
        return [StudySitePublic.model_validate(site) for site in study_sites]


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int


class ItemSummary(SQLModel):
    id: uuid.UUID
    name: str  # or whatever fields you want to expose


class LocationBase(SQLModel):
    """Database model (base) for geographic locations."""

    created_at: datetime = timestamp_field()
    updated_at: datetime = timestamp_field(onupdate_now=True)
    latitude: Latitude
    longitude: Longitude  # validates -180 <= value <= 180
    cluster_label: int | None = None


class Location(LocationBase, table=True):
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
    )
    study_sites: list["StudySite"] = Relationship(back_populates="location")


class LocationPublicSimple(LocationBase):
    """Location without nested study sites (to avoid circular references)."""
    id: uuid.UUID

class LocationPublic(LocationBase):
    id: uuid.UUID
    study_sites: list["StudySitePublic"]


class LocationsPublic(SQLModel):
    data: list[LocationPublic]
    count: int


class LocationUpdate(LocationBase):
    latitude: Latitude
    longitude: Longitude  # validates -180 <= value <= 180


class LocationCreate(LocationBase):
    pass


# Generic message
class Message(SQLModel):
    message: str


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


class StudySiteBase(SQLModel):
    """Database model for study site extraction results."""

    created_at: datetime = timestamp_field()
    updated_at: datetime = timestamp_field(onupdate_now=True)
    confidence_score: float
    context: str
    extraction_method: CoordinateExtractionMethod
    item_id: uuid.UUID = Field(foreign_key="item.id", index=True)
    validation_score: float = 0.0
    source_type: CoordinateSourceType = Field(
        description="Type of source from which the study site was extracted",
    )
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
    is_manual: bool = Field(
        default=False,
        description="True if created or modified by a human, False if automatic extraction",
        index=True,
    )
    location_id: uuid.UUID = Field(foreign_key="location.id", index=True)


class StudySite(StudySiteBase, table=True):
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
    )
    item: "Item" = Relationship(back_populates="study_sites")
    location: "Location" = Relationship(back_populates="study_sites")


class StudySiteUpdate(StudySiteBase):
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

    extraction_method: CoordinateExtractionMethod


class StudySitePublic(StudySiteBase):
    id: uuid.UUID
    item_id: uuid.UUID
    location: "LocationPublicSimple"

    model_config = ConfigDict(from_attributes=True)  # pyright: ignore[reportAssignmentType]

    # Computed fields for backward compatibility with frontend
    # These are automatically included in JSON serialization
    @computed_field  # type: ignore[misc]
    @property
    def latitude(self) -> float | None:
        """Get latitude from location relationship."""
        return self.location.latitude if self.location else None

    @computed_field  # type: ignore[misc]
    @property
    def longitude(self) -> float | None:
        """Get longitude from location relationship."""
        return self.location.longitude if self.location else None


class StudySiteCreate(StudySiteBase):
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
    )
    item_id: uuid.UUID
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    location_id: uuid.UUID | None = None

    def validate_location_or_coordinates(self) -> Self:
        """Ensure either location_id or coordinates are provided."""
        if self.location_id is None and (self.latitude is None or self.longitude is None):
            msg = "Either location_id or both latitude and longitude must be provided."
            raise ValueError(msg)
        return self


class StudySiteManualCreate(SQLModel):
    """Model for manually creating a study site via API."""

    name: str = Field(description="Name of the study site", max_length=255)
    latitude: Latitude = Field(description="Latitude coordinate")
    longitude: Longitude = Field(description="Longitude coordinate")
    context: str = Field(
        default="Manually added by user",
        description="Description or context about the study site",
    )
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    validation_score: float = Field(default=1.0, ge=0.0, le=1.0)


class StudySiteManualUpdate(SQLModel):
    """Model for manually updating a study site via API."""

    name: str | None = Field(default=None, description="Name of the study site", max_length=255)
    latitude: Latitude | None = Field(default=None, description="Latitude coordinate")
    longitude: Longitude | None = Field(default=None, description="Longitude coordinate")
    context: str | None = Field(default=None, description="Description or context")
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    validation_score: float | None = Field(default=None, ge=0.0, le=1.0)


class StudySitesPublic(SQLModel):
    """Collection of study sites."""

    data: list[StudySitePublic]
    count: int


# Extraction Results - store all candidates found during extraction
class ExtractionResultBase(SQLModel):
    """Base model for extraction results (all candidates found)."""

    name: str | None = Field(default=None, max_length=512)
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    context: str | None = Field(default=None, max_length=2048)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    extraction_method: CoordinateExtractionMethod = Field(
        sa_column=Column(Enum(CoordinateExtractionMethod)),
    )
    source_type: CoordinateSourceType = Field(
        sa_column=Column(Enum(CoordinateSourceType)),
    )
    section: PaperSections = Field(sa_column=Column(Enum(PaperSections)))
    rank: int = Field(default=0)  # Ranking position (1 = highest)
    is_saved: bool = Field(default=False)  # Whether it was saved as a StudySite


class ExtractionResult(ExtractionResultBase, table=True):
    """Extraction result - stores all candidates found during extraction.

    This model stores ALL entities found during extraction (not just top 10),
    allowing users to see what was detected and review lower-ranked results.
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    item_id: uuid.UUID = Field(foreign_key="item.id", index=True)
    item: "Item" = Relationship(back_populates="extraction_results")
    created_at: datetime = timestamp_field()


class ExtractionResultPublic(ExtractionResultBase):
    """Public extraction result with computed fields."""

    id: uuid.UUID
    item_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExtractionResultsPublic(SQLModel):
    """Collection of extraction results."""

    data: list[ExtractionResultPublic]
    count: int
    top_10_count: int  # How many of the top 10 were saved


class TagBase(SQLModel):
    name: str = Field(max_length=64)


class Tag(TagBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, max_length=64)
    items: list["Item"] = Relationship(back_populates="tags", link_model=ItemTagLink)
    owner_id: uuid.UUID = Field(foreign_key="user.id")
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
    data: list["TagPublic"]
    count: int


class TaskRef(SQLModel):
    """Model representing a reference to an asynchronous task.

    The task can be discovered and handled by celery workers.
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


class ExtractStudySitesRequest(SQLModel):
    """Request body for study site extraction endpoint."""

    item_ids: list[uuid.UUID] | None = Field(
        default=None,
        description="Optional list of specific item IDs to process. If None, processes all items.",
    )
    force: bool = Field(
        default=False,
        description="Force re-extraction even if study sites already exist",
    )


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


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class UserBase(SQLModel):
    created_at: datetime = timestamp_field()
    updated_at: datetime = timestamp_field(onupdate_now=True)
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
    full_name: str | None = Field(default=None, max_length=255)
    zotero_id: str | None = Field(default=None, max_length=32)
    enc_zotero_api_key: str | None = Field(
        default=None,
        alias="zotero_api_key",
        description="Your Zotero API key. It will be encrypted for security",
    )


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


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=40)
