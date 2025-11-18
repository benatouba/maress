"""spaCy component for study site detection using dependency patterns.

This component uses spaCy's DependencyMatcher to find linguistic patterns
that indicate study site mentions, following best practices for relation extraction.
"""

from typing import ClassVar

from spacy.language import Language
from spacy.matcher import DependencyMatcher
from spacy.tokens import Doc, Span


class StudySiteDependencyMatcher:
    """spaCy component for detecting study sites using dependency patterns.

    Detects linguistic patterns like:
    - "research conducted at [LOCATION]"
    - "sites established in [LOCATION]"
    - "samples collected from [LOCATION]"
    - "fieldwork performed near [LOCATION]"

    Uses dependency parsing to identify syntactic relationships that
    indicate study site mentions.
    """

    # Verbs that indicate study site activities
    STUDY_VERBS: ClassVar[set[str]] = {
        "conduct", "perform", "carry out", "undertake",
        "establish", "set up", "create", "install",
        "locate", "position", "situate", "place",
        "sample", "collect", "gather", "obtain",
        "measure", "monitor", "observe", "record",
        "study", "investigate", "examine", "analyze",
        "survey", "assess", "evaluate",
    }

    # Prepositions that link verbs to locations
    LOCATION_PREPS: ClassVar[set[str]] = {
        "at", "in", "near", "from", "within",
        "along", "around", "across", "throughout",
    }

    # Noun phrases that indicate study sites
    SITE_NOUNS: ClassVar[set[str]] = {
        "site", "sites", "location", "locations",
        "area", "areas", "region", "regions",
        "station", "stations", "plot", "plots",
        "transect", "transects", "quadrat", "quadrats",
        "point", "points", "spot", "spots",
    }

    def __init__(self, nlp: Language, name: str = "study_site_dependency_matcher") -> None:
        """Initialize the study site dependency matcher.

        Args:
            nlp: spaCy Language object
            name: Component name
        """
        self.name = name
        self.nlp = nlp

        # Initialize DependencyMatcher
        self.matcher = DependencyMatcher(nlp.vocab)

        # Add dependency patterns
        self._add_patterns()

    def _add_patterns(self) -> None:
        """Add dependency patterns for study site detection."""

        # Pattern 1: [VERB] at/in/near [LOCATION]
        # Example: "research conducted at San Francisco"
        # Tree: conducted -> prep (at) -> pobj (San Francisco)
        pattern1 = [
            {
                "RIGHT_ID": "verb",
                "RIGHT_ATTRS": {
                    # Match study verbs with POS constraint for precision
                    "POS": "VERB",
                    "LEMMA": {"IN": list(self.STUDY_VERBS)},
                }
            },
            {
                "LEFT_ID": "verb",
                "REL_OP": ">",
                "RIGHT_ID": "prep",
                "RIGHT_ATTRS": {
                    "DEP": "prep",
                    "LEMMA": {"IN": list(self.LOCATION_PREPS)},
                }
            },
            {
                "LEFT_ID": "prep",
                "REL_OP": ">",
                "RIGHT_ID": "location",
                "RIGHT_ATTRS": {
                    "DEP": "pobj",
                    "ENT_TYPE": {"IN": ["GPE", "LOC", "FAC"]},
                }
            }
        ]
        self.matcher.add("VERB_PREP_LOCATION", [pattern1])

        # Pattern 2: [SITE_NOUN] in/at/near [LOCATION]
        # Example: "study sites in California"
        # Tree: sites -> prep (in) -> pobj (California)
        pattern2 = [
            {
                "RIGHT_ID": "site_noun",
                "RIGHT_ATTRS": {
                    # Match site nouns with POS constraint for precision
                    "POS": "NOUN",
                    "LEMMA": {"IN": list(self.SITE_NOUNS)},
                }
            },
            {
                "LEFT_ID": "site_noun",
                "REL_OP": ">",
                "RIGHT_ID": "prep",
                "RIGHT_ATTRS": {
                    "DEP": "prep",
                    "LEMMA": {"IN": list(self.LOCATION_PREPS)},
                }
            },
            {
                "LEFT_ID": "prep",
                "REL_OP": ">",
                "RIGHT_ID": "location",
                "RIGHT_ATTRS": {
                    "DEP": "pobj",
                    "ENT_TYPE": {"IN": ["GPE", "LOC", "FAC"]},
                }
            }
        ]
        self.matcher.add("SITE_NOUN_PREP_LOCATION", [pattern2])

        # Pattern 3: [LOCATION] [SITE_NOUN]
        # Example: "California sites" or "Amazon region"
        # Tree: sites <- nmod (California)
        pattern3 = [
            {
                "RIGHT_ID": "site_noun",
                "RIGHT_ATTRS": {
                    # Match site nouns with POS constraint for precision
                    "POS": "NOUN",
                    "LEMMA": {"IN": list(self.SITE_NOUNS)},
                }
            },
            {
                "LEFT_ID": "site_noun",
                "REL_OP": ">",
                "RIGHT_ID": "location",
                "RIGHT_ATTRS": {
                    "DEP": {"IN": ["compound", "nmod", "amod"]},
                    "ENT_TYPE": {"IN": ["GPE", "LOC", "FAC"]},
                }
            }
        ]
        self.matcher.add("LOCATION_SITE_NOUN", [pattern3])

        # Pattern 4: located/situated/positioned [PREP] [LOCATION]
        # Example: "sites were located in Oregon"
        pattern4 = [
            {
                "RIGHT_ID": "participle",
                "RIGHT_ATTRS": {
                    # Match past participles (VBN) or past tense (VBD) verbs
                    "TAG": {"IN": ["VBN", "VBD"]},
                    "LEMMA": {"IN": ["locate", "situate", "position", "establish"]},
                }
            },
            {
                "LEFT_ID": "participle",
                "REL_OP": ">",
                "RIGHT_ID": "prep",
                "RIGHT_ATTRS": {
                    "DEP": "prep",
                    "LEMMA": {"IN": list(self.LOCATION_PREPS)},
                }
            },
            {
                "LEFT_ID": "prep",
                "REL_OP": ">",
                "RIGHT_ID": "location",
                "RIGHT_ATTRS": {
                    "DEP": "pobj",
                    "ENT_TYPE": {"IN": ["GPE", "LOC", "FAC"]},
                }
            }
        ]
        self.matcher.add("PARTICIPLE_PREP_LOCATION", [pattern4])

        # Pattern 5: [SITE_NOUN] [VERB_passive] in [LOCATION]
        # Example: "sites were established in California"
        pattern5 = [
            {
                "RIGHT_ID": "site_noun",
                "RIGHT_ATTRS": {
                    "POS": "NOUN",
                    "LEMMA": {"IN": list(self.SITE_NOUNS)},
                }
            },
            {
                "LEFT_ID": "site_noun",
                "REL_OP": ">",
                "RIGHT_ID": "verb",
                "RIGHT_ATTRS": {
                    "POS": "VERB",
                    "DEP": {"IN": ["relcl", "acl"]},
                    "LEMMA": {"IN": list(self.STUDY_VERBS)},
                }
            },
            {
                "LEFT_ID": "verb",
                "REL_OP": ">",
                "RIGHT_ID": "prep",
                "RIGHT_ATTRS": {
                    "DEP": "prep",
                    "LEMMA": {"IN": list(self.LOCATION_PREPS)},
                }
            },
            {
                "LEFT_ID": "prep",
                "REL_OP": ">",
                "RIGHT_ID": "location",
                "RIGHT_ATTRS": {
                    "DEP": "pobj",
                    "ENT_TYPE": {"IN": ["GPE", "LOC", "FAC"]},
                }
            }
        ]
        self.matcher.add("SITE_NOUN_PASSIVE_LOCATION", [pattern5])

    def __call__(self, doc: Doc) -> Doc:
        """Process a Doc object and add study site entities.

        Args:
            doc: spaCy Doc object

        Returns:
            Doc with study site entities added
        """
        matches = self.matcher(doc)

        new_ents = []
        seen_locations = set()

        for match_id, token_ids in matches:
            # Get the location token (always last in our patterns)
            location_token = doc[token_ids[-1]]

            # Skip if we've already processed this location
            if location_token.i in seen_locations:
                continue

            seen_locations.add(location_token.i)

            # Expand to full entity span if it's part of a named entity
            if location_token.ent_type_:
                span = location_token.ent_kb_id_
                start = location_token.ent_id
                # Find the full entity span
                for ent in doc.ents:
                    if location_token.i >= ent.start and location_token.i < ent.end:
                        span = ent
                        break
                else:
                    # Create a span from the token
                    span = doc[location_token.i:location_token.i + 1]
            else:
                # Create a span from the token
                span = doc[location_token.i:location_token.i + 1]

            # Create entity span with STUDY_SITE label
            try:
                ent_span = Span(doc, span.start, span.end, label="STUDY_SITE")
                ent_span._.dependency_pattern = self.nlp.vocab.strings[match_id]
                ent_span._.study_site_confidence = 0.90  # High confidence from dependency patterns
                new_ents.append(ent_span)
            except ValueError:
                # Skip if span creation fails
                continue

        # Merge with existing entities
        all_ents = list(doc.ents) + new_ents
        doc.ents = self._filter_overlapping_entities(all_ents)

        return doc

    def _filter_overlapping_entities(self, entities: list[Span]) -> tuple[Span, ...]:
        """Filter overlapping entities, keeping highest priority.

        Priority: STUDY_SITE > COORDINATE > SPATIAL_RELATION > others

        Args:
            entities: List of entity spans

        Returns:
            Tuple of non-overlapping entities
        """
        if not entities:
            return tuple()

        # Define priority order
        priority = {
            "STUDY_SITE": 4,
            "COORDINATE": 3,
            "SPATIAL_RELATION": 2,
        }

        # Sort by: priority (highest first), length (longest first), position
        sorted_ents = sorted(
            entities,
            key=lambda e: (
                -priority.get(e.label_, 1),
                -(e.end - e.start),
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


# Register custom extensions
if not Span.has_extension("dependency_pattern"):
    Span.set_extension("dependency_pattern", default=None)
if not Span.has_extension("study_site_confidence"):
    Span.set_extension("study_site_confidence", default=None)


@Language.factory("study_site_dependency_matcher")
def create_study_site_dependency_matcher(
    nlp: Language, name: str
) -> StudySiteDependencyMatcher:
    """Factory function for creating StudySiteDependencyMatcher component.

    Args:
        nlp: spaCy Language object
        name: Component name

    Returns:
        StudySiteDependencyMatcher instance
    """
    return StudySiteDependencyMatcher(nlp, name)
