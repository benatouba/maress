"""spaCy component for multi-word location detection using PhraseMatcher.

This component uses spaCy's PhraseMatcher to detect complex geographic names
that are often missed by standard NER, improving study site detection accuracy.
"""

import json
from pathlib import Path
from typing import ClassVar

from spacy.language import Language
from spacy.matcher import PhraseMatcher
from spacy.tokens import Doc, Span
from spacy.util import filter_spans  # Phase 1: Use spaCy's optimized overlap filtering


class MultiWordLocationMatcher:
    """spaCy component for detecting multi-word geographic locations.

    Detects complex location names like:
    - "San Francisco Bay Area"
    - "Mount Hood National Forest"
    - "Columbia River Gorge"
    - "Pacific Northwest"
    - "Amazon River Basin"

    Uses PhraseMatcher for exact and fuzzy matching of known locations.
    """

    # Phase 1: Geographic locations externalized to JSONL file
    GEOGRAPHIC_LOCATIONS: ClassVar[list[str]] = []
    DATA_DIR: ClassVar[Path] = Path(__file__).parent / "data"

    @classmethod
    def _load_geographic_locations(cls) -> None:
        """Load geographic locations from JSONL file.

        Phase 1 Best Practice: Externalize vocabularies to JSONL for:
        - Easy updates without code changes
        - Version control
        - Domain-specific customization
        - User contributions
        """
        if cls.GEOGRAPHIC_LOCATIONS:  # Already loaded
            return

        locations_file = cls.DATA_DIR / "geographic_locations.jsonl"
        if locations_file.exists():
            with open(locations_file) as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        cls.GEOGRAPHIC_LOCATIONS.append(data["text"])
        else:
            # Fallback to minimal set if file not found
            cls.GEOGRAPHIC_LOCATIONS = [
                "Yellowstone National Park",
                "Amazon Rainforest",
                "Great Barrier Reef",
            ]

    # Patterns to expand location names
    LOCATION_MODIFIERS: ClassVar[list[str]] = [
        "northern", "southern", "eastern", "western",
        "upper", "lower", "central", "coastal",
        "greater", "outer", "inner",
    ]

    def __init__(self, nlp: Language, name: str = "multiword_location_matcher") -> None:
        """Initialize the multi-word location matcher.

        Args:
            nlp: spaCy Language object
            name: Component name
        """
        self.name = name
        self.nlp = nlp

        # Phase 1: Load geographic locations from JSONL file
        self._load_geographic_locations()

        # Initialize PhraseMatcher
        self.matcher = PhraseMatcher(nlp.vocab, attr="LOWER")

        # Add phrase patterns
        self._add_patterns()

    def _add_patterns(self) -> None:
        """Add phrase patterns for multi-word locations."""
        # Convert location strings to Doc patterns
        patterns = [self.nlp.make_doc(text.lower()) for text in self.GEOGRAPHIC_LOCATIONS]
        self.matcher.add("MULTIWORD_LOCATION", patterns)

        # Add patterns with modifiers
        # e.g., "northern California", "upper Mississippi River"
        modifier_patterns = []
        for modifier in self.LOCATION_MODIFIERS:
            for location in ["California", "Oregon", "Washington", "Nevada",
                           "Arizona", "Montana", "Colorado", "Wyoming"]:
                pattern_text = f"{modifier} {location}".lower()
                modifier_patterns.append(self.nlp.make_doc(pattern_text))

        self.matcher.add("MODIFIED_LOCATION", modifier_patterns)

    def __call__(self, doc: Doc) -> Doc:
        """Process a Doc object and add multi-word location entities.

        Args:
            doc: spaCy Doc object

        Returns:
            Doc with multi-word location entities added
        """
        matches = self.matcher(doc)

        new_ents = []
        seen_spans = set()

        for match_id, start, end in matches:
            # Create span
            span = doc[start:end]

            # Skip if overlaps with existing span
            span_key = (start, end)
            if span_key in seen_spans:
                continue

            seen_spans.add(span_key)

            # Check if this span overlaps with an existing entity
            overlaps = False
            for existing_ent in doc.ents:
                if (start < existing_ent.end and end > existing_ent.start):
                    # Prefer the longer span
                    if (end - start) > (existing_ent.end - existing_ent.start):
                        # Our span is longer, we'll add it and filter later
                        pass
                    else:
                        overlaps = True
                        break

            if overlaps:
                continue

            # Phase 1.4: Use MARESS_MULTIWORD_LOC label to avoid namespace collisions
            # Create entity span
            try:
                ent_span = Span(doc, start, end, label="MARESS_MULTIWORD_LOC")
                ent_span._.is_multiword_location = True
                ent_span._.location_type = self.nlp.vocab.strings[match_id].lower()
                new_ents.append(ent_span)
            except ValueError:
                continue

        # Phase 1: Use spaCy's filter_spans() instead of manual overlap filtering
        # filter_spans automatically keeps longest spans and removes overlaps
        all_ents = list(doc.ents) + new_ents
        doc.ents = filter_spans(all_ents)

        return doc

    def add_custom_locations(self, locations: list[str]) -> None:
        """Add custom location phrases to the matcher.

        This allows domain-specific locations to be added dynamically.

        Args:
            locations: List of location name strings
        """
        patterns = [self.nlp.make_doc(text.lower()) for text in locations]
        self.matcher.add("CUSTOM_LOCATION", patterns)


# Register custom extensions
if not Span.has_extension("is_multiword_location"):
    Span.set_extension("is_multiword_location", default=False)
if not Span.has_extension("location_type"):
    Span.set_extension("location_type", default=None)


@Language.factory("multiword_location_matcher")
def create_multiword_location_matcher(
    nlp: Language, name: str
) -> MultiWordLocationMatcher:
    """Factory function for creating MultiWordLocationMatcher component.

    Args:
        nlp: spaCy Language object
        name: Component name

    Returns:
        MultiWordLocationMatcher instance
    """
    return MultiWordLocationMatcher(nlp, name)
