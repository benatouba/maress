"""spaCy component for coordinate detection using Matcher and regex.

This component follows spaCy best practices:
- Uses Matcher with greedy="LONGEST" for token-based patterns
- Uses regex for complex coordinate patterns
- Integrates seamlessly with spaCy's entity system
"""

import re

from spacy.language import Language
from spacy.matcher import Matcher
from spacy.tokens import Doc, Span
from spacy.util import filter_spans  # Phase 1: Use spaCy's optimized overlap filtering


class CoordinateMatcher:
    """spaCy component for detecting coordinates using Matcher and regex.

    Uses greedy longest-match strategy for overlapping patterns.
    Handles both well-formed and malformed coordinates from PDF extraction.
    """

    def __init__(self, nlp: Language, name: str = "coordinate_matcher") -> None:
        """Initialize the coordinate matcher component.

        Args:
            nlp: spaCy Language object
            name: Component name
        """
        self.name = name
        self.nlp = nlp

        self.matcher = Matcher(nlp.vocab)

        # Add token-based patterns (these align with token boundaries)
        self._add_token_patterns()

        # Store regex patterns for direct application
        self.regex_patterns = self._get_regex_patterns()

    def _add_token_patterns(self) -> None:
        """Add token-based coordinate patterns using spaCy Matcher.

        These patterns match structured formats that align with token boundaries.
        The greedy="LONGEST" ensures we get the longest match for overlaps.
        """
        # Pattern: Lat: 45.123, Lon: -122.456
        # Matches: "Lat:" or "Latitude:" followed by number, comma, "Lon:" or "Longitude:", number
        self.matcher.add(
            "LABELED_LATLON",
            [
                [
                    {"LOWER": {"IN": ["lat", "latitude"]}},
                    {"IS_PUNCT": True, "OP": "?"},  # Optional colon
                    {"IS_SPACE": True, "OP": "*"},  # Optional spaces
                    {"LIKE_NUM": True},  # Latitude value
                    {"IS_PUNCT": True},  # Comma
                    {"IS_SPACE": True, "OP": "*"},
                    {"LOWER": {"IN": ["lon", "long", "longitude"]}},
                    {"IS_PUNCT": True, "OP": "?"},
                    {"IS_SPACE": True, "OP": "*"},
                    {"LIKE_NUM": True},  # Longitude value
                ]
            ],
            greedy="LONGEST",  # Prefer longest match
        )

        # Pattern: Lon: -122.456, Lat: 45.123 (reversed order)
        self.matcher.add(
            "LABELED_LONLAT",
            [
                [
                    {"LOWER": {"IN": ["lon", "long", "longitude"]}},
                    {"IS_PUNCT": True, "OP": "?"},
                    {"IS_SPACE": True, "OP": "*"},
                    {"LIKE_NUM": True},
                    {"IS_PUNCT": True},
                    {"IS_SPACE": True, "OP": "*"},
                    {"LOWER": {"IN": ["lat", "latitude"]}},
                    {"IS_PUNCT": True, "OP": "?"},
                    {"IS_SPACE": True, "OP": "*"},
                    {"LIKE_NUM": True},
                ]
            ],
            greedy="LONGEST",
        )

        # Pattern: Coordinates: 45.123, -122.456
        self.matcher.add(
            "PREFIXED_COORDS",
            [
                [
                    {"LOWER": {"IN": ["coordinates", "coords", "coordinate"]}},
                    {"IS_PUNCT": True, "OP": "?"},
                    {"IS_SPACE": True, "OP": "*"},
                    {"LIKE_NUM": True},
                    {"IS_PUNCT": True},
                    {"IS_SPACE": True, "OP": "*"},
                    {"LIKE_NUM": True},
                ]
            ],
            greedy="LONGEST",
        )

    def _get_regex_patterns(self) -> list[tuple[str, str, float]]:
        """Get regex-based patterns for coordinate matching.

        These patterns handle character-level coordinate formats that don't
        align with token boundaries (DMS, special symbols, PDF artifacts).

        Phase 1.4: Use MARESS_COORDINATE label to avoid namespace collisions.

        Returns:
            List of tuples (pattern, pattern_id, confidence)
        """
        patterns = [
            # === WELL-FORMED DMS/DM FORMATS ===
            # Degrees Minutes Seconds: 45°12'30"N, 122°30'15"W
            (
                r"\d+\s*[°º]\s*\d+\s*[\'′]\s*\d+\.?\d*\s*[\"″]\s*[NS]\s*,?\s*\d+\s*[°º]\s*\d+\s*[\'′]\s*\d+\.?\d*\s*[\"″]\s*[EW]",
                "dms",
                0.95,
            ),
            # Degrees Minutes: 45°12'N, 122°30'W
            (
                r"\d+\s*[°º]\s*\d+\s*[\'′]\s*[NS]\s*,?\s*\d+\s*[°º]\s*\d+\s*[\'′]\s*[EW]",
                "dm",
                0.90,
            ),
            # Decimal degrees with symbol: 45.123°N, 122.456°W
            (
                r"-?\d+\.\d+\s*°\s*[NS]?\s*,?\s*-?\d+\.\d+\s*°\s*[EW]?",
                "dd_symbol",
                0.85,
            ),
            # === MALFORMED PATTERNS - PDF Extraction Artifacts ===
            # Degree as "7" (OCR corruption): 45 7 12'N, 122 7 30'W
            (
                r"\d+\s+7\s+\d+\s*[\'′b9]\s*[NS]\s*,?\s*\d+\s+7\s+\d+\s*[\'′b9]\s*[EW]",
                "dm_deg7",
                0.70,
            ),
            # Degree as "o" or "O": 45o12'N, 122o30'W
            (
                r"\d+\s*[oO]\s*\d+\s*[\'′9]\s*[NS]\s*,?\s*\d+\s*[oO]\s*\d+\s*[\'′9]\s*[EW]",
                "dm_dego",
                0.70,
            ),
            # Degree as "u" (OCR corruption): 13 u 13 9 09 S, 74 u 57 9 45 W
            (
                r"\d+\s*u\s*\d+\s*[\'′b9]\s*\d*\.?\d*\s*[\"″]?\s*[NS]\s*,?\s*\d+\s*u\s*\d+\s*[\'′b9]\s*\d*\.?\d*\s*[\"″]?\s*[EW]",
                "dm_degu",
                0.65,
            ),
            # Minute as "b" (OCR corruption): 45°12bN, 122°30bW
            (
                r"\d+\s*[°7oOu]\s*\d+\s*[b9]\s*[NS]\s*,?\s*\d+\s*[°7oOu]\s*\d+\s*[b9]\s*[EW]",
                "dm_minb",
                0.70,
            ),
            # Compact decimal minutes: 00°01'.72N, 77°59'.13E
            (
                r"\d+\s*[°7oOu]\s*\d+\s*[\'′b9]\.?\d*\s*[NS]\s*,?\s*\d+\s*[°7oOu]\s*\d+\s*[\'′b9]\.?\d*\s*[EW]",
                "dm_compact",
                0.75,
            ),
            # DMS with "u" degree and "9" minute: 13 u 13 9 09 S (full format with seconds)
            (
                r"\d+\s*u\s*\d+\s*9\s*\d+\.?\d*\s*[NS]\s*,?\s*\d+\s*u\s*\d+\s*9\s*\d+\.?\d*\s*[EW]",
                "dms_u_9",
                0.65,
            ),
            # === SIMPLE FORMATS ===
            # Decimal pairs in parentheses: (45.123, -122.456) or (45.5, -122.3)
            (
                r"\(\s*-?\d+\.\d+\s*,\s*-?\d+\.\d+\s*\)",
                "parentheses",
                0.85,
            ),
            # Decimal pairs in brackets: [45.123, -122.456] or [45.5, -122.3]
            (
                r"\[\s*-?\d+\.\d+\s*,\s*-?\d+\.\d+\s*\]",
                "brackets",
                0.85,
            ),
            # Decimal with direction: 45.5 N, 122.3 W
            (
                r"\d+\.\d+\s+[NS]\s*,?\s*\d+\.\d+\s+[EW]",
                "dd_direction",
                0.80,
            ),
            # Signed decimals: +45.123, -122.456 or 45.5, -122.3 or -45.1, 122.4
            (
                r"[+-]?\d+\.\d+\s*,\s*[+-]?\d+\.\d+",
                "decimal_pair",
                0.80,
            ),
        ]

        return patterns

    def __call__(self, doc: Doc) -> Doc:
        """Process a Doc object and add coordinate entities.

        Args:
            doc: spaCy Doc object

        Returns:
            Doc with coordinate entities added
        """
        new_ents = []

        # First, apply regex patterns directly to text
        text = doc.text
        for pattern, pattern_id, confidence in self.regex_patterns:
            for match in re.finditer(pattern, text):
                # Find character span in doc
                start_char = match.start()
                end_char = match.end()

                # Convert character offsets to token offsets
                span = doc.char_span(start_char, end_char, alignment_mode="expand")
                if span is not None:
                    # Create entity span
                    ent_span = Span(doc, span.start, span.end, label="MARESS_COORDINATE")
                    ent_span._.coordinate_format = pattern_id
                    ent_span._.coordinate_confidence = confidence
                    new_ents.append(ent_span)

        # Then, apply Matcher (token patterns)
        # Matcher with greedy="LONGEST" automatically handles overlaps
        matches = self.matcher(doc)

        # Convert matches to entities
        for match_id, start, end in matches:
            span = doc[start:end]
            # Set custom attributes
            span._.coordinate_format = self.nlp.vocab.strings[match_id].lower()
            span._.coordinate_confidence = 0.90  # High confidence for structured patterns

            # Phase 1.4: Use MARESS_COORDINATE label to avoid namespace collisions
            # Create entity span
            ent_span = Span(doc, start, end, label="MARESS_COORDINATE")
            ent_span._.coordinate_format = span._.coordinate_format
            ent_span._.coordinate_confidence = span._.coordinate_confidence
            new_ents.append(ent_span)

        # Phase 1: Use spaCy's filter_spans() instead of manual overlap filtering
        # filter_spans automatically keeps longest spans and removes overlaps
        all_ents = list(doc.ents) + new_ents
        doc.ents = filter_spans(all_ents)

        return doc


# Register custom extensions for coordinate metadata
if not Span.has_extension("coordinate_format"):
    Span.set_extension("coordinate_format", default=None)
if not Span.has_extension("coordinate_confidence"):
    Span.set_extension("coordinate_confidence", default=None)


@Language.factory("coordinate_matcher")
def create_coordinate_matcher(nlp: Language, name: str) -> CoordinateMatcher:
    """Factory function for creating CoordinateMatcher component.

    Args:
        nlp: spaCy Language object
        name: Component name

    Returns:
        CoordinateMatcher instance
    """
    return CoordinateMatcher(nlp, name)
