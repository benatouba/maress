"""Bounding box extraction for study area extent.

This module extracts geographic bounding boxes from text when coordinate
ranges are mentioned. This is common in earth science papers where study
areas are defined by their geographic extent rather than single points.

Examples:
- "The study area extends from 45°N to 47°N and 122°W to 124°W"
- "between 45° and 47° latitude"
- "bounded by 45-47°N and 122-124°W"
- "45°N-47°N, 122°W-124°W"
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar

from app.nlp.domain_models import GeoEntity
from app.nlp.nlp_logger import logger


@dataclass
class BoundingBox:
    """Geographic bounding box representation."""

    min_lat: float  # Southern boundary
    max_lat: float  # Northern boundary
    min_lon: float  # Western boundary
    max_lon: float  # Eastern boundary
    source_text: str  # Original text that was parsed
    confidence: float = 0.85

    @property
    def center(self) -> tuple[float, float]:
        """Get the center point of the bounding box."""
        return (
            (self.min_lat + self.max_lat) / 2,
            (self.min_lon + self.max_lon) / 2,
        )

    @property
    def area_km2(self) -> float:
        """Approximate area in km² (rough estimate)."""
        # 1 degree latitude ≈ 111 km
        # 1 degree longitude ≈ 111 km * cos(lat)
        import math

        lat_km = (self.max_lat - self.min_lat) * 111
        avg_lat = (self.min_lat + self.max_lat) / 2
        lon_km = (self.max_lon - self.min_lon) * 111 * math.cos(math.radians(avg_lat))
        return lat_km * lon_km

    def is_valid(self) -> bool:
        """Check if the bounding box is valid."""
        # Check ranges
        if not (-90 <= self.min_lat <= 90 and -90 <= self.max_lat <= 90):
            return False
        if not (-180 <= self.min_lon <= 180 and -180 <= self.max_lon <= 180):
            return False

        # Check ordering
        if self.min_lat > self.max_lat:
            return False

        # Handle date line crossing for longitude
        # (min_lon > max_lon is valid when crossing 180°)

        # Reject unreasonably large boxes (whole Earth)
        if self.max_lat - self.min_lat > 90:
            return False
        if abs(self.max_lon - self.min_lon) > 180:
            return False

        return True

    def to_wkt(self) -> str:
        """Convert to WKT POLYGON format."""
        return (
            f"POLYGON(({self.min_lon} {self.min_lat}, "
            f"{self.max_lon} {self.min_lat}, "
            f"{self.max_lon} {self.max_lat}, "
            f"{self.min_lon} {self.max_lat}, "
            f"{self.min_lon} {self.min_lat}))"
        )

    def to_geojson(self) -> dict:
        """Convert to GeoJSON Polygon format."""
        return {
            "type": "Polygon",
            "coordinates": [[
                [self.min_lon, self.min_lat],
                [self.max_lon, self.min_lat],
                [self.max_lon, self.max_lat],
                [self.min_lon, self.max_lat],
                [self.min_lon, self.min_lat],
            ]],
        }


class BoundingBoxExtractor:
    """Extract geographic bounding boxes from text.

    Detects coordinate range patterns and converts them to BoundingBox objects.
    """

    # Patterns for latitude ranges
    LAT_RANGE_PATTERNS: ClassVar[list[tuple[str, str]]] = [
        # "45°N to 47°N" or "45°N - 47°N"
        (
            r"(\d+\.?\d*)\s*°?\s*([NS])\s*(?:to|[-–—])\s*(\d+\.?\d*)\s*°?\s*([NS])",
            "range_with_dir",
        ),
        # "between 45° and 47° N latitude"
        (
            r"between\s+(\d+\.?\d*)\s*°?\s*and\s+(\d+\.?\d*)\s*°?\s*([NS])?\s*(?:lat|latitude)?",
            "between_lat",
        ),
        # "45-47°N"
        (
            r"(\d+\.?\d*)\s*[-–—]\s*(\d+\.?\d*)\s*°\s*([NS])",
            "compact_range",
        ),
        # "from 45°N to 47°N latitude"
        (
            r"from\s+(\d+\.?\d*)\s*°?\s*([NS])?\s*to\s+(\d+\.?\d*)\s*°?\s*([NS])\s*(?:lat|latitude)?",
            "from_to_lat",
        ),
        # Decimal ranges: "-45.5 to -43.2" (with context for latitude)
        (
            r"lat(?:itude)?[:\s]*(-?\d+\.?\d*)\s*(?:to|[-–—])\s*(-?\d+\.?\d*)",
            "decimal_lat_range",
        ),
    ]

    # Patterns for longitude ranges
    LON_RANGE_PATTERNS: ClassVar[list[tuple[str, str]]] = [
        # "122°W to 124°W" or "122°W - 124°W"
        (
            r"(\d+\.?\d*)\s*°?\s*([EW])\s*(?:to|[-–—])\s*(\d+\.?\d*)\s*°?\s*([EW])",
            "range_with_dir",
        ),
        # "between 122° and 124° W longitude"
        (
            r"between\s+(\d+\.?\d*)\s*°?\s*and\s+(\d+\.?\d*)\s*°?\s*([EW])?\s*(?:lon|longitude)?",
            "between_lon",
        ),
        # "122-124°W"
        (
            r"(\d+\.?\d*)\s*[-–—]\s*(\d+\.?\d*)\s*°\s*([EW])",
            "compact_range",
        ),
        # "from 122°W to 124°W longitude"
        (
            r"from\s+(\d+\.?\d*)\s*°?\s*([EW])?\s*to\s+(\d+\.?\d*)\s*°?\s*([EW])\s*(?:lon|longitude)?",
            "from_to_lon",
        ),
        # Decimal ranges: "-124.5 to -122.2" (with context for longitude)
        (
            r"lon(?:gitude)?[:\s]*(-?\d+\.?\d*)\s*(?:to|[-–—])\s*(-?\d+\.?\d*)",
            "decimal_lon_range",
        ),
    ]

    # Combined patterns for bounding box
    BBOX_PATTERNS: ClassVar[list[tuple[str, str]]] = [
        # "45°N-47°N, 122°W-124°W" (compact format)
        (
            r"(\d+\.?\d*)\s*°?\s*([NS])\s*[-–—]\s*(\d+\.?\d*)\s*°?\s*([NS])\s*[,;]\s*"
            r"(\d+\.?\d*)\s*°?\s*([EW])\s*[-–—]\s*(\d+\.?\d*)\s*°?\s*([EW])",
            "compact_bbox",
        ),
        # "bounded by 45-47°N and 122-124°W"
        (
            r"bounded\s+by\s+(\d+\.?\d*)\s*[-–—]\s*(\d+\.?\d*)\s*°?\s*([NS])\s*and\s+"
            r"(\d+\.?\d*)\s*[-–—]\s*(\d+\.?\d*)\s*°?\s*([EW])",
            "bounded_by",
        ),
        # "extends from 45°N to 47°N and from 122°W to 124°W"
        (
            r"extends?\s+from\s+(\d+\.?\d*)\s*°?\s*([NS])\s*to\s+(\d+\.?\d*)\s*°?\s*([NS])\s+"
            r"and\s+(?:from\s+)?(\d+\.?\d*)\s*°?\s*([EW])\s*to\s+(\d+\.?\d*)\s*°?\s*([EW])",
            "extends_from_to",
        ),
        # Bounding box with decimal coordinates
        # "bounded by -45.5 to -43.2 latitude and -124.5 to -122.2 longitude"
        (
            r"(?:bounded\s+by|between)\s+(-?\d+\.?\d*)\s*(?:to|and|[-–—])\s*(-?\d+\.?\d*)\s*"
            r"(?:°?\s*)?(?:lat|latitude)\s*and\s+"
            r"(-?\d+\.?\d*)\s*(?:to|and|[-–—])\s*(-?\d+\.?\d*)\s*(?:°?\s*)?(?:lon|longitude)",
            "bounded_decimal",
        ),
    ]

    def __init__(self) -> None:
        """Initialize the bounding box extractor."""
        # Compile patterns for efficiency
        self._lat_patterns = [
            (re.compile(p, re.IGNORECASE), t) for p, t in self.LAT_RANGE_PATTERNS
        ]
        self._lon_patterns = [
            (re.compile(p, re.IGNORECASE), t) for p, t in self.LON_RANGE_PATTERNS
        ]
        self._bbox_patterns = [
            (re.compile(p, re.IGNORECASE), t) for p, t in self.BBOX_PATTERNS
        ]

    def extract(self, text: str) -> list[BoundingBox]:
        """Extract all bounding boxes from text.

        Args:
            text: Text to search for bounding boxes

        Returns:
            List of extracted BoundingBox objects
        """
        boxes: list[BoundingBox] = []

        # Try combined bbox patterns first (most complete)
        for pattern, pattern_type in self._bbox_patterns:
            for match in pattern.finditer(text):
                box = self._parse_bbox_match(match, pattern_type)
                if box and box.is_valid():
                    boxes.append(box)

        # If no combined patterns found, try to combine lat/lon ranges
        if not boxes:
            lat_ranges = self._extract_lat_ranges(text)
            lon_ranges = self._extract_lon_ranges(text)

            # Combine the first lat and lon range found
            if lat_ranges and lon_ranges:
                lat_min, lat_max, lat_text = lat_ranges[0]
                lon_min, lon_max, lon_text = lon_ranges[0]

                box = BoundingBox(
                    min_lat=lat_min,
                    max_lat=lat_max,
                    min_lon=lon_min,
                    max_lon=lon_max,
                    source_text=f"{lat_text}; {lon_text}",
                    confidence=0.75,  # Lower confidence for combined extraction
                )
                if box.is_valid():
                    boxes.append(box)

        return boxes

    def _extract_lat_ranges(self, text: str) -> list[tuple[float, float, str]]:
        """Extract latitude ranges from text.

        Returns:
            List of (min_lat, max_lat, source_text) tuples
        """
        ranges = []

        for pattern, pattern_type in self._lat_patterns:
            for match in pattern.finditer(text):
                result = self._parse_lat_range(match, pattern_type)
                if result:
                    ranges.append(result)

        return ranges

    def _extract_lon_ranges(self, text: str) -> list[tuple[float, float, str]]:
        """Extract longitude ranges from text.

        Returns:
            List of (min_lon, max_lon, source_text) tuples
        """
        ranges = []

        for pattern, pattern_type in self._lon_patterns:
            for match in pattern.finditer(text):
                result = self._parse_lon_range(match, pattern_type)
                if result:
                    ranges.append(result)

        return ranges

    def _parse_lat_range(
        self, match: re.Match, pattern_type: str
    ) -> tuple[float, float, str] | None:
        """Parse a latitude range match."""
        try:
            groups = match.groups()

            if pattern_type == "range_with_dir":
                lat1 = float(groups[0])
                dir1 = groups[1].upper()
                lat2 = float(groups[2])
                dir2 = groups[3].upper()

                if dir1 == "S":
                    lat1 = -lat1
                if dir2 == "S":
                    lat2 = -lat2

                return (min(lat1, lat2), max(lat1, lat2), match.group())

            elif pattern_type in ("between_lat", "compact_range"):
                lat1 = float(groups[0])
                lat2 = float(groups[1])
                direction = groups[2].upper() if len(groups) > 2 and groups[2] else "N"

                if direction == "S":
                    lat1, lat2 = -lat1, -lat2

                return (min(lat1, lat2), max(lat1, lat2), match.group())

            elif pattern_type == "from_to_lat":
                lat1 = float(groups[0])
                dir1 = groups[1].upper() if groups[1] else "N"
                lat2 = float(groups[2])
                dir2 = groups[3].upper() if groups[3] else dir1

                if dir1 == "S":
                    lat1 = -lat1
                if dir2 == "S":
                    lat2 = -lat2

                return (min(lat1, lat2), max(lat1, lat2), match.group())

            elif pattern_type == "decimal_lat_range":
                lat1 = float(groups[0])
                lat2 = float(groups[1])
                return (min(lat1, lat2), max(lat1, lat2), match.group())

        except (ValueError, IndexError) as e:
            logger.debug(f"Failed to parse latitude range: {e}")
            return None

        return None

    def _parse_lon_range(
        self, match: re.Match, pattern_type: str
    ) -> tuple[float, float, str] | None:
        """Parse a longitude range match."""
        try:
            groups = match.groups()

            if pattern_type == "range_with_dir":
                lon1 = float(groups[0])
                dir1 = groups[1].upper()
                lon2 = float(groups[2])
                dir2 = groups[3].upper()

                if dir1 == "W":
                    lon1 = -lon1
                if dir2 == "W":
                    lon2 = -lon2

                return (min(lon1, lon2), max(lon1, lon2), match.group())

            elif pattern_type in ("between_lon", "compact_range"):
                lon1 = float(groups[0])
                lon2 = float(groups[1])
                direction = groups[2].upper() if len(groups) > 2 and groups[2] else "E"

                if direction == "W":
                    lon1, lon2 = -lon1, -lon2

                return (min(lon1, lon2), max(lon1, lon2), match.group())

            elif pattern_type == "from_to_lon":
                lon1 = float(groups[0])
                dir1 = groups[1].upper() if groups[1] else "E"
                lon2 = float(groups[2])
                dir2 = groups[3].upper() if groups[3] else dir1

                if dir1 == "W":
                    lon1 = -lon1
                if dir2 == "W":
                    lon2 = -lon2

                return (min(lon1, lon2), max(lon1, lon2), match.group())

            elif pattern_type == "decimal_lon_range":
                lon1 = float(groups[0])
                lon2 = float(groups[1])
                return (min(lon1, lon2), max(lon1, lon2), match.group())

        except (ValueError, IndexError) as e:
            logger.debug(f"Failed to parse longitude range: {e}")
            return None

        return None

    def _parse_bbox_match(
        self, match: re.Match, pattern_type: str
    ) -> BoundingBox | None:
        """Parse a bounding box match."""
        try:
            groups = match.groups()

            if pattern_type == "compact_bbox":
                # Groups: lat1, dir1, lat2, dir2, lon1, dir3, lon2, dir4
                lat1 = float(groups[0])
                if groups[1].upper() == "S":
                    lat1 = -lat1
                lat2 = float(groups[2])
                if groups[3].upper() == "S":
                    lat2 = -lat2

                lon1 = float(groups[4])
                if groups[5].upper() == "W":
                    lon1 = -lon1
                lon2 = float(groups[6])
                if groups[7].upper() == "W":
                    lon2 = -lon2

                return BoundingBox(
                    min_lat=min(lat1, lat2),
                    max_lat=max(lat1, lat2),
                    min_lon=min(lon1, lon2),
                    max_lon=max(lon1, lon2),
                    source_text=match.group(),
                    confidence=0.90,
                )

            elif pattern_type == "bounded_by":
                # Groups: lat1, lat2, lat_dir, lon1, lon2, lon_dir
                lat1 = float(groups[0])
                lat2 = float(groups[1])
                if groups[2].upper() == "S":
                    lat1, lat2 = -lat1, -lat2

                lon1 = float(groups[3])
                lon2 = float(groups[4])
                if groups[5].upper() == "W":
                    lon1, lon2 = -lon1, -lon2

                return BoundingBox(
                    min_lat=min(lat1, lat2),
                    max_lat=max(lat1, lat2),
                    min_lon=min(lon1, lon2),
                    max_lon=max(lon1, lon2),
                    source_text=match.group(),
                    confidence=0.90,
                )

            elif pattern_type == "extends_from_to":
                # Groups: lat1, dir1, lat2, dir2, lon1, dir3, lon2, dir4
                lat1 = float(groups[0])
                if groups[1].upper() == "S":
                    lat1 = -lat1
                lat2 = float(groups[2])
                if groups[3].upper() == "S":
                    lat2 = -lat2

                lon1 = float(groups[4])
                if groups[5].upper() == "W":
                    lon1 = -lon1
                lon2 = float(groups[6])
                if groups[7].upper() == "W":
                    lon2 = -lon2

                return BoundingBox(
                    min_lat=min(lat1, lat2),
                    max_lat=max(lat1, lat2),
                    min_lon=min(lon1, lon2),
                    max_lon=max(lon1, lon2),
                    source_text=match.group(),
                    confidence=0.90,
                )

            elif pattern_type == "bounded_decimal":
                # Groups: lat1, lat2, lon1, lon2
                lat1 = float(groups[0])
                lat2 = float(groups[1])
                lon1 = float(groups[2])
                lon2 = float(groups[3])

                return BoundingBox(
                    min_lat=min(lat1, lat2),
                    max_lat=max(lat1, lat2),
                    min_lon=min(lon1, lon2),
                    max_lon=max(lon1, lon2),
                    source_text=match.group(),
                    confidence=0.85,
                )

        except (ValueError, IndexError) as e:
            logger.debug(f"Failed to parse bounding box: {e}")
            return None

        return None

    def to_geo_entity(
        self, bbox: BoundingBox, section: str = "unknown"
    ) -> GeoEntity:
        """Convert a BoundingBox to a GeoEntity (using center point).

        Args:
            bbox: Bounding box to convert
            section: Document section name

        Returns:
            GeoEntity with center coordinates
        """
        center = bbox.center

        return GeoEntity(
            text=bbox.source_text,
            entity_type="BOUNDING_BOX",
            context=f"Study area extent: {bbox.source_text}",
            section=section,
            confidence=bbox.confidence,
            start_char=0,
            end_char=len(bbox.source_text),
            coordinates=center,
        )


# Singleton instance
_extractor: BoundingBoxExtractor | None = None


def get_bounding_box_extractor() -> BoundingBoxExtractor:
    """Get the bounding box extractor instance."""
    global _extractor
    if _extractor is None:
        _extractor = BoundingBoxExtractor()
    return _extractor
