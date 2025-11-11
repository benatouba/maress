"""spaCy component for coordinate detection using regex patterns.

This component integrates coordinate detection directly into the spaCy pipeline,
allowing for better handling of malformed coordinates and special character corruptions.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, ClassVar

from spacy.language import Language
from spacy.matcher import Matcher
from spacy.tokens import Doc, Span

if TYPE_CHECKING:
    from spacy.vocab import Vocab


class CoordinateMatcher:
    """spaCy component that detects coordinate patterns using regex.

    This component adds coordinate entities directly to doc.ents, making them
    available to the standard spaCy pipeline. It handles both well-formed and
    malformed coordinates with special character corruptions.
    """

    # Comprehensive coordinate patterns - ordered by priority
    # Each pattern includes variations for malformed special characters
    COORDINATE_PATTERNS: ClassVar[list[tuple[str, str, float]]] = [
        # === WELL-FORMED PATTERNS (Priority 1) ===

        # Simple decimal pairs: 45.123, -122.456
        (
            r"(-?\d+\.\d{2,})\s*,\s*(-?\d+\.\d{2,})",
            "decimal_pair",
            0.95,
        ),

        # Degrees minutes seconds (DMS): 45°12'30"N, 122°30'15"W
        (
            r"(\d+)\s*[°]\s*(\d+)\s*[\'′]\s*(\d+\.?\d*)\s*[\"″]\s*([NS])\s*,?\s*(\d+)\s*[°]\s*(\d+)\s*[\'′]\s*(\d+\.?\d*)\s*[\"″]\s*([EW])",
            "dms",
            1.0,
        ),

        # Degrees minutes (DM): 45°12'N, 122°30'W
        (
            r"(\d+)\s*[°]\s*(\d+)\s*[\'′]\s*([NS])\s*,?\s*(\d+)\s*[°]\s*(\d+)\s*[\'′]\s*([EW])",
            "dm",
            0.90,
        ),

        # Decimal degrees with degree symbol: 45.123°N, 122.456°W
        (
            r"(-?\d+\.\d+)\s*°\s*([NS])?\s*,?\s*(-?\d+\.\d+)\s*°\s*([EW])?",
            "dd_symbol",
            0.85,
        ),

        # === MALFORMED PATTERNS - Degree Symbol Corruptions (Priority 2) ===

        # Degree as "7" (spaCy-layout corruption): 45 7 12'N, 122 7 30'W
        (
            r"(\d+)\s+7\s+(\d+)\s*[\'′b]\s*([NS])\s*,?\s*(\d+)\s+7\s+(\d+)\s*[\'′b]\s*([EW])",
            "dm_deg7",
            0.80,
        ),

        # Degree as "o" or "O": 45o12'N, 122o30'W or 45 o 12'N
        (
            r"(\d+)\s*[oO]\s*(\d+)\s*[\'′]\s*([NS])\s*,?\s*(\d+)\s*[oO]\s*(\d+)\s*[\'′]\s*([EW])",
            "dm_dego",
            0.80,
        ),

        # Degree as "º" (ordinal): 45º12'N, 122º30'W
        (
            r"(\d+)\s*[º]\s*(\d+)\s*[\'′]\s*([NS])\s*,?\s*(\d+)\s*[º]\s*(\d+)\s*[\'′]\s*([EW])",
            "dm_degord",
            0.80,
        ),

        # Degree with UTF-8 corruption "Â°": 45Â°12'N, 122Â°30'W
        (
            r"(\d+)\s*[Â]?[°º]\s*(\d+)\s*[\'′]\s*([NS])\s*,?\s*(\d+)\s*[Â]?[°º]\s*(\d+)\s*[\'′]\s*([EW])",
            "dm_degutf8",
            0.80,
        ),

        # === MALFORMED PATTERNS - Minute Symbol Corruptions (Priority 3) ===

        # Minute as "b" (spaCy-layout corruption): 45°12bN, 122°30bW
        (
            r"(\d+)\s*[°7o]\s*(\d+)\s*[b]\s*([NS])\s*,?\s*(\d+)\s*[°7o]\s*(\d+)\s*[b]\s*([EW])",
            "dm_minb",
            0.75,
        ),

        # Minute as backtick "`": 45°12`N, 122°30`W
        (
            r"(\d+)\s*[°]\s*(\d+)\s*[`]\s*([NS])\s*,?\s*(\d+)\s*[°]\s*(\d+)\s*[`]\s*([EW])",
            "dm_minbt",
            0.75,
        ),

        # Minute as acute "´": 45°12´N, 122°30´W
        (
            r"(\d+)\s*[°]\s*(\d+)\s*[´]\s*([NS])\s*,?\s*(\d+)\s*[°]\s*(\d+)\s*[´]\s*([EW])",
            "dm_minac",
            0.75,
        ),

        # === MALFORMED PATTERNS - DMS Corruptions (Priority 4) ===

        # Full DMS with degree as "7" and minute as "b": 45 7 12 b 30"N
        (
            r"(\d+)\s+7\s+(\d+)\s+b\s+(\d+\.?\d*)\s*[\"″]\s*([NS])\s*,?\s*(\d+)\s+7\s+(\d+)\s+b\s+(\d+\.?\d*)\s*[\"″]\s*([EW])",
            "dms_7b",
            0.75,
        ),

        # DMS with all symbols corrupted: 45o12b30cN (c for seconds)
        (
            r"(\d+)\s*[oO7]\s*(\d+)\s*[b\'′`]\s*(\d+\.?\d*)\s*[c\"″]\s*([NS])\s*,?\s*(\d+)\s*[oO7]\s*(\d+)\s*[b\'′`]\s*(\d+\.?\d*)\s*[c\"″]\s*([EW])",
            "dms_corrupted",
            0.70,
        ),

        # === MALFORMED PATTERNS - Spacing Issues (Priority 5) ===

        # Excessive spacing: 45 ° 12 ' N, 122 ° 30 ' W
        (
            r"(\d+)\s+°\s+(\d+)\s+[\'′]\s+([NS])\s*,?\s*(\d+)\s+°\s+(\d+)\s+[\'′]\s+([EW])",
            "dm_spaced",
            0.70,
        ),

        # Compact format with decimal minute: 00°01'.72N, 77°59'.13E
        (
            r"(\d+)\s*[°7o]\s*(\d+)\s*[\'′b]\.(\d+)\s*([NS])\s*,?\s*(\d+)\s*[°7o]\s*(\d+)\s*[\'′b]\.(\d+)\s*([EW])",
            "dm_compact",
            0.85,
        ),

        # === ALTERNATIVE FORMATS (Priority 6) ===

        # With labels: Lat: 45.123, Lon: -122.456
        (
            r"(?:Lat|Latitude|lat|latitude)[:\s]*(-?\d+\.\d+)[,\s]*(?:Lon|Longitude|long|longitude)[:\s]*(-?\d+\.\d+)",
            "labeled_latlon",
            0.90,
        ),

        # With labels reversed: Lon: -122.456, Lat: 45.123
        (
            r"(?:Lon|Longitude|long|longitude)[:\s]*(-?\d+\.\d+)[,\s]*(?:Lat|Latitude|lat|latitude)[:\s]*(-?\d+\.\d+)",
            "labeled_lonlat",
            0.90,
        ),

        # In parentheses: (45.123, -122.456)
        (
            r"\(\s*(-?\d+\.\d{2,})\s*,\s*(-?\d+\.\d{2,})\s*\)",
            "parentheses",
            0.85,
        ),

        # In brackets: [45.123, -122.456]
        (
            r"\[\s*(-?\d+\.\d{2,})\s*,\s*(-?\d+\.\d{2,})\s*\]",
            "brackets",
            0.85,
        ),

        # Without symbols (requires direction): 45.5 N, 122.3 W
        (
            r"(\d+\.\d+)\s+([NS])\s*,?\s*(\d+\.\d+)\s+([EW])",
            "dd_direction",
            0.75,
        ),

        # === EDGE CASES (Priority 7) ===

        # Range format (extract midpoint): 45.1-45.2°N, 122.3-122.5°W
        (
            r"(\d+\.\d+)\s*-\s*(\d+\.\d+)\s*°?\s*([NS])\s*,?\s*(\d+\.\d+)\s*-\s*(\d+\.\d+)\s*°?\s*([EW])",
            "range",
            0.60,
        ),

        # With explicit signs: +45.123, -122.456
        (
            r"([+-]\d+\.\d{2,})\s*,\s*([+-]\d+\.\d{2,})",
            "signed",
            0.80,
        ),
    ]

    def __init__(self, nlp: Language, name: str = "coordinate_matcher") -> None:
        """Initialize the coordinate matcher component.

        Args:
            nlp: spaCy Language object
            name: Component name
        """
        self.name = name
        self.nlp = nlp

        # Compile all patterns for efficiency
        self.compiled_patterns = [
            (re.compile(pattern, re.IGNORECASE), format_type, confidence)
            for pattern, format_type, confidence in self.COORDINATE_PATTERNS
        ]

    def __call__(self, doc: Doc) -> Doc:
        """Process a Doc object and add coordinate entities.

        Args:
            doc: spaCy Doc object

        Returns:
            Doc with coordinate entities added
        """
        # Extract coordinates using patterns
        new_ents = []
        seen_positions = set()

        for pattern, format_type, confidence in self.compiled_patterns:
            for match in pattern.finditer(doc.text):
                start_char = match.start()
                end_char = match.end()

                # Avoid overlapping matches
                position = (start_char, end_char)
                if position in seen_positions:
                    continue

                # Check if overlaps with existing matches
                if any(s <= start_char < e or s < end_char <= e
                       for s, e in seen_positions):
                    continue

                seen_positions.add(position)

                # Create span for this match
                span = doc.char_span(
                    start_char,
                    end_char,
                    label="COORDINATE",
                    alignment_mode="expand"
                )

                if span is not None:
                    # Store metadata
                    span._.coordinate_format = format_type
                    span._.coordinate_confidence = confidence
                    new_ents.append(span)

        # Add new entities to doc.ents (merge with existing)
        try:
            doc.ents = list(doc.ents) + new_ents
        except ValueError:
            # If there are overlapping entities, filter them
            doc.ents = self._filter_overlapping_entities(list(doc.ents) + new_ents)

        return doc

    def _filter_overlapping_entities(self, entities: list[Span]) -> list[Span]:
        """Filter out overlapping entities, keeping higher priority ones.

        Args:
            entities: List of Span entities

        Returns:
            Filtered list without overlaps
        """
        # Sort by start position, then by length (longer first)
        sorted_ents = sorted(
            entities,
            key=lambda e: (e.start_char, -(e.end_char - e.start_char))
        )

        filtered = []
        for ent in sorted_ents:
            # Check if this entity overlaps with any already filtered entities
            overlaps = False
            for filtered_ent in filtered:
                if (ent.start_char < filtered_ent.end_char and
                    ent.end_char > filtered_ent.start_char):
                    overlaps = True
                    break

            if not overlaps:
                filtered.append(ent)

        return filtered


# Register custom extensions for coordinate metadata
if not Span.has_extension("coordinate_format"):
    Span.set_extension("coordinate_format", default=None)
if not Span.has_extension("coordinate_confidence"):
    Span.set_extension("coordinate_confidence", default=None)


# Factory function for spaCy
@Language.factory("coordinate_matcher")
def create_coordinate_matcher(nlp, name):
    """Factory function for creating CoordinateMatcher component.

    Args:
        nlp: spaCy Language object
        name: Component name

    Returns:
        CoordinateMatcher instance
    """
    return CoordinateMatcher(nlp, name)
