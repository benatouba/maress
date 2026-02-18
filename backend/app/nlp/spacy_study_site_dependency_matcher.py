"""spaCy component for study site detection using dependency patterns.

This component uses spaCy's DependencyMatcher to find linguistic patterns
that indicate study site mentions, following best practices for relation extraction.
"""

import json
from pathlib import Path
from typing import ClassVar

from spacy.language import Language
from spacy.matcher import DependencyMatcher
from spacy.tokens import Doc, Span
from spacy.util import filter_spans  # Phase 1: Use spaCy's optimized overlap filtering


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

    # Phase 1: Vocabularies externalized to JSON files for easy updates
    # These are loaded from backend/app/nlp/data/ directory
    STUDY_VERBS: ClassVar[set[str]] = set()
    LOCATION_PREPS: ClassVar[set[str]] = set()
    SITE_NOUNS: ClassVar[set[str]] = set()
    DATA_DIR: ClassVar[Path] = Path(__file__).parent / "data"

    @classmethod
    def _load_vocabularies(cls) -> None:
        """Load vocabularies from JSON files.

        Phase 1 Best Practice: Externalize vocabularies to JSON for:
        - Easy updates without code changes
        - Version control
        - Domain-specific customization
        - User contributions
        """
        if cls.STUDY_VERBS:  # Already loaded
            return

        # Load study verbs
        verbs_file = cls.DATA_DIR / "study_verbs.json"
        if verbs_file.exists():
            with open(verbs_file) as f:
                data = json.load(f)
                for category in data["categories"].values():
                    cls.STUDY_VERBS.update(category["verbs"])
        else:
            # Fallback to minimal set if file not found
            cls.STUDY_VERBS = {"conduct", "perform", "collect", "study", "locate"}

        # Load site nouns
        nouns_file = cls.DATA_DIR / "site_nouns.json"
        if nouns_file.exists():
            with open(nouns_file) as f:
                data = json.load(f)
                for category in data["categories"].values():
                    cls.SITE_NOUNS.update(category["nouns"])
        else:
            # Fallback to minimal set if file not found
            cls.SITE_NOUNS = {"site", "sites", "area", "areas", "location", "locations"}

        # Load location prepositions
        preps_file = cls.DATA_DIR / "location_prepositions.json"
        if preps_file.exists():
            with open(preps_file) as f:
                data = json.load(f)
                cls.LOCATION_PREPS.update(data["prepositions"])
        else:
            # Fallback to minimal set if file not found
            cls.LOCATION_PREPS = {"at", "in", "near", "from", "within"}

    def __init__(self, nlp: Language, name: str = "study_site_dependency_matcher") -> None:
        """Initialize the study site dependency matcher.

        Args:
            nlp: spaCy Language object
            name: Component name
        """
        self.name = name
        self.nlp = nlp

        # Phase 1: Load vocabularies from JSON files
        self._load_vocabularies()

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

        # Pattern 6: "We/This study focus(es) on [LOCATION]"
        # Example: "We focus on the Amazon basin"
        # Common in earth system papers for describing study scope
        pattern6 = [
            {
                "RIGHT_ID": "verb",
                "RIGHT_ATTRS": {
                    "POS": "VERB",
                    "LEMMA": {"IN": ["focus", "concentrate", "center", "centre"]},
                }
            },
            {
                "LEFT_ID": "verb",
                "REL_OP": ">",
                "RIGHT_ID": "prep",
                "RIGHT_ATTRS": {
                    "DEP": "prep",
                    "LEMMA": "on",
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
        self.matcher.add("FOCUS_ON_LOCATION", [pattern6])

        # Pattern 7: "Data/Measurements were collected from/in [LOCATION]"
        # Example: "Data were collected from sites in California"
        # Captures passive data collection constructions
        pattern7 = [
            {
                "RIGHT_ID": "data_noun",
                "RIGHT_ATTRS": {
                    "POS": "NOUN",
                    "LEMMA": {"IN": ["data", "datum", "measurement", "observation", "sample"]},
                }
            },
            {
                "LEFT_ID": "data_noun",
                "REL_OP": ">",
                "RIGHT_ID": "verb",
                "RIGHT_ATTRS": {
                    "POS": "VERB",
                    "DEP": {"IN": ["relcl", "acl", "ROOT"]},
                    "LEMMA": {"IN": ["collect", "gather", "obtain", "take", "record"]},
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
        self.matcher.add("DATA_COLLECTED_LOCATION", [pattern7])

        # Pattern 8: Domain/Region coverage patterns
        # Example: "The domain covers California" or "The region extends from..."
        # Common in climate modeling and regional studies
        pattern8 = [
            {
                "RIGHT_ID": "domain_noun",
                "RIGHT_ATTRS": {
                    "POS": "NOUN",
                    "LEMMA": {"IN": ["domain", "region", "area", "model"]},
                }
            },
            {
                "LEFT_ID": "domain_noun",
                "REL_OP": ">",
                "RIGHT_ID": "verb",
                "RIGHT_ATTRS": {
                    "POS": "VERB",
                    "LEMMA": {"IN": ["cover", "span", "extend", "encompass", "include"]},
                }
            },
            {
                "LEFT_ID": "verb",
                "REL_OP": ">",
                "RIGHT_ID": "location",
                "RIGHT_ATTRS": {
                    "DEP": {"IN": ["dobj", "pobj"]},
                    "ENT_TYPE": {"IN": ["GPE", "LOC", "FAC"]},
                }
            }
        ]
        self.matcher.add("DOMAIN_COVERAGE_LOCATION", [pattern8])

        # === NEW PATTERNS (Priority 2 Improvements) ===

        # Pattern 9: "field work was carried out at [LOCATION]"
        # Example: "Fieldwork was carried out at three sites in the Alps"
        # Captures passive fieldwork constructions
        pattern9 = [
            {
                "RIGHT_ID": "fieldwork",
                "RIGHT_ATTRS": {
                    "POS": "NOUN",
                    "LEMMA": {"IN": ["fieldwork", "field", "work", "campaign", "expedition"]},
                }
            },
            {
                "LEFT_ID": "fieldwork",
                "REL_OP": ">",
                "RIGHT_ID": "verb",
                "RIGHT_ATTRS": {
                    "POS": "VERB",
                    "LEMMA": {"IN": ["carry", "conduct", "perform", "undertake", "complete"]},
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
        self.matcher.add("FIELDWORK_AT_LOCATION", [pattern9])

        # Pattern 10: "[LOCATION] was selected as the study site"
        # Example: "The Amazon basin was selected as our primary study area"
        # Captures selection/choice patterns
        pattern10 = [
            {
                "RIGHT_ID": "location",
                "RIGHT_ATTRS": {
                    "ENT_TYPE": {"IN": ["GPE", "LOC", "FAC"]},
                }
            },
            {
                "LEFT_ID": "location",
                "REL_OP": "<",
                "RIGHT_ID": "verb",
                "RIGHT_ATTRS": {
                    "POS": "VERB",
                    "LEMMA": {"IN": ["select", "choose", "designate", "identify", "define"]},
                }
            },
            {
                "LEFT_ID": "verb",
                "REL_OP": ">",
                "RIGHT_ID": "prep_as",
                "RIGHT_ATTRS": {
                    "DEP": "prep",
                    "LEMMA": "as",
                }
            },
            {
                "LEFT_ID": "prep_as",
                "REL_OP": ">",
                "RIGHT_ID": "site_noun",
                "RIGHT_ATTRS": {
                    "DEP": "pobj",
                    "LEMMA": {"IN": list(self.SITE_NOUNS)},
                }
            }
        ]
        self.matcher.add("LOCATION_SELECTED_AS_SITE", [pattern10])

        # Pattern 11: "cores/samples were extracted from [LOCATION]"
        # Example: "Sediment cores were extracted from Lake Victoria"
        # Common in paleoclimate and geological studies
        pattern11 = [
            {
                "RIGHT_ID": "sample_noun",
                "RIGHT_ATTRS": {
                    "POS": "NOUN",
                    "LEMMA": {"IN": ["core", "sample", "specimen", "sediment", "ice", "peat"]},
                }
            },
            {
                "LEFT_ID": "sample_noun",
                "REL_OP": ">",
                "RIGHT_ID": "verb",
                "RIGHT_ATTRS": {
                    "POS": "VERB",
                    "LEMMA": {"IN": ["extract", "retrieve", "obtain", "collect", "drill", "take"]},
                }
            },
            {
                "LEFT_ID": "verb",
                "REL_OP": ">",
                "RIGHT_ID": "prep",
                "RIGHT_ATTRS": {
                    "DEP": "prep",
                    "LEMMA": {"IN": ["from", "in", "at"]},
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
        self.matcher.add("SAMPLES_FROM_LOCATION", [pattern11])

        # Pattern 12: "sensors/instruments deployed at [LOCATION]"
        # Example: "Flux towers were deployed across the boreal forest"
        # Common in monitoring and remote sensing studies
        pattern12 = [
            {
                "RIGHT_ID": "instrument",
                "RIGHT_ATTRS": {
                    "POS": "NOUN",
                    "LEMMA": {"IN": ["sensor", "instrument", "tower", "station", "buoy", "logger", "probe", "gauge"]},
                }
            },
            {
                "LEFT_ID": "instrument",
                "REL_OP": ">",
                "RIGHT_ID": "verb",
                "RIGHT_ATTRS": {
                    "POS": "VERB",
                    "LEMMA": {"IN": ["deploy", "install", "place", "position", "set", "mount"]},
                }
            },
            {
                "LEFT_ID": "verb",
                "REL_OP": ">",
                "RIGHT_ID": "prep",
                "RIGHT_ATTRS": {
                    "DEP": "prep",
                    "LEMMA": {"IN": list(set(self.LOCATION_PREPS) | {"across", "throughout"})},
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
        self.matcher.add("INSTRUMENTS_AT_LOCATION", [pattern12])

        # Pattern 13: "transects/plots established across [LOCATION]"
        # Example: "Vegetation transects were established across the savanna"
        # Common in ecological surveys
        pattern13 = [
            {
                "RIGHT_ID": "survey_noun",
                "RIGHT_ATTRS": {
                    "POS": "NOUN",
                    "LEMMA": {"IN": ["transect", "plot", "quadrat", "grid", "profile", "survey"]},
                }
            },
            {
                "LEFT_ID": "survey_noun",
                "REL_OP": ">",
                "RIGHT_ID": "verb",
                "RIGHT_ATTRS": {
                    "POS": "VERB",
                    "LEMMA": {"IN": ["establish", "set", "lay", "run", "conduct", "perform"]},
                }
            },
            {
                "LEFT_ID": "verb",
                "REL_OP": ">",
                "RIGHT_ID": "prep",
                "RIGHT_ATTRS": {
                    "DEP": "prep",
                    "LEMMA": {"IN": ["across", "along", "through", "in", "within", "throughout"]},
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
        self.matcher.add("TRANSECTS_ACROSS_LOCATION", [pattern13])

        # Pattern 14: "monitoring network in [LOCATION]"
        # Example: "A monitoring network was established in the watershed"
        # Common in long-term ecological research
        pattern14 = [
            {
                "RIGHT_ID": "network_noun",
                "RIGHT_ATTRS": {
                    "POS": "NOUN",
                    "LEMMA": {"IN": ["network", "array", "system", "infrastructure", "observatory"]},
                }
            },
            {
                "LEFT_ID": "network_noun",
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
        self.matcher.add("NETWORK_IN_LOCATION", [pattern14])

        # Pattern 15: "derived from [LOCATION]" (remote sensing)
        # Example: "Data were derived from imagery covering the Sahel"
        # Common in remote sensing studies
        pattern15 = [
            {
                "RIGHT_ID": "verb",
                "RIGHT_ATTRS": {
                    "POS": "VERB",
                    "LEMMA": {"IN": ["derive", "obtain", "acquire", "source", "extract"]},
                }
            },
            {
                "LEFT_ID": "verb",
                "REL_OP": ">",
                "RIGHT_ID": "prep_from",
                "RIGHT_ATTRS": {
                    "DEP": "prep",
                    "LEMMA": "from",
                }
            },
            {
                "LEFT_ID": "prep_from",
                "REL_OP": ">",
                "RIGHT_ID": "imagery",
                "RIGHT_ATTRS": {
                    "DEP": "pobj",
                    "LEMMA": {"IN": ["imagery", "image", "satellite", "scene", "data", "product"]},
                }
            },
            {
                "LEFT_ID": "imagery",
                "REL_OP": ">",
                "RIGHT_ID": "prep_cover",
                "RIGHT_ATTRS": {
                    "DEP": "acl",
                }
            },
            {
                "LEFT_ID": "prep_cover",
                "REL_OP": ">",
                "RIGHT_ID": "location",
                "RIGHT_ATTRS": {
                    "DEP": {"IN": ["dobj", "pobj"]},
                    "ENT_TYPE": {"IN": ["GPE", "LOC", "FAC"]},
                }
            }
        ]
        self.matcher.add("DERIVED_FROM_LOCATION", [pattern15])

        # Pattern 16: "experiments performed/conducted at [LOCATION]"
        # Example: "Experiments were conducted at the field station"
        pattern16 = [
            {
                "RIGHT_ID": "experiment",
                "RIGHT_ATTRS": {
                    "POS": "NOUN",
                    "LEMMA": {"IN": ["experiment", "trial", "test", "manipulation", "treatment"]},
                }
            },
            {
                "LEFT_ID": "experiment",
                "REL_OP": ">",
                "RIGHT_ID": "verb",
                "RIGHT_ATTRS": {
                    "POS": "VERB",
                    "LEMMA": {"IN": ["perform", "conduct", "carry", "run", "execute"]},
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
        self.matcher.add("EXPERIMENTS_AT_LOCATION", [pattern16])

        # Pattern 17: "based in/at [LOCATION]" (research base)
        # Example: "The research was based at McMurdo Station"
        pattern17 = [
            {
                "RIGHT_ID": "based",
                "RIGHT_ATTRS": {
                    "LEMMA": "base",
                    "TAG": {"IN": ["VBN", "VBD"]},
                }
            },
            {
                "LEFT_ID": "based",
                "REL_OP": ">",
                "RIGHT_ID": "prep",
                "RIGHT_ATTRS": {
                    "DEP": "prep",
                    "LEMMA": {"IN": ["in", "at", "on"]},
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
        self.matcher.add("BASED_AT_LOCATION", [pattern17])

        # Pattern 18: "along the [LOCATION] coast/river/border"
        # Example: "Sampling was conducted along the California coast"
        # Captures linear feature sampling
        pattern18 = [
            {
                "RIGHT_ID": "prep_along",
                "RIGHT_ATTRS": {
                    "LEMMA": {"IN": ["along", "across", "through"]},
                }
            },
            {
                "LEFT_ID": "prep_along",
                "REL_OP": ">",
                "RIGHT_ID": "feature",
                "RIGHT_ATTRS": {
                    "DEP": "pobj",
                    "LEMMA": {"IN": ["coast", "coastline", "river", "border", "margin", "shore", "gradient", "transect"]},
                }
            },
            {
                "LEFT_ID": "feature",
                "REL_OP": ">",
                "RIGHT_ID": "location",
                "RIGHT_ATTRS": {
                    "DEP": {"IN": ["compound", "nmod", "poss"]},
                    "ENT_TYPE": {"IN": ["GPE", "LOC", "FAC"]},
                }
            }
        ]
        self.matcher.add("ALONG_LOCATION_FEATURE", [pattern18])

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
            span = None
            if location_token.ent_type_:
                # Find the full entity span
                for ent in doc.ents:
                    if location_token.i >= ent.start and location_token.i < ent.end:
                        span = ent
                        break

            # Fallback: Create a span from just the token
            if span is None:
                span = doc[location_token.i:location_token.i + 1]

            # Phase 1.4: Use MARESS_STUDY_SITE label to avoid namespace collisions
            # Create entity span with MARESS_STUDY_SITE label
            try:
                ent_span = Span(doc, span.start, span.end, label="MARESS_STUDY_SITE")
                ent_span._.dependency_pattern = self.nlp.vocab.strings[match_id]
                ent_span._.study_site_confidence = 0.90  # High confidence from dependency patterns
                new_ents.append(ent_span)
            except ValueError:
                # Skip if span creation fails
                continue

        # Phase 1: Use spaCy's filter_spans() instead of manual overlap filtering
        # filter_spans automatically handles priority and removes overlaps
        all_ents = list(doc.ents) + new_ents
        doc.ents = filter_spans(all_ents)

        return doc


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
