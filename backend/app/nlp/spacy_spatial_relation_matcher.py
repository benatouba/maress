"""spaCy component for spatial relation detection using Matcher.

This component uses spaCy's Matcher with token-based patterns to detect
spatial relations, following spaCy best practices instead of regex.
"""

import json
from pathlib import Path
from typing import ClassVar

from spacy.language import Language
from spacy.matcher import Matcher
from spacy.tokens import Doc, Span
from spacy.util import filter_spans  # Phase 1: Use spaCy's optimized overlap filtering


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
            cls.DISTANCE_UNITS = ["km", "m", "miles"]
            cls.CARDINAL_DIRECTIONS = ["north", "south", "east", "west"]
            cls.HYDROLOGICAL_DIRECTIONS = ["upstream", "downstream"]
            cls.PROXIMITY_PREPS = ["near", "close", "adjacent"]
            cls.CONTAINMENT_PREPS = ["within", "inside", "around"]
            cls.DIRECTIONAL_PREPS = ["of", "from"]
            cls.LOCATION_PREPS = ["in", "at", "near", "on"]
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

        # Combine all direction types
        all_directions = self.CARDINAL_DIRECTIONS + self.HYDROLOGICAL_DIRECTIONS

        # Pattern: [NUM] [UNIT] [DIRECTION] of [LOCATION]
        # Example: "10 km north of Paris"
        self.matcher.add(
            "DISTANCE_DIRECTION",
            [
                [
                    {"LIKE_NUM": True},  # Distance number
                    {"LOWER": {"IN": self.DISTANCE_UNITS}},  # Unit
                    {"LOWER": {"IN": all_directions}},  # Direction
                    {"LOWER": {"IN": self.DIRECTIONAL_PREPS}},
                    {"ENT_TYPE": {"IN": ["LOC", "GPE", "FAC"]}, "OP": "+"},  # Location entity
                ]
            ],
            greedy="LONGEST",
        )

        # Pattern: [SPATIAL_PREP] [LOCATION]
        # Example: "near Paris", "adjacent to the river", "close to the station"
        self.matcher.add(
            "SPATIAL_PREPOSITION",
            [
                [
                    {"LOWER": {"IN": self.PROXIMITY_PREPS}},
                    {"LOWER": "to", "OP": "?"},  # Optional "to"
                    {"POS": "DET", "OP": "?"},  # Optional determiner
                    {"ENT_TYPE": {"IN": ["LOC", "GPE", "FAC"]}, "OP": "+"},  # Location
                ],
                [
                    {"LOWER": {"IN": self.CONTAINMENT_PREPS}},
                    {"POS": "DET", "OP": "?"},  # Optional determiner
                    {"ENT_TYPE": {"IN": ["LOC", "GPE", "FAC"]}, "OP": "+"},
                ],
            ],
            greedy="LONGEST",
        )

        # Pattern: [DIRECTION] of [LOCATION]
        # Example: "north of Paris", "east of the river"
        self.matcher.add(
            "DIRECTION_OF",
            [
                [
                    {"LOWER": {"IN": all_directions}},
                    {"LOWER": "of"},
                    {"POS": "DET", "OP": "?"},  # Optional determiner
                    {"ENT_TYPE": {"IN": ["LOC", "GPE", "FAC"]}, "OP": "+"},
                ]
            ],
            greedy="LONGEST",
        )

        # Pattern: [LOCATION_VERB] in/at/near [LOCATION]
        # Example: "located in California", "situated at the coast", "found near the river"
        self.matcher.add(
            "LOCATION_VERB",
            [
                [
                    {"LOWER": {"IN": self.LOCATION_VERBS}},
                    {"LOWER": {"IN": self.LOCATION_PREPS}},
                    {"POS": "DET", "OP": "?"},  # Optional determiner
                    {"ENT_TYPE": {"IN": ["LOC", "GPE", "FAC"]}, "OP": "+"},
                ],
                [
                    {"LOWER": {"IN": self.LOCATION_VERBS}},
                    {"LOWER": {"IN": self.LOCATION_PREPS}},
                    {"POS": "DET", "OP": "?"},  # Optional determiner
                    {"POS": {"IN": ["PROPN", "NOUN"]}, "OP": "+"},  # Location name (proper noun or noun)
                ],
            ],
            greedy="LONGEST",
        )

        # Pattern: [LOCATION] [DESCRIPTOR]
        # Example: "Amazon River basin", "Pacific Ocean region", "coastal area"
        self.matcher.add(
            "LOCATION_DESCRIPTOR",
            [
                [
                    {"ENT_TYPE": {"IN": ["LOC", "GPE"]}},
                    {"LOWER": {"IN": self.LOCATION_DESCRIPTORS}},
                ]
            ],
            greedy="LONGEST",
        )

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
        for match_id, start, end in matches:
            span = doc[start:end]

            # Phase 1.4: Use MARESS_SPATIAL_REL label to avoid namespace collisions
            # Create entity span
            ent_span = Span(doc, start, end, label="MARESS_SPATIAL_REL")
            ent_span._.spatial_relation_type = self.nlp.vocab.strings[match_id].lower()
            new_ents.append(ent_span)

        # Phase 1: Use spaCy's filter_spans() instead of manual overlap filtering
        # filter_spans automatically keeps longest spans and removes overlaps
        all_ents = list(doc.ents) + new_ents
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
