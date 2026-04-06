"""spaCy component for spatial relation detection using Matcher.

This component uses spaCy's Matcher with token-based patterns to detect
spatial relations, following spaCy best practices instead of regex.
"""

from __future__ import annotations

import re

import json
from pathlib import Path
from typing import ClassVar

from spacy.language import Language
from spacy.matcher import Matcher
from spacy.tokens import Doc, Span
from spacy.util import filter_spans  # Phase 1: Use spaCy's optimized overlap filtering

from app.nlp.pattern_registry import PatternRegistry


ADJACENT_FALLBACK_RE = re.compile(
    r"adjacent\s+to\s+(?:the\s+)?(?:national\s+|state\s+|regional\s+)?[a-z]+(?:\s+[a-z]+){0,3}",
    re.IGNORECASE,
)


class SpatialRelationMatcher:
    """spaCy component for detecting spatial relation phrases using Matcher.

    Detects patterns like:
    - "10 km north of Paris"
    - "near the Amazon River"
    - "adjacent to the research station"
    - "located in California"

    Uses token-based patterns with greedy longest matching.
    """

    # Phase 1: Vocabularies externalized to JSON for easy updates
    DISTANCE_UNITS: ClassVar[list[str]] = []
    CARDINAL_DIRECTIONS: ClassVar[list[str]] = []
    HYDROLOGICAL_DIRECTIONS: ClassVar[list[str]] = []
    PROXIMITY_PREPS: ClassVar[list[str]] = []
    CONTAINMENT_PREPS: ClassVar[list[str]] = []
    DIRECTIONAL_PREPS: ClassVar[list[str]] = []
    LOCATION_PREPS: ClassVar[list[str]] = []
    LOCATION_VERBS: ClassVar[list[str]] = []
    LOCATION_DESCRIPTORS: ClassVar[list[str]] = []
    DATA_DIR: ClassVar[Path] = Path(__file__).parent / "data"

    @classmethod
    def _load_vocabularies(cls) -> None:
        """Load vocabularies from JSON file.

        Phase 1 Best Practice: Externalize vocabularies to JSON for:
        - Easy updates without code changes
        - Version control
        - Domain-specific customization
        - User contributions
        """
        if cls.DISTANCE_UNITS:  # Already loaded
            return

        vocab_file = cls.DATA_DIR / "spatial_relations.json"
        if vocab_file.exists():
            with open(vocab_file) as f:
                data = json.load(f)
                categories = data["categories"]

                cls.DISTANCE_UNITS = categories["distance_units"]["units"]
                cls.CARDINAL_DIRECTIONS = categories["cardinal_directions"]["directions"]
                cls.HYDROLOGICAL_DIRECTIONS = categories["hydrological_directions"]["directions"]
                cls.PROXIMITY_PREPS = categories["proximity_prepositions"]["prepositions"]
                cls.CONTAINMENT_PREPS = categories["containment_prepositions"]["prepositions"]
                cls.DIRECTIONAL_PREPS = categories["directional_prepositions"]["prepositions"]
                cls.LOCATION_PREPS = categories["location_prepositions"]["prepositions"]
                cls.LOCATION_VERBS = categories["location_verbs"]["verbs"]
                cls.LOCATION_DESCRIPTORS = categories["location_descriptors"]["descriptors"]
        else:
            # Fallback to minimal sets if file not found
            cls.DISTANCE_UNITS = ["km", "kilometers", "kilometer", "m", "meters", "meter", "miles", "mile"]
            cls.CARDINAL_DIRECTIONS = ["north", "south", "east", "west", "northeast", "northwest", "southeast", "southwest"]
            cls.HYDROLOGICAL_DIRECTIONS = ["upstream", "downstream", "offshore"]
            cls.PROXIMITY_PREPS = ["near", "close", "adjacent"]
            cls.CONTAINMENT_PREPS = ["within", "inside", "around"]
            cls.DIRECTIONAL_PREPS = ["of", "from"]
            cls.LOCATION_PREPS = ["in", "at", "near", "on", "along"]
            cls.LOCATION_VERBS = ["located", "situated", "positioned"]
            cls.LOCATION_DESCRIPTORS = ["region", "area", "basin"]

    def __init__(self, nlp: Language, name: str = "spatial_relation_matcher") -> None:
        """Initialize the spatial relation matcher.

        Args:
            nlp: spaCy Language object
            name: Component name
        """
        self.name = name
        self.nlp = nlp

        # Phase 1: Load vocabularies from JSON file
        self._load_vocabularies()

        # Initialize Matcher with greedy LONGEST
        self.matcher = Matcher(nlp.vocab, validate=True)

        # Add spatial relation patterns
        self._add_patterns()

    def _add_patterns(self) -> None:
        """Add token-based patterns for spatial relations."""

        all_directions = self.CARDINAL_DIRECTIONS + self.HYDROLOGICAL_DIRECTIONS
        patterns = PatternRegistry.get_spatial_relation_token_patterns(
            distance_units=self.DISTANCE_UNITS,
            all_directions=all_directions,
            directional_preps=self.DIRECTIONAL_PREPS,
            proximity_preps=self.PROXIMITY_PREPS,
            containment_preps=self.CONTAINMENT_PREPS,
            location_verbs=self.LOCATION_VERBS,
            location_preps=self.LOCATION_PREPS,
            location_descriptors=self.LOCATION_DESCRIPTORS,
        )

        for pattern_name, pattern_list in patterns.items():
            self.matcher.add(pattern_name, pattern_list, greedy="LONGEST")

    def __call__(self, doc: Doc) -> Doc:
        """Process a Doc object and add spatial relation entities.

        Args:
            doc: spaCy Doc object

        Returns:
            Doc with spatial relation entities added
        """
        # Get matches from Matcher (with greedy="LONGEST" handling overlaps)
        matches = self.matcher(doc)

        # Convert matches to entities
        new_ents = []
        match_span_keys: set[tuple[int, int]] = set()
        for match_id, start, end in matches:
            span = doc[start:end]
            match_span_keys.add((span.start_char, span.end_char))

            # Phase 1.4: Use MARESS_SPATIAL_REL label to avoid namespace collisions
            # Create entity span
            ent_span = Span(doc, start, end, label="MARESS_SPATIAL_REL")
            ent_span._.spatial_relation_type = self.nlp.vocab.strings[match_id].lower()
            new_ents.append(ent_span)

        # Add short fallback spans for adjacency-like phrases that may be
        # swallowed by longer greedy matches.
        for token in doc:
            if token.lower_ != "adjacent":
                continue

            # Use compact fallback span to avoid overlap suppression.
            span = doc[token.i : token.i + 1]
            span_key = (span.start_char, span.end_char)
            if span_key in match_span_keys:
                continue

            ent_span = Span(doc, span.start, span.end, label="MARESS_SPATIAL_REL")
            ent_span._.spatial_relation_type = "spatial_preposition"
            new_ents.append(ent_span)
            match_span_keys.add(span_key)

        # Regex fallback for adjacency phrases in noisy tagger parses.
        for match in ADJACENT_FALLBACK_RE.finditer(doc.text):
            span = doc.char_span(match.start(), match.end(), alignment_mode="expand")
            if span is None:
                continue
            span_key = (span.start_char, span.end_char)
            if span_key in match_span_keys:
                continue

            ent_span = Span(doc, span.start, span.end, label="MARESS_SPATIAL_REL")
            ent_span._.spatial_relation_type = "spatial_preposition"
            new_ents.append(ent_span)
            match_span_keys.add(span_key)

        # Phase 1: Use spaCy's filter_spans() instead of manual overlap filtering
        # filter_spans automatically keeps longest spans and removes overlaps
        all_ents = new_ents + list(doc.ents)
        doc.ents = filter_spans(all_ents)

        return doc


# Register custom extension for spatial relation type
if not Span.has_extension("spatial_relation_type"):
    Span.set_extension("spatial_relation_type", default=None)


@Language.factory("spatial_relation_matcher")
def create_spatial_relation_matcher(nlp: Language, name: str) -> SpatialRelationMatcher:
    """Factory function for creating SpatialRelationMatcher component.

    Args:
        nlp: spaCy Language object
        name: Component name

    Returns:
        SpatialRelationMatcher instance
    """
    return SpatialRelationMatcher(nlp, name)
