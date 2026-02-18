"""Coreference resolution for location mentions.

Resolves references like "the site", "this location", "these areas" back to
the actual location entities they refer to. This is critical for earth science
papers where pronouns and definite descriptions are common.

Example:
    "The study was conducted in Paradise, Alaska. The site is characterized by..."
    -> Resolves "The site" back to "Paradise, Alaska"

This is a Priority 4 improvement that enhances entity linking and reduces
false negatives from anaphoric references.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from app.nlp.nlp_logger import logger

if TYPE_CHECKING:
    from spacy.tokens import Doc, Span, Token
    from app.nlp.domain_models import GeoEntity


@dataclass
class CoreferenceLink:
    """A coreference link between a mention and its antecedent."""

    mention_text: str  # "the site"
    mention_start: int
    mention_end: int
    antecedent_text: str  # "Paradise, Alaska"
    antecedent_start: int
    antecedent_end: int
    confidence: float


class LocationCoreferenceResolver:
    """Resolve location coreferences in scientific text.

    Handles common patterns in earth science papers:
    - "the site", "the study site", "the study area"
    - "this location", "these locations"
    - "the region", "the area"
    - "here", "there"
    """

    # Anaphoric expressions that refer to locations
    LOCATION_ANAPHORS: ClassVar[list[re.Pattern[str]]] = [
        # Definite descriptions
        re.compile(r"\bthe\s+(study\s+)?(site|area|region|location|zone|domain|field)\b", re.I),
        re.compile(r"\bthe\s+(sampling|research|experimental|observation)\s+(site|area|location)\b", re.I),
        re.compile(r"\bthis\s+(site|area|region|location|zone)\b", re.I),
        re.compile(r"\bthese\s+(sites|areas|regions|locations|zones)\b", re.I),
        re.compile(r"\bour\s+(site|area|region|study\s+area)\b", re.I),

        # Demonstratives
        re.compile(r"\b(here|there)\b", re.I),

        # Pronouns in specific contexts
        re.compile(r"\bit\b(?=\s+(?:is|was|has|features|contains))", re.I),

        # Elliptical references
        re.compile(r"\bat\s+the\s+(?:same\s+)?(?:site|location|area)\b", re.I),
    ]

    # Indicators that help identify the antecedent
    LOCATION_INTRODUCTION_PATTERNS: ClassVar[list[re.Pattern[str]]] = [
        re.compile(r"\b(?:in|at|near|from)\s+([A-Z][^,.;]+)\b"),
        re.compile(r"\blocated\s+(?:in|at|near)\s+([A-Z][^,.;]+)\b", re.I),
        re.compile(r"\bconducted\s+(?:in|at)\s+([A-Z][^,.;]+)\b", re.I),
    ]

    # Maximum distance (in sentences) to search for antecedent
    MAX_SENTENCE_DISTANCE = 3

    def __init__(self) -> None:
        """Initialize the coreference resolver."""
        pass

    def resolve_coreferences(
        self,
        doc: Doc,
        entities: list[GeoEntity],
    ) -> list[CoreferenceLink]:
        """Find coreference links in document.

        Args:
            doc: spaCy Doc object
            entities: Extracted location entities

        Returns:
            List of coreference links
        """
        links: list[CoreferenceLink] = []

        # Find all location anaphors in text
        text = doc.text
        anaphors = self._find_anaphors(text)

        if not anaphors:
            return links

        # For each anaphor, find the most likely antecedent
        for anaphor_start, anaphor_end, anaphor_text in anaphors:
            antecedent = self._find_antecedent(
                doc,
                entities,
                anaphor_start,
                anaphor_end,
            )

            if antecedent:
                link = CoreferenceLink(
                    mention_text=anaphor_text,
                    mention_start=anaphor_start,
                    mention_end=anaphor_end,
                    antecedent_text=antecedent.text,
                    antecedent_start=antecedent.start_char,
                    antecedent_end=antecedent.end_char,
                    confidence=0.8,  # Could be refined with ML model
                )
                links.append(link)
                logger.debug(
                    f"Resolved coreference: '{anaphor_text}' -> '{antecedent.text}'"
                )

        return links

    def _find_anaphors(self, text: str) -> list[tuple[int, int, str]]:
        """Find all location anaphors in text.

        Returns:
            List of (start, end, text) tuples
        """
        anaphors = []

        for pattern in self.LOCATION_ANAPHORS:
            for match in pattern.finditer(text):
                anaphors.append((match.start(), match.end(), match.group()))

        return anaphors

    def _find_antecedent(
        self,
        doc: Doc,
        entities: list[GeoEntity],
        anaphor_start: int,
        anaphor_end: int,
    ) -> GeoEntity | None:
        """Find the antecedent for an anaphor.

        Uses recency heuristic: nearest preceding location entity.

        Args:
            doc: spaCy Doc
            entities: Location entities
            anaphor_start: Start position of anaphor
            anaphor_end: End position of anaphor

        Returns:
            Most likely antecedent entity or None
        """
        # Filter to entities that appear before the anaphor
        preceding_entities = [
            e for e in entities
            if e.end_char < anaphor_start
            and e.entity_type in {"LOC", "GPE", "FAC", "STUDY_SITE", "WATER_BODY", "GEO_FEATURE"}
        ]

        if not preceding_entities:
            return None

        # Find the sentence containing the anaphor
        anaphor_sent_idx = self._get_sentence_index(doc, anaphor_start)

        # Score candidates by recency and salience
        candidates = []
        for entity in preceding_entities:
            entity_sent_idx = self._get_sentence_index(doc, entity.start_char)

            # Distance in sentences
            sent_distance = anaphor_sent_idx - entity_sent_idx

            if sent_distance > self.MAX_SENTENCE_DISTANCE:
                continue

            # Score: prefer closer entities, prefer study sites
            recency_score = 1.0 / (sent_distance + 1)
            salience_score = 1.5 if entity.entity_type == "STUDY_SITE" else 1.0

            score = recency_score * salience_score * entity.confidence
            candidates.append((entity, score))

        if not candidates:
            return None

        # Return highest-scoring candidate
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    def _get_sentence_index(self, doc: Doc, char_pos: int) -> int:
        """Get the sentence index for a character position."""
        for i, sent in enumerate(doc.sents):
            if sent.start_char <= char_pos < sent.end_char:
                return i
        return len(list(doc.sents)) - 1

    def expand_entities_with_coreferences(
        self,
        doc: Doc,
        entities: list[GeoEntity],
    ) -> list[GeoEntity]:
        """Create additional entities from resolved coreferences.

        Args:
            doc: spaCy Doc
            entities: Original entities

        Returns:
            Expanded list including coreference-derived entities
        """
        links = self.resolve_coreferences(doc, entities)

        if not links:
            return entities

        # Create new entities for resolved coreferences
        expanded = list(entities)

        for link in links:
            # Find the antecedent entity to copy metadata from
            antecedent = next(
                (e for e in entities if e.start_char == link.antecedent_start),
                None,
            )

            if not antecedent:
                continue

            # Create new entity at the anaphor position
            # Use antecedent's metadata but anaphor's position
            coref_entity = GeoEntity(
                text=link.mention_text,
                entity_type=antecedent.entity_type,
                context=self._get_context_around(doc.text, link.mention_start, link.mention_end),
                section=antecedent.section,
                confidence=antecedent.confidence * link.confidence,
                start_char=link.mention_start,
                end_char=link.mention_end,
                coordinates=antecedent.coordinates,
            )
            expanded.append(coref_entity)

        logger.info(f"Coreference resolution: added {len(links)} entities from anaphoric references")

        return expanded

    def _get_context_around(self, text: str, start: int, end: int, window: int = 100) -> str:
        """Get context around a span."""
        context_start = max(0, start - window)
        context_end = min(len(text), end + window)
        return text[context_start:context_end]


class AbbreviationExpander:
    """Expand common abbreviations and acronyms in location names.

    Handles:
    - Directional abbreviations: N, S, E, W, NE, SW, etc.
    - Country codes: USA, UK, UAE, etc.
    - State codes: CA, NY, TX, etc.
    - Geographic terms: Mt., St., Is., etc.
    """

    ABBREVIATIONS: ClassVar[dict[str, str]] = {
        # Directions
        "N": "North",
        "S": "South",
        "E": "East",
        "W": "West",
        "NE": "Northeast",
        "NW": "Northwest",
        "SE": "Southeast",
        "SW": "Southwest",
        "N.": "North",
        "S.": "South",
        "E.": "East",
        "W.": "West",

        # Geographic terms
        "Mt.": "Mount",
        "Mt": "Mount",
        "Mts.": "Mountains",
        "Mts": "Mountains",
        "St.": "Saint",
        "Is.": "Island",
        "Is": "Island",
        "Pen.": "Peninsula",
        "Pk.": "Peak",
        "R.": "River",
        "L.": "Lake",

        # Common countries (ISO codes)
        "USA": "United States",
        "U.S.A.": "United States",
        "U.S.": "United States",
        "US": "United States",
        "UK": "United Kingdom",
        "U.K.": "United Kingdom",
        "UAE": "United Arab Emirates",
        "U.A.E.": "United Arab Emirates",

        # US States (common ones)
        "CA": "California",
        "NY": "New York",
        "TX": "Texas",
        "FL": "Florida",
        "AK": "Alaska",
        "AZ": "Arizona",
        "CO": "Colorado",
        "WA": "Washington",
        "OR": "Oregon",
    }

    def expand(self, text: str) -> str:
        """Expand abbreviations in text.

        Args:
            text: Text potentially containing abbreviations

        Returns:
            Text with abbreviations expanded
        """
        result = text

        # Try each abbreviation
        for abbr, expansion in self.ABBREVIATIONS.items():
            # Use word boundary matching to avoid false matches
            pattern = r'\b' + re.escape(abbr) + r'\b'
            result = re.sub(pattern, expansion, result)

        return result

    def normalize_location_name(self, name: str) -> str:
        """Normalize a location name.

        Args:
            name: Raw location name

        Returns:
            Normalized name
        """
        # Expand abbreviations
        expanded = self.expand(name)

        # Normalize whitespace
        normalized = ' '.join(expanded.split())

        # Remove trailing punctuation
        normalized = normalized.rstrip('.,;:')

        return normalized


# Singleton instances
_coref_resolver: LocationCoreferenceResolver | None = None
_abbr_expander: AbbreviationExpander | None = None


def get_coreference_resolver() -> LocationCoreferenceResolver:
    """Get the coreference resolver instance."""
    global _coref_resolver
    if _coref_resolver is None:
        _coref_resolver = LocationCoreferenceResolver()
    return _coref_resolver


def get_abbreviation_expander() -> AbbreviationExpander:
    """Get the abbreviation expander instance."""
    global _abbr_expander
    if _abbr_expander is None:
        _abbr_expander = AbbreviationExpander()
    return _abbr_expander
