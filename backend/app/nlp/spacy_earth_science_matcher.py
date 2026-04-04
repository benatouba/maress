"""spaCy component for earth science domain-specific entity detection.

This component detects domain-specific geographic entities that are often
missed by general-purpose NER models, including:
- Water bodies (rivers, lakes, oceans, wetlands)
- Geological features (mountains, valleys, glaciers)
- Ecosystems (forests, savannas, reefs)
- Research infrastructure (stations, transects, plots)

These entities are crucial for identifying study site locations in
earth system science publications.
"""

import json
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from spacy.language import Language
from spacy.matcher import Matcher, PhraseMatcher
from spacy.tokens import Doc, Span
from spacy.util import filter_spans

if TYPE_CHECKING:
    pass


class EarthScienceEntityMatcher:
    """spaCy component for detecting earth science domain-specific entities.

    Detects entities like:
    - WATER_BODY: rivers, lakes, wetlands, aquifers
    - GEO_FEATURE: mountains, glaciers, faults, basins
    - ECOSYSTEM: forests, savannas, reefs, tundra
    - COASTAL: beaches, estuaries, barrier islands
    - RESEARCH_SITE: stations, transects, monitoring plots

    Uses both token patterns (for single words) and phrase patterns
    (for compound terms like "river basin" or "flux tower").
    """

    DATA_DIR: ClassVar[Path] = Path(__file__).parent / "data"

    # Entity type mapping for MARESS namespace
    ENTITY_TYPES: ClassVar[dict[str, str]] = {
        "water_bodies": "MARESS_WATER_BODY",
        "geological_features": "MARESS_GEO_FEATURE",
        "ecosystems": "MARESS_ECOSYSTEM",
        "coastal_features": "MARESS_COASTAL",
        "research_infrastructure": "MARESS_RESEARCH_SITE",
        "climate_zones": "MARESS_CLIMATE_ZONE",
    }

    # Confidence scores by entity type
    CONFIDENCE_SCORES: ClassVar[dict[str, float]] = {
        "MARESS_WATER_BODY": 0.85,
        "MARESS_GEO_FEATURE": 0.85,
        "MARESS_ECOSYSTEM": 0.80,
        "MARESS_COASTAL": 0.85,
        "MARESS_RESEARCH_SITE": 0.90,
        "MARESS_CLIMATE_ZONE": 0.75,
    }

    def __init__(self, nlp: Language, name: str = "earth_science_matcher") -> None:
        """Initialize the earth science entity matcher.

        Args:
            nlp: spaCy Language object
            name: Component name
        """
        self.name = name
        self.nlp = nlp

        # Initialize matchers
        self.token_matcher = Matcher(nlp.vocab)
        self.phrase_matcher = PhraseMatcher(nlp.vocab, attr="LOWER")

        # Load vocabularies and add patterns
        self._load_and_add_patterns()

    def _load_and_add_patterns(self) -> None:
        """Load vocabularies from JSON and add matcher patterns."""
        vocab_file = self.DATA_DIR / "earth_science_entities.json"

        if not vocab_file.exists():
            # Use minimal fallback patterns
            self._add_fallback_patterns()
            return

        with open(vocab_file) as f:
            data = json.load(f)

        categories = data.get("categories", {})

        for category_name, category_data in categories.items():
            entity_label = self.ENTITY_TYPES.get(category_name)
            if not entity_label:
                continue

            # Add single-word token patterns
            terms = category_data.get("terms", [])
            if terms:
                self._add_token_patterns(entity_label, terms)

            # Add compound phrase patterns
            compounds = category_data.get("compound_patterns", [])
            if compounds:
                self._add_phrase_patterns(entity_label, compounds)

    def _add_token_patterns(self, label: str, terms: list[str]) -> None:
        """Add token-based patterns for single-word entities.

        Args:
            label: Entity label (e.g., MARESS_WATER_BODY)
            terms: List of terms to match
        """
        # Pattern: [PROPN] + term (e.g., "Amazon River", "Mount Everest")
        # This catches "X River", "Mount X", etc.
        patterns = []

        for term in terms:
            # Pattern 1: Term followed by proper noun (e.g., "River Amazon")
            patterns.append([
                {"LOWER": term.lower()},
                {"POS": "PROPN", "OP": "+"},
            ])

            # Pattern 2: Proper noun followed by term (e.g., "Amazon River")
            patterns.append([
                {"POS": "PROPN", "OP": "+"},
                {"LOWER": term.lower()},
            ])

            # Pattern 3: "The" + term + proper noun (e.g., "the Nile River")
            patterns.append([
                {"LOWER": "the"},
                {"POS": "PROPN", "OP": "+"},
                {"LOWER": term.lower()},
            ])

        if patterns:
            self.token_matcher.add(label, patterns, greedy="LONGEST")

    def _add_phrase_patterns(self, label: str, compounds: list[str]) -> None:
        """Add phrase-based patterns for compound terms.

        Args:
            label: Entity label
            compounds: List of compound phrases to match
        """
        patterns = [self.nlp.make_doc(phrase.lower()) for phrase in compounds]
        if patterns:
            self.phrase_matcher.add(label, patterns)

    def _add_fallback_patterns(self) -> None:
        """Add minimal fallback patterns if vocabulary file not found."""
        # Minimal water body patterns
        water_terms = ["river", "lake", "ocean", "sea", "wetland"]
        self._add_token_patterns("MARESS_WATER_BODY", water_terms)

        # Minimal geological patterns
        geo_terms = ["mountain", "volcano", "glacier", "valley"]
        self._add_token_patterns("MARESS_GEO_FEATURE", geo_terms)

        # Minimal ecosystem patterns
        eco_terms = ["forest", "rainforest", "savanna", "reef"]
        self._add_token_patterns("MARESS_ECOSYSTEM", eco_terms)

    def __call__(self, doc: Doc) -> Doc:
        """Process a Doc and add earth science entities.

        Args:
            doc: spaCy Doc object

        Returns:
            Doc with earth science entities added
        """
        new_ents = []
        seen_spans: set[tuple[int, int]] = set()

        # Process token matches
        token_matches = self.token_matcher(doc)
        for match_id, start, end in token_matches:
            span_key = (start, end)
            if span_key in seen_spans:
                continue

            seen_spans.add(span_key)
            label = self.nlp.vocab.strings[match_id]

            try:
                ent_span = Span(doc, start, end, label=label)
                ent_span._.earth_science_type = label.replace("MARESS_", "")
                ent_span._.earth_science_confidence = self.CONFIDENCE_SCORES.get(
                    label, 0.80
                )
                new_ents.append(ent_span)
            except ValueError:
                continue

        # Process phrase matches
        phrase_matches = self.phrase_matcher(doc)
        for match_id, start, end in phrase_matches:
            span_key = (start, end)
            if span_key in seen_spans:
                continue

            seen_spans.add(span_key)
            label = self.nlp.vocab.strings[match_id]

            try:
                ent_span = Span(doc, start, end, label=label)
                ent_span._.earth_science_type = label.replace("MARESS_", "")
                ent_span._.earth_science_confidence = self.CONFIDENCE_SCORES.get(
                    label, 0.80
                )
                new_ents.append(ent_span)
            except ValueError:
                continue

        # Merge with existing entities, preferring longer spans
        all_ents = list(doc.ents) + new_ents
        doc.ents = filter_spans(all_ents)

        return doc


# Register custom extensions
if not Span.has_extension("earth_science_type"):
    Span.set_extension("earth_science_type", default=None)
if not Span.has_extension("earth_science_confidence"):
    Span.set_extension("earth_science_confidence", default=None)


@Language.factory("earth_science_matcher")
def create_earth_science_matcher(nlp: Language, name: str) -> EarthScienceEntityMatcher:
    """Factory function for creating EarthScienceEntityMatcher component.

    Args:
        nlp: spaCy Language object
        name: Component name

    Returns:
        EarthScienceEntityMatcher instance
    """
    return EarthScienceEntityMatcher(nlp, name)
