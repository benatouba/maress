import uuid
from datetime import UTC, datetime
from typing import Optional

from pydantic_extra_types.coordinate import Latitude, Longitude  # noqa: TC002
from sqlmodel import Column, DateTime, Enum, Field, Relationship, SQLModel, func

from maress_types import (
    CoordinateExtractionMethod,
    CoordinateSourceType,
    PaperSections,
)



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
    section: PaperSections = Field(
        default=PaperSections.OTHER,
        description="Section of the paper where the study site was mentioned",
        sa_column=Column(Enum(PaperSections)),
    )

    extraction_method: CoordinateExtractionMethod
