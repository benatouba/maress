"""spaCy component for coordinate detection using Matcher and EntityRuler.

This component follows spaCy best practices:
- Uses Matcher with greedy="LONGEST" for token-based patterns
- Uses EntityRuler for regex patterns
- Integrates seamlessly with spaCy's entity system
"""

from spacy.language import Language
from spacy.matcher import Matcher
from spacy.pipeline import EntityRuler
from spacy.tokens import Doc, Span


class CoordinateMatcher:
    """spaCy component for detecting coordinates using Matcher and EntityRuler.

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

        # Initialize EntityRuler for regex patterns
        self.ruler = EntityRuler(nlp, validate=True, overwrite_ents=False)
        self._add_regex_patterns()

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

    def _add_regex_patterns(self) -> None:
        """Add regex-based patterns using EntityRuler.

        These patterns handle character-level coordinate formats that don't
        align with token boundaries (DMS, special symbols, PDF artifacts).
        EntityRuler integrates regex patterns into spaCy's entity system.
        """
        patterns = [
            # === WELL-FORMED DMS/DM FORMATS ===
            # Degrees Minutes Seconds: 45°12'30"N, 122°30'15"W
            {
                "label": "COORDINATE",
                "pattern": r"\d+\s*[°º]\s*\d+\s*[\'′]\s*\d+\.?\d*\s*[\"″]\s*[NS]\s*,?\s*\d+\s*[°º]\s*\d+\s*[\'′]\s*\d+\.?\d*\s*[\"″]\s*[EW]",
                "id": "dms",
            },
            # Degrees Minutes: 45°12'N, 122°30'W
            {
                "label": "COORDINATE",
                "pattern": r"\d+\s*[°º]\s*\d+\s*[\'′]\s*[NS]\s*,?\s*\d+\s*[°º]\s*\d+\s*[\'′]\s*[EW]",
                "id": "dm",
            },
            # Decimal degrees with symbol: 45.123°N, 122.456°W
            {
                "label": "COORDINATE",
                "pattern": r"-?\d+\.\d+\s*°\s*[NS]?\s*,?\s*-?\d+\.\d+\s*°\s*[EW]?",
                "id": "dd_symbol",
            },
            # === MALFORMED PATTERNS - PDF Extraction Artifacts ===
            # Degree as "7" (OCR corruption): 45 7 12'N, 122 7 30'W
            {
                "label": "COORDINATE",
                "pattern": r"\d+\s+7\s+\d+\s*[\'′b]\s*[NS]\s*,?\s*\d+\s+7\s+\d+\s*[\'′b]\s*[EW]",
                "id": "dm_deg7",
            },
            # Degree as "o" or "O": 45o12'N, 122o30'W
            {
                "label": "COORDINATE",
                "pattern": r"\d+\s*[oO]\s*\d+\s*[\'′]\s*[NS]\s*,?\s*\d+\s*[oO]\s*\d+\s*[\'′]\s*[EW]",
                "id": "dm_dego",
            },
            # Minute as "b" (OCR corruption): 45°12bN, 122°30bW
            {
                "label": "COORDINATE",
                "pattern": r"\d+\s*[°7oO]\s*\d+\s*[b]\s*[NS]\s*,?\s*\d+\s*[°7oO]\s*\d+\s*[b]\s*[EW]",
                "id": "dm_minb",
            },
            # Compact decimal minutes: 00°01'.72N, 77°59'.13E
            {
                "label": "COORDINATE",
                "pattern": r"\d+\s*[°7oO]\s*\d+\s*[\'′b]\.?\d*\s*[NS]\s*,?\s*\d+\s*[°7oO]\s*\d+\s*[\'′b]\.?\d*\s*[EW]",
                "id": "dm_compact",
            },
            # === SIMPLE FORMATS ===
            # Decimal pairs in parentheses: (45.123, -122.456)
            {
                "label": "COORDINATE",
                "pattern": r"\(\s*-?\d+\.\d{2,}\s*,\s*-?\d+\.\d{2,}\s*\)",
                "id": "parentheses",
            },
            # Decimal pairs in brackets: [45.123, -122.456]
            {
                "label": "COORDINATE",
                "pattern": r"\[\s*-?\d+\.\d{2,}\s*,\s*-?\d+\.\d{2,}\s*\]",
                "id": "brackets",
            },
            # Decimal with direction: 45.5 N, 122.3 W
            {
                "label": "COORDINATE",
                "pattern": r"\d+\.\d+\s+[NS]\s*,?\s*\d+\.\d+\s+[EW]",
                "id": "dd_direction",
            },
            # Signed decimals: +45.123, -122.456 or -45.123, 122.456
            {
                "label": "COORDINATE",
                "pattern": r"[+-]?\d+\.\d{2,}\s*,\s*[+-]?\d+\.\d{2,}",
                "id": "decimal_pair",
            },
        ]

        self.ruler.add_patterns(patterns)

    def __call__(self, doc: Doc) -> Doc:
        """Process a Doc object and add coordinate entities.

        Args:
            doc: spaCy Doc object

        Returns:
            Doc with coordinate entities added
        """
        # First, apply EntityRuler (regex patterns)
        doc = self.ruler(doc)

        # Then, apply Matcher (token patterns)
        # Matcher with greedy="LONGEST" automatically handles overlaps
        matches = self.matcher(doc)

        # Convert matches to entities
        new_ents = []
        for match_id, start, end in matches:
            span = doc[start:end]
            # Set custom attributes
            span._.coordinate_format = self.nlp.vocab.strings[match_id].lower()
            span._.coordinate_confidence = 0.90  # High confidence for structured patterns

            # Create entity span
            ent_span = Span(doc, start, end, label="COORDINATE")
            ent_span._.coordinate_format = span._.coordinate_format
            ent_span._.coordinate_confidence = span._.coordinate_confidence
            new_ents.append(ent_span)

        # Merge with existing entities, keeping longest spans
        all_ents = list(doc.ents) + new_ents
        doc.ents = self._filter_overlapping_entities(all_ents)

        return doc

    def _filter_overlapping_entities(self, entities: list[Span]) -> tuple[Span, ...]:
        """Filter overlapping entities, keeping longest spans (greedy).

        Args:
            entities: List of entity spans

        Returns:
            Tuple of non-overlapping entities, sorted by position
        """
        if not entities:
            return tuple()

        # Sort by: length (longest first), then by start position
        sorted_ents = sorted(
            entities,
            key=lambda e: (-(e.end - e.start), e.start)
        )

        filtered = []
        occupied_positions = set()

        for ent in sorted_ents:
            # Check if any token position is already occupied
            positions = set(range(ent.start, ent.end))
            if not positions.intersection(occupied_positions):
                filtered.append(ent)
                occupied_positions.update(positions)

        # Sort by document position for final output
        return tuple(sorted(filtered, key=lambda e: e.start))


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
