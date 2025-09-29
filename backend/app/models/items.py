"""Item models."""
# pyright: reportAny=false

import uuid
from datetime import UTC, datetime

from sqlmodel import Column, DateTime, Field, Relationship, SQLModel, func

from app.models.collections import Collection
from app.models.creators import Creator
from app.models.links import ItemTagLink
from app.models.relations import Relation
from app.models.study_sites import StudySite
from app.models.tags import Tag
from app.models.users import User


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


class ItemSummary(SQLModel):
    id: uuid.UUID
    name: str  # or whatever fields you want to expose
