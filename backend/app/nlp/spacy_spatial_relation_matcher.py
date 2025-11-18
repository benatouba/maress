"""spaCy component for spatial relation detection using Matcher.

This component uses spaCy's Matcher with token-based patterns to detect
spatial relations, following spaCy best practices instead of regex.
"""

from spacy.language import Language
from spacy.matcher import Matcher
from spacy.tokens import Doc, Span


class SpatialRelationMatcher:
    """spaCy component for detecting spatial relation phrases using Matcher.

    Detects patterns like:
    - "10 km north of Paris"
    - "near the Amazon River"
    - "adjacent to the research station"
    - "located in California"

    Uses token-based patterns with greedy longest matching.
    """

    def __init__(self, nlp: Language, name: str = "spatial_relation_matcher") -> None:
        """Initialize the spatial relation matcher.

        Args:
            nlp: spaCy Language object
            name: Component name
        """
        self.name = name
        self.nlp = nlp

        # Initialize Matcher with greedy LONGEST
        self.matcher = Matcher(nlp.vocab, validate=True)

        # Add spatial relation patterns
        self._add_patterns()

    def _add_patterns(self) -> None:
        """Add token-based patterns for spatial relations."""

        # Pattern: [NUM] [UNIT] [DIRECTION] of [LOCATION]
        # Example: "10 km north of Paris"
        self.matcher.add(
            "DISTANCE_DIRECTION",
            [
                [
                    {"LIKE_NUM": True},  # Distance number
                    {"LOWER": {"IN": ["km", "kilometers", "kilometres", "m", "meters", "metres", "miles"]}},  # Unit
                    {"LOWER": {"IN": ["north", "south", "east", "west", "n", "s", "e", "w", "northeast", "northwest", "southeast", "southwest"]}},  # Direction
                    {"LOWER": {"IN": ["of", "from"]}},
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
                    {"LOWER": {"IN": ["near", "nearby", "close", "adjacent", "next", "beside"]}},
                    {"LOWER": "to", "OP": "?"},  # Optional "to"
                    {"POS": "DET", "OP": "?"},  # Optional determiner
                    {"ENT_TYPE": {"IN": ["LOC", "GPE", "FAC"]}, "OP": "+"},  # Location
                ],
                [
                    {"LOWER": {"IN": ["within", "inside", "outside", "around", "surrounding"]}},
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
                    {"LOWER": {"IN": ["north", "south", "east", "west", "northeast", "northwest", "southeast", "southwest", "upstream", "downstream", "offshore"]}},
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
                    {"LOWER": {"IN": ["located", "situated", "positioned", "found", "established"]}},
                    {"LOWER": {"IN": ["in", "at", "near", "on", "along"]}},
                    {"POS": "DET", "OP": "?"},  # Optional determiner
                    {"ENT_TYPE": {"IN": ["LOC", "GPE", "FAC"]}, "OP": "+"},
                ],
                [
                    {"LOWER": {"IN": ["located", "situated", "positioned", "found", "established"]}},
                    {"LOWER": {"IN": ["in", "at", "near", "on", "along"]}},
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
                    {"LOWER": {"IN": ["region", "area", "vicinity", "basin", "zone", "sector", "district"]}},
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

            # Create entity span
            ent_span = Span(doc, start, end, label="SPATIAL_RELATION")
            ent_span._.spatial_relation_type = self.nlp.vocab.strings[match_id].lower()
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
