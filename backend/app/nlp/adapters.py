"""Adapters for converting between new architecture and legacy models.

This module provides compatibility layers between the new SOLID
architecture and the existing API/database models.
"""

from __future__ import annotations

import uuid

from pydantic_extra_types.coordinate import Latitude, Longitude

from app.models import StudySiteCreate
from app.nlp.domain_models import ExtractionResult, GeoEntity
from app.nlp.nlp_logger import logger
from maress_types import (
    CoordinateExtractionMethod,
    CoordinateSourceType,
    PaperSections,
)


class StudySiteResultAdapter:
    """Adapter to convert ExtractionResult to StudySiteCreate models.

    This bridges the gap between the new SOLID architecture and the
    existing database models, maintaining backward compatibility.
    """

    @staticmethod
    def to_study_sites(
        result: ExtractionResult,
        item_id: uuid.UUID,
        min_confidence: float,
    ) -> list[StudySiteCreate]:
        """Convert ExtractionResult to list of StudySiteCreate.

        Args:
            result: ExtractionResult from new pipeline
            item_id: UUID of the item (paper) these sites belong to
            min_confidence: Minimum confidence threshold for inclusion

        Returns:
            List of StudySiteCreate objects ready for database insertion
        """
        study_sites: list[StudySiteCreate] = []

        # Get entities with coordinates
        entities_with_coords = result.get_entities_with_coordinates()

        # COORDINATES always create StudySites (bypass confidence threshold)
        coordinate_entities = [e for e in entities_with_coords if e.entity_type == "COORDINATE"]

        # Other entities must pass confidence threshold
        other_entities = [
            e for e in entities_with_coords
            if e.entity_type != "COORDINATE" and e.confidence >= min_confidence
        ]

        # Combine: all coordinates + high-confidence others
        high_confidence = coordinate_entities + other_entities

        logger.info(
            f"Found {len(coordinate_entities)} coordinate entities (always included), "
            f"{len(other_entities)} other high-confidence entities (threshold: {min_confidence})"
        )

        if not high_confidence and entities_with_coords:
            logger.warning(
                f"No high-confidence entities found. Adding best entity as fallback.",
            )
            # If none meet criteria, add the highest confidence one
            best_entity = max(entities_with_coords, key=lambda e: e.confidence)
            high_confidence.append(best_entity)

        # Convert each entity to StudySiteCreate
        for entity in high_confidence:
            try:
                study_site = StudySiteResultAdapter._entity_to_study_site(
                    entity,
                    item_id,
                    cluster_info=result.cluster_info,
                )
                study_sites.append(study_site)
            except Exception as e:
                logger.warning(f"Failed to convert entity to StudySite: {e}")
                continue

        logger.info(f"Converted {len(study_sites)} entities to StudySiteCreate")
        return study_sites

    @staticmethod
    def _entity_to_study_site(
        entity: GeoEntity,
        item_id: uuid.UUID,
        cluster_info: dict[str, int],
    ) -> StudySiteCreate:
        """Convert single GeoEntity to StudySiteCreate.

        Args:
            entity: GeoEntity with coordinates
            item_id: Item UUID
            cluster_info: Clustering metadata

        Returns:
            StudySiteCreate object
        """
        if not entity.coordinates:
            msg = "Entity must have coordinates"
            raise ValueError(msg)

        # Map entity type to extraction method
        extraction_method = StudySiteResultAdapter._map_extraction_method(entity)

        # Map entity type to source type
        source_type = StudySiteResultAdapter._map_source_type(entity)

        # Map section
        section = StudySiteResultAdapter._map_section(entity.section)

        # Calculate validation score based on cluster size
        validation_score = StudySiteResultAdapter._calculate_validation_score(
            entity.confidence,
            cluster_info,
        )

        # Extract name from entity text or context
        name = StudySiteResultAdapter._extract_name(entity)

        return StudySiteCreate(
            name=name,
            latitude=Latitude(entity.coordinates[0]),
            longitude=Longitude(entity.coordinates[1]),
            confidence_score=entity.confidence,
            context=entity.context[:500],  # Limit context length
            extraction_method=extraction_method,
            section=section,
            source_type=source_type,
            validation_score=validation_score,
            item_id=item_id,
        )

    @staticmethod
    def _map_extraction_method(entity: GeoEntity) -> CoordinateExtractionMethod:
        """Map entity type to extraction method."""
        if entity.entity_type == "COORDINATE":
            # Check if from table
            if "Table" in entity.context:
                return CoordinateExtractionMethod.TABLE_PARSING
            return CoordinateExtractionMethod.REGEX

        if entity.entity_type in ["LOC", "GPE", "CONTEXTUAL_LOCATION"]:
            return CoordinateExtractionMethod.GEOCODED

        if entity.entity_type == "SPATIAL_RELATION":
            return CoordinateExtractionMethod.NER

        # Default
        return CoordinateExtractionMethod.NER

    @staticmethod
    def _map_source_type(entity: GeoEntity) -> CoordinateSourceType:
        """Map entity to source type."""
        if "Table" in entity.context:
            return CoordinateSourceType.TABLE

        if entity.entity_type in ["CAPTION", "FIGURE"]:
            return CoordinateSourceType.CAPTION

        return CoordinateSourceType.TEXT

    @staticmethod
    def _map_section(section_str: str) -> PaperSections:
        """Map section string to PaperSections enum."""
        section_map = {
            "title": PaperSections.TITLE,
            "abstract": PaperSections.ABSTRACT,
            "introduction": PaperSections.INTRODUCTION,
            "methods": PaperSections.METHODS,
            "results": PaperSections.RESULTS,
            "discussion": PaperSections.DISCUSSION,
            "conclusion": PaperSections.CONCLUSION,
            "references": PaperSections.REFERENCES,
        }

        return section_map.get(section_str.lower(), PaperSections.OTHER)

    @staticmethod
    def _calculate_validation_score(
        confidence: float,
        cluster_info: dict[str, int],
    ) -> float:
        """Calculate validation score.

        Args:
            confidence: Entity confidence
            cluster_info: Clustering metadata

        Returns:
            Validation score between 0 and 1
        """
        # Base score from confidence
        score = confidence

        # Boost if part of a cluster
        if cluster_info:
            # Higher score for entities in larger clusters
            max_cluster_size = max(cluster_info.values()) if cluster_info else 1
            if max_cluster_size > 1:
                score = min(score + 0.1, 1.0)

        return round(score, 3)

    @staticmethod
    def _extract_name(entity: GeoEntity) -> str:
        """Extract name from entity.

        Args:
            entity: GeoEntity

        Returns:
            Name string
        """
        # For coordinate entities, use text
        if entity.entity_type == "COORDINATE":
            # Try to extract name from context
            context = entity.context
            # Look for patterns like "Site Name:" or "located at"
            import re

            name_pattern = r"(?:site|location|station)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)"
            match = re.search(name_pattern, context, re.IGNORECASE)
            if match:
                return match.group(1)

            # Default to coordinate text
            return f"Site at {entity.text}"

        # For location entities, use the entity text
        return entity.text[:100]  # Limit length


def get_primary_study_site(study_sites: list[StudySiteCreate]) -> StudySiteCreate | None:
    """Get the primary (highest confidence) study site.

    Args:
        study_sites: List of study sites

    Returns:
        Primary study site or None
    """
    if not study_sites:
        return None

    # Sort by confidence score (descending)
    sorted_sites = sorted(
        study_sites,
        key=lambda s: s.confidence_score,
        reverse=True,
    )

    return sorted_sites[0]
