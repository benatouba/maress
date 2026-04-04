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

from app.nlp.pattern_registry import PatternRegistry


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

        base_patterns = PatternRegistry.get_study_site_dependency_patterns(
            study_verbs=list(self.STUDY_VERBS),
            location_preps=list(self.LOCATION_PREPS),
            site_nouns=list(self.SITE_NOUNS),
        )
        for pattern_name, pattern_list in base_patterns.items():
            self.matcher.add(pattern_name, pattern_list)

        extended_patterns = PatternRegistry.get_extended_study_site_dependency_patterns(
            location_preps=list(self.LOCATION_PREPS),
            site_nouns=list(self.SITE_NOUNS),
        )
        for pattern_name, pattern_list in extended_patterns.items():
            self.matcher.add(pattern_name, pattern_list)

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
