"""spaCy component for multi-word location detection using PhraseMatcher.

This component uses spaCy's PhraseMatcher to detect complex geographic names
that are often missed by standard NER, improving study site detection accuracy.
"""

from typing import ClassVar

from spacy.language import Language
from spacy.matcher import PhraseMatcher
from spacy.tokens import Doc, Span


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

    # Common multi-word geographic locations (can be expanded)
    GEOGRAPHIC_LOCATIONS: ClassVar[list[str]] = [
        # National Parks & Forests (USA)
        "Yellowstone National Park",
        "Yosemite National Park",
        "Grand Canyon National Park",
        "Mount Hood National Forest",
        "Olympic National Forest",
        "Angeles National Forest",

        # Geographic Features (USA)
        "San Francisco Bay Area",
        "San Francisco Bay",
        "Columbia River Gorge",
        "Columbia River",
        "Mississippi River",
        "Rio Grande",
        "Great Salt Lake",
        "Chesapeake Bay",
        "Puget Sound",
        "Sierra Nevada",
        "Rocky Mountains",
        "Cascade Range",
        "Appalachian Mountains",
        "Great Plains",
        "Mojave Desert",
        "Sonoran Desert",
        "Death Valley",

        # Regions (USA)
        "Pacific Northwest",
        "Pacific Coast",
        "Atlantic Coast",
        "Gulf Coast",
        "New England",
        "Great Lakes Region",
        "Intermountain West",
        "Mountain West",

        # International Features
        "Amazon River Basin",
        "Amazon Rainforest",
        "Great Barrier Reef",
        "Sahara Desert",
        "Himalayan Mountains",
        "Mount Everest",
        "Lake Victoria",
        "Victoria Falls",
        "Nile River",
        "Congo River",
        "Danube River",
        "Rhine River",
        "Ganges River",
        "Yangtze River",
        "Mekong River",

        # Marine & Coastal
        "North Pacific Ocean",
        "South Pacific Ocean",
        "North Atlantic Ocean",
        "South Atlantic Ocean",
        "Indian Ocean",
        "Arctic Ocean",
        "Southern Ocean",
        "Mediterranean Sea",
        "Caribbean Sea",
        "Red Sea",
        "Baltic Sea",
        "Black Sea",
        "Coral Sea",
        "Bering Sea",

        # Islands & Archipelagos
        "Hawaiian Islands",
        "Florida Keys",
        "Channel Islands",
        "Galapagos Islands",
        "British Isles",
        "Canary Islands",

        # Bays & Gulfs
        "San Francisco Bay",
        "Monterey Bay",
        "Tampa Bay",
        "Galveston Bay",
        "Hudson Bay",
        "Gulf of Mexico",
        "Gulf of California",
        "Persian Gulf",
        "Bay of Bengal",

        # Research Station Names (common patterns)
        "Hubbard Brook Experimental Forest",
        "Coweeta Hydrologic Laboratory",
        "H.J. Andrews Experimental Forest",

        # Universities & Research Areas (often study sites)
        "Stanford University",
        "University of California",
        "Woods Hole",
        "Friday Harbor",
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

            # Create entity span
            try:
                ent_span = Span(doc, start, end, label="MULTIWORD_LOCATION")
                ent_span._.is_multiword_location = True
                ent_span._.location_type = self.nlp.vocab.strings[match_id].lower()
                new_ents.append(ent_span)
            except ValueError:
                continue

        # Merge with existing entities
        all_ents = list(doc.ents) + new_ents
        doc.ents = self._filter_overlapping_entities(all_ents)

        return doc

    def _filter_overlapping_entities(self, entities: list[Span]) -> tuple[Span, ...]:
        """Filter overlapping entities, preferring longer spans.

        Args:
            entities: List of entity spans

        Returns:
            Tuple of non-overlapping entities
        """
        if not entities:
            return tuple()

        # Priority: longer spans preferred, then by entity type
        priority = {
            "STUDY_SITE": 5,
            "COORDINATE": 4,
            "MULTIWORD_LOCATION": 3,
            "SPATIAL_RELATION": 2,
        }

        # Sort by: length (longest first), priority, position
        sorted_ents = sorted(
            entities,
            key=lambda e: (
                -(e.end - e.start),
                -priority.get(e.label_, 1),
                e.start
            )
        )

        filtered = []
        occupied_positions = set()

        for ent in sorted_ents:
            positions = set(range(ent.start, ent.end))
            if not positions.intersection(occupied_positions):
                filtered.append(ent)
                occupied_positions.update(positions)

        return tuple(sorted(filtered, key=lambda e: e.start))

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
