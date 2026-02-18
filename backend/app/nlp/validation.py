"""Validation and quality assurance for extraction results.

Performs sanity checks and validation on extracted entities and coordinates:
- Geographic validity (coordinates in valid ranges)
- Consistency checks (clustered coordinates shouldn't be too far apart)
- Duplicate detection
- Confidence threshold validation
- Extraction quality metrics

This is a Priority 4 improvement that catches errors and improves reliability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.nlp.domain_models import ExtractionResult, GeoEntity
from app.nlp.nlp_logger import logger


@dataclass
class ValidationIssue:
    """A validation issue found during QA."""

    severity: str  # "error", "warning", "info"
    category: str  # Type of issue
    message: str
    entity_text: str | None = None
    entity_index: int | None = None


@dataclass
class ValidationReport:
    """Report of validation results."""

    is_valid: bool
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)
    info: list[ValidationIssue] = field(default_factory=list)
    statistics: dict[str, Any] = field(default_factory=dict)

    def add_error(self, category: str, message: str, **kwargs) -> None:
        """Add an error."""
        self.errors.append(
            ValidationIssue(
                severity="error",
                category=category,
                message=message,
                **kwargs,
            )
        )
        self.is_valid = False

    def add_warning(self, category: str, message: str, **kwargs) -> None:
        """Add a warning."""
        self.warnings.append(
            ValidationIssue(
                severity="warning",
                category=category,
                message=message,
                **kwargs,
            )
        )

    def add_info(self, category: str, message: str, **kwargs) -> None:
        """Add an info message."""
        self.info.append(
            ValidationIssue(
                severity="info",
                category=category,
                message=message,
                **kwargs,
            )
        )

    def print_report(self) -> None:
        """Print a formatted report."""
        print(f"\n{'=' * 70}")
        print("Validation Report")
        print(f"{'=' * 70}")
        print(f"Status: {'✓ VALID' if self.is_valid else '✗ INVALID'}")
        print(f"Errors: {len(self.errors)}")
        print(f"Warnings: {len(self.warnings)}")
        print(f"Info: {len(self.info)}")

        if self.errors:
            print(f"\nErrors:")
            for issue in self.errors:
                print(f"  ✗ [{issue.category}] {issue.message}")

        if self.warnings:
            print(f"\nWarnings:")
            for issue in self.warnings:
                print(f"  ⚠ [{issue.category}] {issue.message}")

        if self.statistics:
            print(f"\nStatistics:")
            for key, value in self.statistics.items():
                print(f"  {key}: {value}")

        print(f"{'=' * 70}\n")


class ExtractionValidator:
    """Validator for extraction results."""

    # Valid coordinate ranges
    MIN_LAT = -90.0
    MAX_LAT = 90.0
    MIN_LON = -180.0
    MAX_LON = 180.0

    # Reasonable thresholds
    MAX_CLUSTER_DIAMETER_KM = 5000.0  # Max distance across a cluster
    MIN_CONFIDENCE = 0.3
    MAX_ENTITIES_PER_DOCUMENT = 1000

    def __init__(self) -> None:
        """Initialize the validator."""
        pass

    def validate_result(self, result: ExtractionResult) -> ValidationReport:
        """Validate an extraction result.

        Args:
            result: Extraction result to validate

        Returns:
            ValidationReport with issues found
        """
        report = ValidationReport(is_valid=True)

        # Basic statistics
        report.statistics = {
            "total_entities": len(result.entities),
            "entities_with_coords": len(result.get_entities_with_coordinates()),
            "sections_processed": result.total_sections_processed,
            "average_confidence": self._calculate_avg_confidence(result.entities),
        }

        # Validate entities
        self._validate_entities(result.entities, report)

        # Validate coordinates
        entities_with_coords = result.get_entities_with_coordinates()
        if entities_with_coords:
            self._validate_coordinates(entities_with_coords, report)

        # Validate clustering
        if result.cluster_info:
            self._validate_clusters(result, report)

        # Check for suspicious patterns
        self._check_suspicious_patterns(result, report)

        return report

    def _validate_entities(
        self,
        entities: list[GeoEntity],
        report: ValidationReport,
    ) -> None:
        """Validate entity properties."""
        # Check entity count
        if len(entities) > self.MAX_ENTITIES_PER_DOCUMENT:
            report.add_warning(
                "entity_count",
                f"Very high entity count: {len(entities)} (expected < {self.MAX_ENTITIES_PER_DOCUMENT})",
            )

        if len(entities) == 0:
            report.add_warning(
                "entity_count",
                "No entities extracted",
            )

        # Check individual entities
        for i, entity in enumerate(entities):
            # Validate confidence
            if entity.confidence < 0 or entity.confidence > 1:
                report.add_error(
                    "confidence",
                    f"Invalid confidence value: {entity.confidence}",
                    entity_text=entity.text,
                    entity_index=i,
                )

            if entity.confidence < self.MIN_CONFIDENCE:
                report.add_warning(
                    "confidence",
                    f"Very low confidence: {entity.confidence:.2f} for '{entity.text}'",
                    entity_text=entity.text,
                    entity_index=i,
                )

            # Validate positions
            if entity.start_char < 0 or entity.end_char < 0:
                report.add_error(
                    "position",
                    f"Negative position values for '{entity.text}'",
                    entity_text=entity.text,
                    entity_index=i,
                )

            if entity.start_char >= entity.end_char:
                report.add_error(
                    "position",
                    f"Invalid position range for '{entity.text}': {entity.start_char} >= {entity.end_char}",
                    entity_text=entity.text,
                    entity_index=i,
                )

            # Validate text
            if not entity.text or not entity.text.strip():
                report.add_error(
                    "text",
                    f"Empty entity text at position {entity.start_char}",
                    entity_index=i,
                )

            # Validate entity type
            valid_types = {
                "LOC", "GPE", "FAC", "NORP", "COORDINATE", "SPATIAL_RELATION",
                "STUDY_SITE", "WATER_BODY", "GEO_FEATURE", "BOUNDING_BOX",
            }
            if entity.entity_type not in valid_types:
                report.add_warning(
                    "entity_type",
                    f"Unknown entity type: {entity.entity_type} for '{entity.text}'",
                    entity_text=entity.text,
                    entity_index=i,
                )

    def _validate_coordinates(
        self,
        entities: list[GeoEntity],
        report: ValidationReport,
    ) -> None:
        """Validate coordinate values."""
        for i, entity in enumerate(entities):
            if not entity.coordinates:
                continue

            lat, lon = entity.coordinates

            # Check ranges
            if not (self.MIN_LAT <= lat <= self.MAX_LAT):
                report.add_error(
                    "coordinates",
                    f"Latitude out of range: {lat} for '{entity.text}'",
                    entity_text=entity.text,
                    entity_index=i,
                )

            if not (self.MIN_LON <= lon <= self.MAX_LON):
                report.add_error(
                    "coordinates",
                    f"Longitude out of range: {lon} for '{entity.text}'",
                    entity_text=entity.text,
                    entity_index=i,
                )

            # Check for suspicious values
            if lat == 0.0 and lon == 0.0:
                report.add_warning(
                    "coordinates",
                    f"Suspicious (0, 0) coordinates for '{entity.text}'",
                    entity_text=entity.text,
                    entity_index=i,
                )

    def _validate_clusters(
        self,
        result: ExtractionResult,
        report: ValidationReport,
    ) -> None:
        """Validate clustering results."""
        cluster_info = result.cluster_info

        total_clusters = cluster_info.get("total_clusters", 0)
        largest_cluster_size = cluster_info.get("largest_cluster_size", 0)

        if total_clusters == 0:
            report.add_info(
                "clustering",
                "No clusters formed (this may be expected if no coordinates were found)",
            )
            return

        # Check cluster statistics
        if total_clusters > 10:
            report.add_warning(
                "clustering",
                f"Many clusters found: {total_clusters} (study sites may be geographically dispersed)",
            )

        # Check cluster diameter
        coords_in_cluster = [
            e.coordinates for e in result.entities
            if e.coordinates is not None
        ]

        if len(coords_in_cluster) > 1:
            diameter = self._calculate_cluster_diameter(coords_in_cluster)
            if diameter > self.MAX_CLUSTER_DIAMETER_KM:
                report.add_warning(
                    "clustering",
                    f"Very large cluster diameter: {diameter:.0f} km "
                    f"(locations may span multiple study areas)",
                )

    def _calculate_cluster_diameter(self, coords: list[tuple[float, float]]) -> float:
        """Calculate maximum distance in a set of coordinates."""
        from geopy.distance import geodesic

        max_dist = 0.0
        for i, coord1 in enumerate(coords):
            for coord2 in coords[i + 1:]:
                dist = geodesic(coord1, coord2).kilometers
                max_dist = max(max_dist, dist)

        return max_dist

    def _check_suspicious_patterns(
        self,
        result: ExtractionResult,
        report: ValidationReport,
    ) -> None:
        """Check for suspicious patterns that might indicate errors."""
        entities = result.entities

        # Check for too many duplicate texts
        text_counts: dict[str, int] = {}
        for entity in entities:
            text_lower = entity.text.lower().strip()
            text_counts[text_lower] = text_counts.get(text_lower, 0) + 1

        for text, count in text_counts.items():
            if count > 10:
                report.add_warning(
                    "duplicates",
                    f"Entity text '{text}' appears {count} times (possible over-extraction)",
                )

        # Check for very short entities
        short_entities = [e for e in entities if len(e.text.strip()) < 3]
        if len(short_entities) > len(entities) * 0.3:
            report.add_warning(
                "entity_quality",
                f"{len(short_entities)} entities have very short text (< 3 chars)",
            )

        # Check section distribution
        section_counts: dict[str, int] = {}
        for entity in entities:
            section_counts[entity.section] = section_counts.get(entity.section, 0) + 1

        # All entities from one section might indicate a problem
        if len(section_counts) == 1 and result.total_sections_processed > 1:
            section = list(section_counts.keys())[0]
            report.add_info(
                "distribution",
                f"All entities from section '{section}' only",
            )

    def _calculate_avg_confidence(self, entities: list[GeoEntity]) -> float:
        """Calculate average confidence."""
        if not entities:
            return 0.0
        return sum(e.confidence for e in entities) / len(entities)

    def auto_fix_issues(
        self,
        result: ExtractionResult,
        report: ValidationReport,
    ) -> ExtractionResult:
        """Attempt to automatically fix some validation issues.

        Args:
            result: Extraction result with issues
            report: Validation report

        Returns:
            Fixed extraction result
        """
        fixed_entities = list(result.entities)

        # Fix 1: Remove entities with invalid coordinates
        fixed_entities = [
            e for e in fixed_entities
            if not e.coordinates or (
                self.MIN_LAT <= e.coordinates[0] <= self.MAX_LAT and
                self.MIN_LON <= e.coordinates[1] <= self.MAX_LON
            )
        ]

        # Fix 2: Remove empty entities
        fixed_entities = [
            e for e in fixed_entities
            if e.text and e.text.strip()
        ]

        # Fix 3: Clip confidence values to [0, 1]
        clipped_entities = []
        for entity in fixed_entities:
            if entity.confidence < 0 or entity.confidence > 1:
                clipped_entity = GeoEntity(
                    text=entity.text,
                    entity_type=entity.entity_type,
                    context=entity.context,
                    section=entity.section,
                    confidence=max(0.0, min(1.0, entity.confidence)),
                    start_char=entity.start_char,
                    end_char=entity.end_char,
                    coordinates=entity.coordinates,
                    bounding_box=entity.bounding_box,
                )
                clipped_entities.append(clipped_entity)
            else:
                clipped_entities.append(entity)

        # Create new result with fixed entities
        fixed_result = ExtractionResult(
            pdf_path=result.pdf_path,
            entities=clipped_entities,
            total_sections_processed=result.total_sections_processed,
            extraction_metadata=result.extraction_metadata,
            doc=result.doc,
            title=result.title,
            cluster_info=result.cluster_info,
            average_text_quality=result.average_text_quality,
            section_quality_scores=result.section_quality_scores,
        )

        fixes_applied = len(result.entities) - len(fixed_result.entities)
        if fixes_applied > 0:
            logger.info(f"Auto-fix: removed {fixes_applied} invalid entities")

        return fixed_result


# Singleton instance
_validator: ExtractionValidator | None = None


def get_validator() -> ExtractionValidator:
    """Get the validator instance."""
    global _validator
    if _validator is None:
        _validator = ExtractionValidator()
    return _validator
