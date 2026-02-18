"""Spatial relation resolution for computing coordinates from relative descriptions.

This module resolves spatial relation phrases like "10 km north of Paris" to
actual geographic coordinates by:
1. Parsing the distance, direction, and reference location
2. Geocoding the reference location
3. Calculating the offset coordinates using geodesic math

This is a Priority 3 improvement that significantly enhances location extraction
for papers that describe study sites relative to known landmarks.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, ClassVar

from geopy.distance import geodesic
from geopy.point import Point

from app.nlp.nlp_logger import logger

if TYPE_CHECKING:
    from app.nlp.domain_models import GeoEntity
    from app.nlp.geocoding import CachedGeocoder


class CardinalDirection(Enum):
    """Cardinal and intercardinal directions with bearing angles."""

    NORTH = 0
    NORTHEAST = 45
    EAST = 90
    SOUTHEAST = 135
    SOUTH = 180
    SOUTHWEST = 225
    WEST = 270
    NORTHWEST = 315

    # Aliases
    N = 0
    NE = 45
    E = 90
    SE = 135
    S = 180
    SW = 225
    W = 270
    NW = 315

    @classmethod
    def from_string(cls, direction: str) -> CardinalDirection | None:
        """Parse direction string to CardinalDirection."""
        direction_map = {
            "north": cls.NORTH,
            "n": cls.N,
            "northeast": cls.NORTHEAST,
            "ne": cls.NE,
            "north-east": cls.NORTHEAST,
            "east": cls.EAST,
            "e": cls.E,
            "southeast": cls.SOUTHEAST,
            "se": cls.SE,
            "south-east": cls.SOUTHEAST,
            "south": cls.SOUTH,
            "s": cls.S,
            "southwest": cls.SOUTHWEST,
            "sw": cls.SW,
            "south-west": cls.SOUTHWEST,
            "west": cls.WEST,
            "w": cls.W,
            "northwest": cls.NORTHWEST,
            "nw": cls.NW,
            "north-west": cls.NORTHWEST,
            # Hydrological directions
            "upstream": cls.NORTH,  # Approximate - depends on river
            "downstream": cls.SOUTH,
            "offshore": cls.WEST,  # Approximate
            "onshore": cls.EAST,
            "inland": cls.EAST,
        }
        return direction_map.get(direction.lower().strip())


@dataclass
class SpatialRelation:
    """Parsed spatial relation with components."""

    distance: float  # Distance value
    unit: str  # Distance unit (km, m, miles, etc.)
    direction: CardinalDirection  # Direction from reference
    reference_location: str  # Name of reference location
    original_text: str  # Original text that was parsed
    confidence: float = 0.85

    @property
    def distance_km(self) -> float:
        """Get distance in kilometers."""
        unit_conversions = {
            "km": 1.0,
            "kilometer": 1.0,
            "kilometers": 1.0,
            "kilometre": 1.0,
            "kilometres": 1.0,
            "m": 0.001,
            "meter": 0.001,
            "meters": 0.001,
            "metre": 0.001,
            "metres": 0.001,
            "mi": 1.60934,
            "mile": 1.60934,
            "miles": 1.60934,
            "nm": 1.852,  # Nautical mile
            "nautical mile": 1.852,
            "nautical miles": 1.852,
        }
        return self.distance * unit_conversions.get(self.unit.lower(), 1.0)


@dataclass
class ResolvedLocation:
    """Result of spatial relation resolution."""

    latitude: float
    longitude: float
    reference_coords: tuple[float, float]  # Coords of reference location
    spatial_relation: SpatialRelation
    confidence: float

    @property
    def coordinates(self) -> tuple[float, float]:
        """Get (lat, lon) tuple."""
        return (self.latitude, self.longitude)


class SpatialRelationResolver:
    """Resolve spatial relations to geographic coordinates.

    Parses phrases like:
    - "10 km north of Paris"
    - "approximately 50 miles southwest of London"
    - "5 km upstream from the river mouth"
    - "located 20 km NE of the capital"

    And computes the actual coordinates using geodesic calculations.
    """

    # Patterns for parsing spatial relations
    PATTERNS: ClassVar[list[tuple[re.Pattern[str], str]]] = [
        # "10 km north of Paris"
        (
            re.compile(
                r"(?:about|approximately|~|circa|ca\.?)?\s*"
                r"(\d+\.?\d*)\s*"
                r"(km|kilometers?|kilometres?|m|meters?|metres?|miles?|mi|nm)\s+"
                r"(north|south|east|west|northeast|northwest|southeast|southwest|"
                r"n|s|e|w|ne|nw|se|sw|north-east|north-west|south-east|south-west|"
                r"upstream|downstream|offshore|onshore|inland)\s+"
                r"(?:of|from)\s+"
                r"(?:the\s+)?(.+?)(?:\.|,|;|$)",
                re.IGNORECASE,
            ),
            "distance_direction_of",
        ),
        # "north of Paris, about 10 km"
        (
            re.compile(
                r"(north|south|east|west|northeast|northwest|southeast|southwest|"
                r"n|s|e|w|ne|nw|se|sw)\s+"
                r"(?:of|from)\s+"
                r"(?:the\s+)?(.+?),?\s+"
                r"(?:about|approximately|~|circa|ca\.?)?\s*"
                r"(\d+\.?\d*)\s*"
                r"(km|kilometers?|kilometres?|m|meters?|metres?|miles?|mi)",
                re.IGNORECASE,
            ),
            "direction_of_distance",
        ),
        # "located 10 km to the north of Paris"
        (
            re.compile(
                r"(?:located|situated|positioned)\s+"
                r"(?:about|approximately|~)?\s*"
                r"(\d+\.?\d*)\s*"
                r"(km|kilometers?|kilometres?|m|meters?|metres?|miles?|mi)\s+"
                r"(?:to\s+the\s+)?"
                r"(north|south|east|west|northeast|northwest|southeast|southwest)\s+"
                r"(?:of|from)\s+"
                r"(?:the\s+)?(.+?)(?:\.|,|;|$)",
                re.IGNORECASE,
            ),
            "located_distance_direction",
        ),
        # Simple proximity: "near Paris" or "close to London"
        (
            re.compile(
                r"(?:near|nearby|close\s+to|adjacent\s+to|in\s+the\s+vicinity\s+of)\s+"
                r"(?:the\s+)?(.+?)(?:\.|,|;|$)",
                re.IGNORECASE,
            ),
            "proximity",
        ),
    ]

    # Default distance for proximity relations (km)
    DEFAULT_PROXIMITY_DISTANCE: ClassVar[float] = 5.0

    def __init__(self, geocoder: CachedGeocoder | None = None) -> None:
        """Initialize the spatial relation resolver.

        Args:
            geocoder: Geocoder for resolving reference locations
        """
        self._geocoder = geocoder

    @property
    def geocoder(self) -> CachedGeocoder:
        """Get geocoder, initializing if needed."""
        if self._geocoder is None:
            from app.nlp.geocoding import get_geocoder
            self._geocoder = get_geocoder()
        return self._geocoder

    def parse(self, text: str) -> list[SpatialRelation]:
        """Parse spatial relations from text.

        Args:
            text: Text containing spatial relation descriptions

        Returns:
            List of parsed SpatialRelation objects
        """
        relations = []

        for pattern, pattern_type in self.PATTERNS:
            for match in pattern.finditer(text):
                relation = self._parse_match(match, pattern_type)
                if relation:
                    relations.append(relation)

        return relations

    def _parse_match(
        self, match: re.Match, pattern_type: str
    ) -> SpatialRelation | None:
        """Parse a regex match into a SpatialRelation."""
        try:
            groups = match.groups()

            if pattern_type == "distance_direction_of":
                distance = float(groups[0])
                unit = groups[1]
                direction = CardinalDirection.from_string(groups[2])
                reference = groups[3].strip()

                if direction is None:
                    return None

                return SpatialRelation(
                    distance=distance,
                    unit=unit,
                    direction=direction,
                    reference_location=reference,
                    original_text=match.group(),
                )

            elif pattern_type == "direction_of_distance":
                direction = CardinalDirection.from_string(groups[0])
                reference = groups[1].strip()
                distance = float(groups[2])
                unit = groups[3]

                if direction is None:
                    return None

                return SpatialRelation(
                    distance=distance,
                    unit=unit,
                    direction=direction,
                    reference_location=reference,
                    original_text=match.group(),
                )

            elif pattern_type == "located_distance_direction":
                distance = float(groups[0])
                unit = groups[1]
                direction = CardinalDirection.from_string(groups[2])
                reference = groups[3].strip()

                if direction is None:
                    return None

                return SpatialRelation(
                    distance=distance,
                    unit=unit,
                    direction=direction,
                    reference_location=reference,
                    original_text=match.group(),
                )

            elif pattern_type == "proximity":
                # No distance/direction, just proximity
                reference = groups[0].strip()

                return SpatialRelation(
                    distance=self.DEFAULT_PROXIMITY_DISTANCE,
                    unit="km",
                    direction=CardinalDirection.NORTH,  # Placeholder
                    reference_location=reference,
                    original_text=match.group(),
                    confidence=0.6,  # Lower confidence for proximity
                )

        except (ValueError, IndexError) as e:
            logger.debug(f"Failed to parse spatial relation: {e}")
            return None

        return None

    def resolve(
        self,
        relation: SpatialRelation,
        country_bias: str | None = None,
    ) -> ResolvedLocation | None:
        """Resolve a spatial relation to coordinates.

        Args:
            relation: Parsed spatial relation
            country_bias: Preferred country for geocoding

        Returns:
            ResolvedLocation with computed coordinates, or None
        """
        # Geocode the reference location
        ref_coords = self.geocoder.geocode(
            relation.reference_location,
            bias_point=None,
        )

        if not ref_coords:
            logger.debug(
                f"Could not geocode reference location: {relation.reference_location}"
            )
            return None

        # Calculate offset coordinates
        try:
            new_coords = self._calculate_offset(
                ref_coords,
                relation.distance_km,
                relation.direction.value,
            )

            return ResolvedLocation(
                latitude=new_coords[0],
                longitude=new_coords[1],
                reference_coords=ref_coords,
                spatial_relation=relation,
                confidence=relation.confidence,
            )

        except Exception as e:
            logger.warning(f"Failed to calculate offset: {e}")
            return None

    def _calculate_offset(
        self,
        origin: tuple[float, float],
        distance_km: float,
        bearing_degrees: float,
    ) -> tuple[float, float]:
        """Calculate destination point given origin, distance, and bearing.

        Uses geodesic (great circle) calculation for accuracy.

        Args:
            origin: (latitude, longitude) of starting point
            distance_km: Distance in kilometers
            bearing_degrees: Bearing in degrees (0=North, 90=East, etc.)

        Returns:
            (latitude, longitude) of destination point
        """
        # Convert to radians
        lat1 = math.radians(origin[0])
        lon1 = math.radians(origin[1])
        bearing = math.radians(bearing_degrees)

        # Earth's radius in km
        R = 6371.0

        # Calculate destination using haversine formula
        lat2 = math.asin(
            math.sin(lat1) * math.cos(distance_km / R)
            + math.cos(lat1) * math.sin(distance_km / R) * math.cos(bearing)
        )

        lon2 = lon1 + math.atan2(
            math.sin(bearing) * math.sin(distance_km / R) * math.cos(lat1),
            math.cos(distance_km / R) - math.sin(lat1) * math.sin(lat2),
        )

        # Convert back to degrees
        return (math.degrees(lat2), math.degrees(lon2))

    def resolve_from_text(
        self,
        text: str,
        country_bias: str | None = None,
    ) -> list[ResolvedLocation]:
        """Parse and resolve all spatial relations in text.

        Args:
            text: Text containing spatial relation descriptions
            country_bias: Preferred country for geocoding

        Returns:
            List of ResolvedLocation objects
        """
        relations = self.parse(text)
        resolved = []

        for relation in relations:
            location = self.resolve(relation, country_bias)
            if location:
                resolved.append(location)

        return resolved

    def resolve_entity(
        self,
        entity: GeoEntity,
        country_bias: str | None = None,
    ) -> tuple[float, float] | None:
        """Resolve a SPATIAL_RELATION entity to coordinates.

        Args:
            entity: GeoEntity with entity_type="SPATIAL_RELATION"
            country_bias: Preferred country for geocoding

        Returns:
            (latitude, longitude) tuple or None
        """
        if entity.entity_type != "SPATIAL_RELATION":
            return None

        # Try to resolve from entity text or context
        text = entity.context or entity.text
        resolved = self.resolve_from_text(text, country_bias)

        if resolved:
            return resolved[0].coordinates

        return None


# Singleton instance
_resolver: SpatialRelationResolver | None = None


def get_spatial_relation_resolver() -> SpatialRelationResolver:
    """Get the spatial relation resolver instance."""
    global _resolver
    if _resolver is None:
        _resolver = SpatialRelationResolver()
    return _resolver
