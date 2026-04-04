"""spaCy component for coordinate detection using Matcher and regex.

This component follows spaCy best practices:
- Uses Matcher with greedy="LONGEST" for token-based patterns
- Uses regex for complex coordinate patterns
- Integrates seamlessly with spaCy's entity system
"""

from __future__ import annotations

import re

from spacy.language import Language
from spacy.matcher import Matcher
from spacy.tokens import Doc, Span
from spacy.util import filter_spans  # Phase 1: Use spaCy's optimized overlap filtering

from app.nlp.pattern_registry import PatternRegistry


class CoordinateMatcher:
    """spaCy component for detecting coordinates using Matcher and regex.

    Uses greedy longest-match strategy for overlapping patterns.
    Handles both well-formed and malformed coordinates from PDF extraction.
    """

    PATTERN_CONFIDENCE = {
        "dms": 0.95,
        "dm": 0.90,
        "dd_symbol": 0.85,
        "parentheses": 0.85,
        "brackets": 0.85,
        "dd_direction": 0.80,
        "decimal_pair": 0.80,
        "dm_compact": 0.75,
        "dm_deg7": 0.70,
        "dm_dego": 0.70,
        "dm_minb": 0.70,
        "dms_u_9": 0.65,
        "dm_u": 0.65,
    }

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
        token_patterns = PatternRegistry.get_coordinate_token_patterns()

        for pattern_name, pattern_list in token_patterns.items():
            self.matcher.add(pattern_name, pattern_list, greedy="LONGEST")

    def _get_regex_patterns(self) -> list[tuple[str, str, float]]:
        """Get regex-based patterns for coordinate matching.

        These patterns handle character-level coordinate formats that don't
        align with token boundaries (DMS, special symbols, PDF artifacts).

        Phase 1.4: Use MARESS_COORDINATE label to avoid namespace collisions.

        Returns:
            List of tuples (pattern, pattern_id, confidence)
        """
        patterns: list[tuple[str, str, float]] = []

        for entry in PatternRegistry.get_coordinate_regex_patterns():
            pattern_id = entry["id"]
            confidence = self.PATTERN_CONFIDENCE.get(pattern_id, 0.75)
            patterns.append((entry["pattern"], pattern_id, confidence))

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
