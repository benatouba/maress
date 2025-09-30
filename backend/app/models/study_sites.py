# pyright: reportAny=false
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from pydantic_extra_types.coordinate import Latitude, Longitude  # noqa: TC002
from sqlmodel import Column, DateTime, Enum, Field, Relationship, SQLModel, func

from maress_types import (
    CoordinateExtractionMethod,
    CoordinateSourceType,
    PaperSections,
)

if TYPE_CHECKING:
    from app.models.items import Item


class StudySiteBase(SQLModel):
    """Database model for study site extraction results."""

    confidence_score: float
    context: str
    extraction_method: CoordinateExtractionMethod
    item_id: uuid.UUID = Field(foreign_key="item.id", index=True)
    latitude: Latitude
    longitude: Longitude  # validates -180 <= value <= 180
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
    item: "Item" = Relationship(back_populates="study_sites")


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
    item_id: uuid.UUID
