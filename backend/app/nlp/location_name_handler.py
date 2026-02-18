"""Handler for compound and multi-word location names.

Ensures that location names like "Paradise, United States" are recognized
as single entities rather than being fragmented into separate entities.

This module provides:
- Pattern matching for compound location names
- Post-processing to merge fragmented locations
- Training data generation for multi-word locations
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar

from app.nlp.domain_models import GeoEntity
from app.nlp.nlp_logger import logger


@dataclass
class LocationPattern:
    """Pattern for recognizing compound location names."""

    pattern: re.Pattern[str]
    entity_type: str
    confidence: float


class LocationNameHandler:
    """Handle compound location names and prevent fragmentation."""

    # Patterns for common compound location formats
    COMPOUND_PATTERNS: ClassVar[list[LocationPattern]] = [
        # City, Country format: "Paris, France"
        LocationPattern(
            pattern=re.compile(
                r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*,\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b"
            ),
            entity_type="LOC",
            confidence=0.95,
        ),
        # City, State, Country: "New York, NY, USA"
        LocationPattern(
            pattern=re.compile(
                r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*,\s*([A-Z]{2})\s*,\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b"
            ),
            entity_type="GPE",
            confidence=0.95,
        ),
        # Lake/River/Mountain + Location: "Lake Superior, USA"
        LocationPattern(
            pattern=re.compile(
                r"\b(Lake|River|Mount|Mountain|Bay|Gulf|Sea|Ocean|Peninsula)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*,?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b"
            ),
            entity_type="LOC",
            confidence=0.90,
        ),
        # Geographic Feature + Descriptor: "Northern Hemisphere", "South Pacific"
        LocationPattern(
            pattern=re.compile(
                r"\b(North|South|East|West|Northern|Southern|Eastern|Western|Central|Mediterranean|Atlantic|Pacific|Arctic)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b"
            ),
            entity_type="LOC",
            confidence=0.85,
        ),
        # Region, Subregion: "Scandinavia region", "Sub-Saharan Africa"
        LocationPattern(
            pattern=re.compile(
                r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:Region|Basin|Delta|Valley|Plain|Plateau)\b"
            ),
            entity_type="LOC",
            confidence=0.85,
        ),
    ]

    # Keywords that indicate location names
    LOCATION_KEYWORDS: ClassVar[set[str]] = {
        "lake", "river", "mount", "mountain", "bay", "gulf", "sea", "ocean",
        "peninsula", "island", "strait", "channel", "valley", "plateau",
        "desert", "forest", "region", "basin", "delta", "plains",
        "coast", "shore", "beach", "city", "town", "province", "state",
        "country", "nation", "kingdom", "republic", "territory",
    }

    def __init__(self) -> None:
        """Initialize the location name handler."""
        pass

    def merge_fragmented_entities(
        self, entities: list[GeoEntity]
    ) -> list[GeoEntity]:
        """Merge adjacent location entities that form compound names.

        Args:
            entities: List of extracted entities

        Returns:
            List with merged compound location entities
        """
        if len(entities) < 2:
            return entities

        # Sort by position
        sorted_entities = sorted(entities, key=lambda e: (e.start_char, e.end_char))

        merged: list[GeoEntity] = []
        skip_indices = set()

        for i, entity in enumerate(sorted_entities):
            if i in skip_indices:
                continue

            # Check if this and next entities should be merged
            if i + 1 < len(sorted_entities):
                current = entity
                next_entity = sorted_entities[i + 1]

                # Check if they're adjacent or very close (separated by comma/space)
                gap = next_entity.start_char - current.end_char
                if gap <= 2:  # Allows for ", " or "-"
                    # Check if both are location-related
                    if self._are_mergeable(current, next_entity):
                        # Merge them
                        merged_entity = self._merge_entities(current, next_entity)
                        merged.append(merged_entity)
                        skip_indices.add(i + 1)
                        logger.debug(
                            f"Merged '{current.text}' + '{next_entity.text}' "
                            f"-> '{merged_entity.text}'"
                        )
                        continue

            merged.append(entity)

        return merged

    def _are_mergeable(self, entity1: GeoEntity, entity2: GeoEntity) -> bool:
        """Check if two entities should be merged.

        Args:
            entity1: First entity
            entity2: Second entity

        Returns:
            True if entities should be merged
        """
        # Both must be location types
        location_types = {"LOC", "GPE", "FAC", "WATER_BODY", "GEO_FEATURE"}
        if entity1.entity_type not in location_types or entity2.entity_type not in location_types:
            return False

        # Check context for location keywords
        combined_text = f"{entity1.text} {entity2.text}".lower()
        has_location_keyword = any(
            keyword in combined_text for keyword in self.LOCATION_KEYWORDS
        )

        # If they form a common pattern, they're mergeable
        return has_location_keyword or self._matches_pattern(f"{entity1.text}, {entity2.text}")

    def _matches_pattern(self, text: str) -> bool:
        """Check if text matches a known compound location pattern."""
        for pattern in self.COMPOUND_PATTERNS:
            if pattern.pattern.search(text):
                return True
        return False

    def _merge_entities(self, entity1: GeoEntity, entity2: GeoEntity) -> GeoEntity:
        """Merge two entities into one.

        Args:
            entity1: First entity
            entity2: Second entity

        Returns:
            Merged entity
        """
        # Combine text
        combined_text = f"{entity1.text}, {entity2.text}"

        # Use higher confidence
        merged_confidence = max(entity1.confidence, entity2.confidence) * 0.99

        # Combine context
        combined_context = f"{entity1.context} {entity2.context}".strip()

        # Use position of first entity
        merged_entity = GeoEntity(
            text=combined_text,
            entity_type=entity1.entity_type,
            context=combined_context,
            section=entity1.section,
            confidence=merged_confidence,
            start_char=entity1.start_char,
            end_char=entity2.end_char,
            coordinates=entity1.coordinates or entity2.coordinates,
        )

        return merged_entity

    def extract_compound_locations(self, text: str) -> list[GeoEntity]:
        """Extract compound location names using pattern matching.

        Args:
            text: Source text

        Returns:
            List of extracted compound location entities
        """
        entities: list[GeoEntity] = []

        for pattern in self.COMPOUND_PATTERNS:
            for match in pattern.pattern.finditer(text):
                matched_text = match.group(0)
                start = match.start()
                end = match.end()

                entity = GeoEntity(
                    text=matched_text,
                    entity_type=pattern.entity_type,
                    context=self._get_context(text, start, end),
                    section="",
                    confidence=pattern.confidence,
                    start_char=start,
                    end_char=end,
                )
                entities.append(entity)

        return entities

    def _get_context(self, text: str, start: int, end: int, window: int = 50) -> str:
        """Get context around a span."""
        context_start = max(0, start - window)
        context_end = min(len(text), end + window)
        return text[context_start:context_end]

    def prioritize_longer_entities(
        self, entities: list[GeoEntity]
    ) -> list[GeoEntity]:
        """When entities overlap, prefer longer entity names.

        Args:
            entities: List of entities

        Returns:
            Deduplicated entities favoring longer names
        """
        if len(entities) < 2:
            return entities

        # Sort by length (longest first) and confidence
        sorted_entities = sorted(
            entities,
            key=lambda e: (len(e.text), e.confidence),
            reverse=True,
        )

        kept: list[GeoEntity] = []
        used_ranges = set()

        for entity in sorted_entities:
            # Check if this entity overlaps with already kept entities
            entity_range = set(range(entity.start_char, entity.end_char))

            if not entity_range.intersection(used_ranges):
                kept.append(entity)
                used_ranges.update(entity_range)

        # Return in original order
        return sorted(kept, key=lambda e: e.start_char)

    def post_process_entities(
        self, entities: list[GeoEntity], merge: bool = True, prioritize_long: bool = True
    ) -> list[GeoEntity]:
        """Post-process entities to handle compound location names.

        Args:
            entities: Extracted entities
            merge: Whether to merge adjacent locations
            prioritize_long: Whether to prioritize longer entity names

        Returns:
            Post-processed entities
        """
        result = list(entities)

        if prioritize_long:
            result = self.prioritize_longer_entities(result)

        if merge:
            result = self.merge_fragmented_entities(result)

        return result


def create_compound_location_training_data() -> list[tuple[str, dict]]:
    """Create training examples for compound location names.

    Returns:
        List of spaCy training examples
    """
    examples = [
        # City, Country
        ("Paris, France", {"entities": [(0, 14, "LOC")]}),
        ("Tokyo, Japan", {"entities": [(0, 12, "LOC")]}),
        ("Sydney, Australia", {"entities": [(0, 17, "LOC")]}),
        ("New York, United States", {"entities": [(0, 23, "GPE")]}),
        ("Paradise, United States", {"entities": [(0, 23, "GPE")]}),
        ("Toronto, Canada", {"entities": [(0, 15, "LOC")]}),
        # Lake/Water bodies with location
        ("Lake Superior, USA", {"entities": [(0, 18, "LOC")]}),
        ("Lake Baikal, Russia", {"entities": [(0, 19, "LOC")]}),
        ("River Amazon, Brazil", {"entities": [(0, 20, "LOC")]}),
        ("Gulf of Mexico", {"entities": [(0, 14, "LOC")]}),
        ("Bay of Bengal", {"entities": [(0, 13, "LOC")]}),
        # Mountain ranges
        ("Mount Everest, Nepal", {"entities": [(0, 20, "LOC")]}),
        ("Mount Kilimanjaro, Tanzania", {"entities": [(0, 27, "LOC")]}),
        ("Rocky Mountains, USA", {"entities": [(0, 20, "LOC")]}),
        # Regions
        ("Southern Africa", {"entities": [(0, 15, "LOC")]}),
        ("Northern Europe", {"entities": [(0, 15, "LOC")]}),
        ("Southeast Asia", {"entities": [(0, 14, "LOC")]}),
        ("Mediterranean Sea", {"entities": [(0, 17, "LOC")]}),
        ("Atlantic Ocean", {"entities": [(0, 14, "LOC")]}),
        ("Pacific Ocean", {"entities": [(0, 13, "LOC")]}),
        # City, State, Country
        ("New York, NY, USA", {"entities": [(0, 17, "GPE")]}),
        ("Los Angeles, CA, USA", {"entities": [(0, 20, "GPE")]}),
        ("San Francisco, CA, USA", {"entities": [(0, 22, "GPE")]}),
        # Geographic features
        ("Sahara Desert, Africa", {"entities": [(0, 21, "LOC")]}),
        ("Amazon Basin, Brazil", {"entities": [(0, 20, "LOC")]}),
        ("Nile Delta, Egypt", {"entities": [(0, 17, "LOC")]}),
        ("Atacama Desert, Chile", {"entities": [(0, 21, "LOC")]}),
        # Study site specific
        ("Yellowstone National Park, USA", {"entities": [(0, 30, "FAC")]}),
        ("Grand Canyon, Arizona", {"entities": [(0, 20, "LOC")]}),
        ("Great Barrier Reef, Australia", {"entities": [(0, 29, "LOC")]}),
        ("Death Valley, California", {"entities": [(0, 24, "LOC")]}),
    ]

    return examples


# Singleton instance
_handler: LocationNameHandler | None = None


def get_location_name_handler() -> LocationNameHandler:
    """Get the location name handler instance."""
    global _handler
    if _handler is None:
        _handler = LocationNameHandler()
    return _handler
