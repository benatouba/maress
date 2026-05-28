"""Adapters for converting between new architecture and legacy models.

This module provides compatibility layers between the new SOLID
architecture and the existing API/database models.
"""

from __future__ import annotations

import re
import uuid
from typing import ClassVar

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

    EXTRACTION_VALIDATION_BONUS = {
        CoordinateExtractionMethod.MANUAL: 0.22,
        CoordinateExtractionMethod.REGEX: 0.18,
        CoordinateExtractionMethod.TABLE_PARSING: 0.16,
        CoordinateExtractionMethod.NER: 0.12,
        CoordinateExtractionMethod.GEOCODED: 0.08,
    }

    SOURCE_VALIDATION_BONUS = {
        CoordinateSourceType.MANUAL: 0.20,
        CoordinateSourceType.TABLE: 0.10,
        CoordinateSourceType.TEXT: 0.08,
        CoordinateSourceType.METADATA: 0.04,
        CoordinateSourceType.CAPTION: -0.04,
    }

    SECTION_VALIDATION_BONUS = {
        PaperSections.METHODS: 0.12,
        PaperSections.RESULTS: 0.08,
        PaperSections.ABSTRACT: 0.04,
        PaperSections.TITLE: 0.03,
        PaperSections.DISCUSSION: 0.01,
        PaperSections.CONCLUSION: 0.01,
        PaperSections.INTRODUCTION: 0.0,
        PaperSections.OTHER: 0.0,
        PaperSections.REFERENCES: -0.20,
    }

    EXTRACTION_PRIORITY = {
        CoordinateExtractionMethod.MANUAL: 5,
        CoordinateExtractionMethod.REGEX: 4,
        CoordinateExtractionMethod.TABLE_PARSING: 4,
        CoordinateExtractionMethod.NER: 3,
        CoordinateExtractionMethod.GEOCODED: 2,
    }

    SOURCE_PRIORITY = {
        CoordinateSourceType.MANUAL: 5,
        CoordinateSourceType.TABLE: 4,
        CoordinateSourceType.TEXT: 3,
        CoordinateSourceType.METADATA: 2,
        CoordinateSourceType.CAPTION: 1,
    }

    SECTION_PRIORITY = {
        PaperSections.METHODS: 4,
        PaperSections.RESULTS: 3,
        PaperSections.ABSTRACT: 2,
        PaperSections.TITLE: 2,
        PaperSections.DISCUSSION: 1,
        PaperSections.INTRODUCTION: 1,
        PaperSections.CONCLUSION: 1,
        PaperSections.OTHER: 0,
        PaperSections.REFERENCES: -1,
    }
    EXCLUDED_ENTITY_TYPES: ClassVar[set[str]] = {"BOUNDING_BOX"}
    GENERIC_COORDINATE_NAME_PREFIX: ClassVar[str] = "Site at "
    VAGUE_NAME_PREFIX_TOKENS: ClassVar[set[str]] = {
        "near",
        "around",
        "within",
        "between",
        "across",
        "along",
        "of",
        "the",
        "this",
        "that",
        "these",
        "those",
        "our",
        "their",
        "its",
    }
    VAGUE_NAME_PHRASES: ClassVar[set[str]] = {
        "study area",
        "study site",
        "study sites",
        "study region",
        "research site",
        "sampling site",
        "field site",
        "this study",
        "our study",
    }
    GENERIC_NAME_VALIDATION_PENALTY: ClassVar[float] = 0.10

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
        entities_with_coords = [
            entity
            for entity in result.get_entities_with_coordinates()
            if entity.entity_type not in StudySiteResultAdapter.EXCLUDED_ENTITY_TYPES
        ]

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

        study_sites.sort(key=StudySiteResultAdapter._study_site_sort_key, reverse=True)

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

        # Extract name from entity text or context
        name = StudySiteResultAdapter._extract_name(entity)

        rejection_reason = StudySiteResultAdapter._study_site_rejection_reason(entity, name)
        if rejection_reason is not None:
            msg = f"Skipping study-site candidate '{name}': {rejection_reason}"
            raise ValueError(msg)

        # Map entity type to extraction method
        extraction_method = StudySiteResultAdapter._map_extraction_method(entity)

        # Map entity type to source type
        source_type = StudySiteResultAdapter._map_source_type(entity)

        # Map section
        section = StudySiteResultAdapter._map_section(entity.section)

        # Calculate validation score based on cluster size
        validation_score = StudySiteResultAdapter._calculate_validation_score(
            confidence=entity.confidence,
            cluster_info=cluster_info,
            extraction_method=extraction_method,
            source_type=source_type,
            section=section,
            name=name,
        )

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

        if entity.entity_type in ["STUDY_SITE", "MULTIWORD_LOCATION"]:
            return CoordinateExtractionMethod.NER

        if entity.entity_type in [
            "WATER_BODY",
            "GEO_FEATURE",
            "ECOSYSTEM",
            "COASTAL",
            "RESEARCH_SITE",
            "CLIMATE_ZONE",
        ]:
            return CoordinateExtractionMethod.NER

        if entity.entity_type == "BOUNDING_BOX":
            return CoordinateExtractionMethod.REGEX

        # Default
        return CoordinateExtractionMethod.NER

    @staticmethod
    def _map_source_type(entity: GeoEntity) -> CoordinateSourceType:
        """Map entity to source type."""
        if "Table" in entity.context:
            return CoordinateSourceType.TABLE

        if "[IMAGE_OCR" in entity.context:
            return CoordinateSourceType.CAPTION

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
            "methodology": PaperSections.METHODS,
            "results": PaperSections.RESULTS,
            "discussion": PaperSections.DISCUSSION,
            "conclusion": PaperSections.CONCLUSION,
            "conclusions": PaperSections.CONCLUSION,
            "study_area": PaperSections.METHODS,
            "study area": PaperSections.METHODS,
            "study_site": PaperSections.METHODS,
            "study site": PaperSections.METHODS,
            "materials": PaperSections.METHODS,
            "materials and methods": PaperSections.METHODS,
            "data": PaperSections.METHODS,
            "data and methods": PaperSections.METHODS,
            "data collection": PaperSections.METHODS,
            "other": PaperSections.OTHER,
            "references": PaperSections.REFERENCES,
        }

        return section_map.get(section_str.lower(), PaperSections.OTHER)

    @staticmethod
    def _calculate_validation_score(
        confidence: float,
        cluster_info: dict[str, int],
        extraction_method: CoordinateExtractionMethod,
        source_type: CoordinateSourceType,
        section: PaperSections,
        name: str,
    ) -> float:
        """Calculate validation score.

        Args:
            confidence: Entity confidence
            cluster_info: Clustering metadata

        Returns:
            Validation score between 0 and 1
        """
        score = confidence * 0.6
        score += StudySiteResultAdapter.EXTRACTION_VALIDATION_BONUS.get(
            extraction_method,
            0.08,
        )
        score += StudySiteResultAdapter.SOURCE_VALIDATION_BONUS.get(source_type, 0.0)
        score += StudySiteResultAdapter.SECTION_VALIDATION_BONUS.get(section, 0.0)

        cluster_sizes = [
            value
            for key, value in cluster_info.items()
            if key == "largest_cluster_size" or key.startswith("cluster_")
        ]
        largest_cluster_size = max(cluster_sizes, default=0)
        if largest_cluster_size >= 2:
            score += min((largest_cluster_size - 1) * 0.03, 0.09)

        if name.startswith(StudySiteResultAdapter.GENERIC_COORDINATE_NAME_PREFIX):
            score -= StudySiteResultAdapter.GENERIC_NAME_VALIDATION_PENALTY

        return round(min(max(score, 0.0), 1.0), 3)

    @staticmethod
    def _study_site_sort_key(
        study_site: StudySiteCreate,
    ) -> tuple[float, int, int, int, float, bool]:
        """Prefer validated, explicit, methods-based study sites."""
        return (
            study_site.validation_score,
            StudySiteResultAdapter.EXTRACTION_PRIORITY.get(study_site.extraction_method, 0),
            StudySiteResultAdapter.SECTION_PRIORITY.get(study_site.section, 0),
            StudySiteResultAdapter.SOURCE_PRIORITY.get(study_site.source_type, 0),
            study_site.confidence_score,
            bool(
                study_site.name
                and not study_site.name.startswith(
                    StudySiteResultAdapter.GENERIC_COORDINATE_NAME_PREFIX,
                )
            ),
        )

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
            # Only accept clearly delimited proper names after site/location labels.
            name_pattern = re.compile(
                r"(?i:\b(?:site|location|station)\b(?:\s+name)?[:\-\s]+)"
                r"([A-Z][A-Za-z'/-]*(?:\s+(?:de|del|da|do|dos|das|of|the|la|las|los)\s+"
                r"[A-Z][A-Za-z'/-]*|\s+[A-Z][A-Za-z'/-]*){0,5})"
            )
            match = name_pattern.search(context)
            if match:
                return match.group(1)

            # Default to coordinate text
            return f"{StudySiteResultAdapter.GENERIC_COORDINATE_NAME_PREFIX}{entity.text}"

        # For location entities, use the entity text
        return entity.text[:100]  # Limit length

    @staticmethod
    def _study_site_rejection_reason(entity: GeoEntity, name: str) -> str | None:
        """Return reason when a candidate should not become a saved study site."""
        if entity.entity_type in StudySiteResultAdapter.EXCLUDED_ENTITY_TYPES:
            return "study_area_extent"

        if entity.entity_type == "COORDINATE":
            return None

        normalized_name = " ".join(name.strip().lower().split())
        if not normalized_name:
            return "empty_name"

        if any(phrase in normalized_name for phrase in StudySiteResultAdapter.VAGUE_NAME_PHRASES):
            return "generic_location_phrase"

        name_tokens = re.findall(r"[A-Za-z]+", normalized_name)
        if name_tokens and name_tokens[0] in StudySiteResultAdapter.VAGUE_NAME_PREFIX_TOKENS:
            return "leading_preposition_or_determiner"

        return None


def get_primary_study_site(study_sites: list[StudySiteCreate]) -> StudySiteCreate | None:
    """Get the best-supported study site.

    Args:
        study_sites: List of study sites

    Returns:
        Primary study site or None
    """
    if not study_sites:
        return None

    sorted_sites = sorted(
        study_sites,
        key=StudySiteResultAdapter._study_site_sort_key,
        reverse=True,
    )

    return sorted_sites[0]
