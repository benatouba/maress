# pyright: reportAny=false
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from pydantic_extra_types.coordinate import Latitude, Longitude  # noqa: TC002
from sqlmodel import Column, DateTime, Enum, Field, Relationship, SQLModel, func

from maress_types import (
    CoordinateExtractionMethod,
    CoordinateSourceType,
    PaperSections,
)

from .factories import timestamp_field

if TYPE_CHECKING:
    from app.models.items import Item


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


class LocationBase(SQLModel):
    """Database model (base) for geographic locations."""

    created_at: datetime = timestamp_field()
    updated_at: datetime = timestamp_field(onupdate_now=True)
    latitude: Latitude
    longitude: Longitude  # validates -180 <= value <= 180


class Location(LocationBase, table=True):
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
    )
    study_sites: list[StudySite] = Relationship(back_populates="location")


class LocationPublic(LocationBase):
    id: uuid.UUID
    study_sites: list[StudySitePublic]


class LocationsPublic(SQLModel):
    data: list[LocationPublic]
    count: int


class LocationUpdate(LocationBase):
    latitude: Latitude
    longitude: Longitude  # validates -180 <= value <= 180


class LocationCreate(LocationBase):
    pass
