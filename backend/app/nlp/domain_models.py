from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator


class GeoEntity(BaseModel):
    """Immutable geo-referenced entity with context and metadata."""

    model_config = ConfigDict(frozen=True)  # pyright: ignore[reportUnannotatedClassAttribute]

    text: str = Field(..., min_length=1, description="Entity text")
    entity_type: str = Field(
        ...,
        description="Type: COORDINATE, SPATIAL_RELATION, LOC, GPE",
    )
    context: str = Field(..., description="Surrounding text context")
    section: str = Field(..., description="Document section name")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    start_char: int = Field(..., ge=0, description="Start position in text")
    end_char: int = Field(..., ge=0, description="End position in text")
    coordinates: tuple[float, float] | None = Field(
        default=None,
        description="Parsed (lat, lon) if available",
    )

    @field_validator("end_char")
    @classmethod
    def validate_positions(cls, v: int, info) -> int:
        """Ensure end_char > start_char."""
        if "start_char" in info.data and v <= info.data["start_char"]:
            msg = "end_char must be greater than start_char"
            raise ValueError(msg)
        return v

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with separated lat/lon."""
        return {
            "text": self.text,
            "type": self.entity_type,
            "section": self.section,
            "context": self.context,
            "confidence": self.confidence,
            "latitude": self.coordinates[0] if self.coordinates else None,
            "longitude": self.coordinates[1] if self.coordinates else None,
        }

class ExtractionMetadata(BaseModel):
    """Metadata for extraction process."""

    total_sections_processed: int
    average_text_quality: float
    section_quality_scores: dict[str, dict[str, float]] = Field(default_factory=dict)
    total_entities: int
    coordinates: int
    clusters: int
    locations: int

class ExtractionResult(BaseModel):
    """Complete extraction result with metadata."""

    pdf_path: Path
    entities: list[GeoEntity]
    total_sections_processed: int
    extraction_metadata: ExtractionMetadata
    doc: Any  = Field(..., description="Processed spaCy Doc object")  # pyright: ignore[reportAny]
    title: str | None = None
    cluster_info: dict[str, int]  # or Dict[str, int]
    average_text_quality: float
    section_quality_scores: dict

    def get_high_confidence_entities(self, threshold: float = 0.8) -> list[GeoEntity]:
        """Filter entities by confidence threshold."""
        return [e for e in self.entities if e.confidence >= threshold]

    def get_entities_with_coordinates(self) -> list[GeoEntity]:
        """Get only entities with explicit coordinates."""
        return [e for e in self.entities if e.coordinates is not None]

    def to_dataframe(self) -> pd.DataFrame:
        """Convert to pandas DataFrame for analysis."""
        return pd.DataFrame([e.to_dict() for e in self.entities])
