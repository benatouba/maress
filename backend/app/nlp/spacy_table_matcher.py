"""spaCy component for table reference detection using Matcher.

This component uses spaCy's Matcher with token-based patterns to detect
table references, following spaCy best practices instead of regex.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from spacy.language import Language
from spacy.matcher import Matcher
from spacy.tokens import Span

if TYPE_CHECKING:
    from spacy.tokens import Doc


class TableMatcher:
    """spaCy component for detecting table references using Matcher.

    Detects patterns like:
    - "Table 1", "Table 2A"
    - "Supplementary Table 1", "Table S2"

    Uses token-based patterns with greedy longest matching.
    """

    def __init__(self, nlp: Language, name: str = "table_matcher") -> None:
        """Initialize the table matcher.

        Args:
            nlp: spaCy Language object
            name: Component name
        """
        self.name = name
        self.nlp = nlp

        # Initialize Matcher with greedy LONGEST
        self.matcher = Matcher(nlp.vocab, validate=True)

        # Add table reference patterns
        self._add_patterns()

    def _add_patterns(self) -> None:
        """Add token-based patterns for table references."""

        # Pattern: Table [NUMBER][LETTER?]
        # Example: "Table 1", "Table 2A"
        self.matcher.add(
            "TABLE",
            [
                [
                    {"LOWER": "table"},
                    {"IS_PUNCT": True, "OP": "?"},  # Optional period
                    {"IS_SPACE": True, "OP": "*"},  # Optional spaces
                    {"IS_DIGIT": True},  # Number
                    {"IS_ALPHA": True, "LENGTH": 1, "OP": "?"},  # Optional letter (e.g., "A" in "Table 1A")
                ]
            ],
            greedy="LONGEST",
        )

        # Pattern: Supplementary Table [NUMBER]
        # Example: "Supplementary Table 1", "Supplementary Table S2"
        self.matcher.add(
            "SUPPLEMENTARY_TABLE",
            [
                [
                    {"LOWER": "supplementary"},
                    {"LOWER": "table"},
                    {"IS_PUNCT": True, "OP": "?"},
                    {"IS_SPACE": True, "OP": "*"},
                    {"IS_DIGIT": True},
                    {"IS_ALPHA": True, "LENGTH": 1, "OP": "?"},
                ],
                [
                    {"LOWER": "table"},
                    {"TEXT": "S"},  # "S" prefix for supplementary
                    {"IS_DIGIT": True},
                    {"IS_ALPHA": True, "LENGTH": 1, "OP": "?"},
                ],
            ],
            greedy="LONGEST",
        )

    def __call__(self, doc: Doc) -> Doc:
        """Process a Doc object and add table reference entities.

        Args:
            doc: spaCy Doc object

        Returns:
            Doc with table reference entities added
        """
        # Get matches from Matcher (with greedy="LONGEST" handling overlaps)
        matches = self.matcher(doc)

        # Convert matches to entities
        new_ents = []
        for match_id, start, end in matches:
            span = doc[start:end]

            # Determine the reference type
            ref_type = self.nlp.vocab.strings[match_id].lower()

            # Create entity span
            ent_span = Span(doc, start, end, label="TABLE_REF")
            ent_span._.table_ref_type = ref_type
            new_ents.append(ent_span)

        # Merge with existing entities, filtering overlaps
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


# Register custom extension for table reference type
if not Span.has_extension("table_ref_type"):
    Span.set_extension("table_ref_type", default=None)


@Language.factory("table_matcher")
def create_table_matcher(nlp: Language, name: str) -> TableMatcher:
    """Factory function for creating TableMatcher component.

    Args:
        nlp: spaCy Language object
        name: Component name

    Returns:
        TableMatcher instance
    """
    return TableMatcher(nlp, name)
