"""Entity extractors for spaCy, BERT/Transformer, and explicit extraction.

The spaCyExtractor is inspired by Geospacy.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar, Protocol, override

import spacy
from spacy.tokens import Doc

from app.nlp.domain_models import GeoEntity
from app.nlp.model_config import model_settings
from app.nlp.text_processing import (
    CoordinateParser,
    PDFTextCleaner,
    SpatialRelationExtractor,
)
from maress_types import NERResultKeys

if TYPE_CHECKING:
    from spacy.language import Language
    from spacy.tokens import Span
    from transformers import Pipeline

    from app.nlp.model_config import ModelConfig


class EntityExtractor(Protocol):
    """Protocol for entity extraction strategies."""

    def extract(self, text: str, section: str) -> list[GeoEntity]:
        """Extract entities from text."""
        ...


class BaseEntityExtractor(ABC):
    """Abstract base for extraction strategies (Open/Closed Principle)."""

    def __init__(self, config: ModelConfig) -> None:
        """Initialize extractor with configuration."""
        self.config: ModelConfig = config
        self.nlp: Language = spacy.load(model_settings.SPACY_MODEL)

    def set_nlp(self, nlp: Language) -> None:
        """Inject spaCy model for sentence detection."""
        self.nlp = nlp

    @abstractmethod
    def extract(self, text: str, section: str) -> list[GeoEntity]:
        """Extract entities from text section."""

    def _get_context(self, text: str, start: int) -> str:
        """Extract context window around entity."""
        doc = self.nlp(text)
        for sent in doc.sents:
            if sent.start_char <= start < sent.end_char:
                return sent.text.strip()
        # We need a fallback for locations from non-sentence context
        return self._get_range_context(text, start, self.config.CONTEXT_WINDOW)

    def _get_range_context(self, text: str, start: int, window: int) -> str:
        """Extract fixed character window around entity."""
        begin = max(0, start - window)
        end = min(len(text), start + window)
        return text[begin:end].strip()


class CoordinateExtractor(BaseEntityExtractor):
    """Extracts explicit coordinate entities."""

    def __init__(self, config: ModelConfig) -> None:
        """Initialize coordinate extractor."""
        super().__init__(config)
        self.parser: CoordinateParser = CoordinateParser()
        self.cleaner: PDFTextCleaner = PDFTextCleaner()

    @override
    def extract(self, text: str, section: str) -> list[GeoEntity]:
        """Extract coordinate entities from text."""
        clean_text = self.cleaner.clean(text)
        coordinate_matches = self.parser.extract_coordinates(clean_text)

        entities: list[GeoEntity] = []
        for coord_str, start, end in coordinate_matches:
            context = self._get_context(clean_text, start)
            parsed_coords = self.parser.parse_to_decimal(coord_str)

            entities.append(
                GeoEntity(
                    text=coord_str,
                    entity_type="COORDINATE",
                    context=context,
                    section=section,
                    confidence=1.0,  # Pattern-based extraction
                    start_char=start,
                    end_char=end,
                    coordinates=parsed_coords,
                ),
            )

        return entities


class SpatialRelationEntityExtractor(BaseEntityExtractor):
    """Extracts spatial relation entities."""

    def __init__(self, config: ModelConfig) -> None:
        """Initialize spatial relation extractor."""
        super().__init__(config)
        self.extractor: SpatialRelationExtractor = SpatialRelationExtractor()
        self.cleaner: PDFTextCleaner = PDFTextCleaner()

    @override
    def extract(self, text: str, section: str) -> list[GeoEntity]:
        """Extract spatial relation entities."""
        clean_text = self.cleaner.clean(text)
        matches = self.extractor.extract(clean_text)

        entities: list[GeoEntity] = []
        for relation_str, start, end in matches:
            context = self._get_context(clean_text, start)

            entities.append(
                GeoEntity(
                    text=relation_str,
                    entity_type="SPATIAL_RELATION",
                    context=context,
                    section=section,
                    confidence=0.9,
                    start_char=start,
                    end_char=end,
                ),
            )

        return entities


class TransformerNERExtractor(BaseEntityExtractor):
    """Extracts location entities using transformer models."""

    def __init__(self, config: ModelConfig, ner_pipeline: Pipeline) -> None:
        """Initialize transformer-based extractor.

        Args:
            config: Model configuration
            ner_pipeline: Pre-initialised Hugging Face pipeline
        """
        super().__init__(config)
        self.ner_pipeline: Pipeline = ner_pipeline

    @override
    def extract(self, text: str, section: str) -> list[GeoEntity]:
        """Extract location entities using BERT/transformer model."""
        return self._extract_sentence_based(text, section)

    def _extract_sentence_based(self, text: str, section: str) -> list[GeoEntity]:
        doc = self.nlp(text)
        entities: list[GeoEntity] = []

        for sent in doc.sents:
            sent_text = sent.text
            sent_start = sent.start_char

            # Run NER on sentence
            ner_results: dict[NERResultKeys, int | str] = self.ner_pipeline(sent_text)

            for entity in ner_results:
                if entity["entity_group"] not in ["LOC", "GPE"]:
                    continue

                if entity["score"] < self.config.MIN_CONFIDENCE:
                    continue

                # Adjust positions to document coordinates
                abs_start = sent_start + entity["start"]
                abs_end = sent_start + entity["end"]

                entities.append(
                    GeoEntity(
                        text=entity["word"],
                        entity_type=entity["entity_group"],
                        context=sent_text,  # Full sentence as context
                        section=section,
                        confidence=entity["score"],
                        start_char=abs_start,
                        end_char=abs_end,
                    ),
                )

        return entities


class SpaCyGeoExtractor(BaseEntityExtractor):
    """Extract geospatial entities using spaCy NER (Geospacy-inspired).

    Extracts standard NER entities (LOC, GPE, FAC, NORP) and identifies
    spatial relation phrases using linguistic patterns.
    """

    # Geospatial entity labels from spaCy NER
    GEO_LABELS: ClassVar[set[str]] = {"LOC", "GPE", "FAC", "NORP"}

    # Spatial relation patterns inspired by Geospacy
    # These capture directional and proximity relations
    SPATIAL_PREPOSITIONS: ClassVar[set[str]] = {
        "near",
        "close to",
        "adjacent to",
        "next to",
        "beside",
        "north of",
        "south of",
        "east of",
        "west of",
        "northeast of",
        "northwest of",
        "southeast of",
        "southwest of",
        "within",
        "inside",
        "outside",
        "around",
        "surrounding",
        "upstream of",
        "downstream of",
        "offshore from",
    }

    DISTANCE_INDICATORS: ClassVar[set[str]] = {
        "km",
        "kilometers",
        "miles",
        "meters",
        "m",
        "away from",
        "from",
        "distant from",
    }

    LOCATION_INDICATORS: ClassVar[set[str]] = {
        "located",
        "situated",
        "positioned",
        "found",
        "region",
        "area",
        "vicinity",
        "site",
        "station",
    }

    def __init__(self, config: ModelConfig) -> None:
        """Initialize spaCy-based geo extractor."""
        super().__init__(config)
        self.cleaner: PDFTextCleaner = PDFTextCleaner()
        # Track seen entities to avoid duplicates
        self._seen_spans: set[tuple[int, int]] = set()

    @override
    def extract(self, text: str, section: str) -> list[GeoEntity]:
        """Extract geospatial entities from text without duplicates.

        Args:
            text: Text to process
            section: Document section name

        Returns:
            List of unique GeoEntity objects
        """
        # Reset seen spans for each new extraction
        self._seen_spans.clear()

        clean_text = self.cleaner.clean(text)
        doc = self.nlp(clean_text)

        entities: list[GeoEntity] = []
        entities.extend(self._extract_ner_entities(doc, section))
        entities.extend(self._extract_spatial_relations(doc, section))
        entities.extend(self._extract_contextual_locations(doc, section))

        return entities

    def _extract_ner_entities(self, doc: Doc, section: str) -> list[GeoEntity]:
        """Extract standard spaCy NER geographic entities."""
        entities: list[GeoEntity] = []

        for ent in doc.ents:
            print(ent.text, ent.label_)
            if ent.label_ not in self.GEO_LABELS:
                continue

            # Check for duplicates
            span_key = (ent.start_char, ent.end_char)
            if span_key in self._seen_spans:
                continue

            self._seen_spans.add(span_key)

            # Get sentence context
            context = ent.sent.text if ent.sent else self._get_context(doc.text, ent.start_char)

            entities.append(
                GeoEntity(
                    text=ent.text,
                    entity_type=ent.label_,
                    context=context,
                    section=section,
                    confidence=0.95,  # High confidence for NER
                    start_char=ent.start_char,
                    end_char=ent.end_char,
                ),
            )

        return entities

    def _extract_spatial_relations(self, doc: Doc, section: str) -> list[GeoEntity]:
        """Extract spatial relation phrases (e.g., '10 km north of Paris').

        This implements Geospacy's approach to identifying spatial
        expressions.
        """
        entities: list[GeoEntity] = []

        for sent in doc.sents:
            sent_text_lower = sent.text.lower()

            # Check for spatial prepositions
            for prep in self.SPATIAL_PREPOSITIONS:
                if prep not in sent_text_lower:
                    continue

                # Find the span containing the spatial relation
                span = self._find_spatial_relation_span(sent, prep)
                if not span:
                    continue

                span_key = (span.start_char, span.end_char)
                if span_key in self._seen_spans:
                    continue

                self._seen_spans.add(span_key)

                entities.append(
                    GeoEntity(
                        text=span.text,
                        entity_type="SPATIAL_RELATION",
                        context=sent.text,
                        section=section,
                        confidence=0.85,
                        start_char=span.start_char,
                        end_char=span.end_char,
                    ),
                )

        return entities

    def _extract_contextual_locations(self, doc: Doc, section: str) -> list[GeoEntity]:
        """Extract location mentions using contextual indicators.

        Identifies phrases like 'study site in', 'research station at',
        etc.
        """
        entities: list[GeoEntity] = []

        for sent in doc.sents:
            sent_text_lower = sent.text.lower()

            # Look for location indicators
            for indicator in self.LOCATION_INDICATORS:
                if indicator not in sent_text_lower:
                    continue

                # Find potential location entities near the indicator
                span = self._find_location_near_indicator(sent, indicator)
                if not span:
                    continue

                span_key = (span.start_char, span.end_char)
                if span_key in self._seen_spans:
                    continue

                self._seen_spans.add(span_key)

                entities.append(
                    GeoEntity(
                        text=span.text,
                        entity_type="CONTEXTUAL_LOCATION",
                        context=sent.text,
                        section=section,
                        confidence=0.75,
                        start_char=span.start_char,
                        end_char=span.end_char,
                    ),
                )

        return entities

    def _find_spatial_relation_span(self, sent: Span, spatial_prep: str) -> Span | None:
        """Find the span containing a spatial relation expression.

        Looks for patterns like:
        - "10 km north of Paris"
        - "near the Amazon River"
        - "adjacent to the research station"
        """
        sent_text = sent.text
        sent_text_lower = sent_text.lower()

        # Find the position of the spatial preposition
        prep_start = sent_text_lower.find(spatial_prep)
        if prep_start == -1:
            return None

        # Look backward for distance/quantity
        pre_text = sent_text_lower[:prep_start].strip()
        tokens_before = pre_text.split()

        # Check if there's a distance indicator
        start_offset = 0
        if len(tokens_before) >= 2:
            # Look for patterns like "10 km" or "5 miles"
            for i in range(len(tokens_before) - 1, max(0, len(tokens_before) - 4), -1):
                if any(dist in tokens_before[i] for dist in self.DISTANCE_INDICATORS):
                    start_offset = sent_text_lower.find(" ".join(tokens_before[i:]))
                    break

        if start_offset == 0:
            start_offset = prep_start

        # Look forward for the location entity
        post_text = sent_text[prep_start + len(spatial_prep) :].strip()

        # Find the end of the spatial relation (usually up to punctuation or end of phrase)
        end_offset = prep_start + len(spatial_prep)

        # Look for the next proper noun or entity
        for token in sent[sent.start :]:
            if token.idx >= prep_start + len(spatial_prep):
                if token.pos_ in ["PROPN", "NOUN"] or token.ent_type_ in self.GEO_LABELS:
                    end_offset = token.idx + len(token.text)
                    # Continue until we hit punctuation or conjunction
                    continue
                if token.pos_ in ["PUNCT", "CCONJ", "SCONJ"]:
                    break

        # Create span from sent character offsets
        abs_start = sent.start_char + start_offset
        abs_end = sent.start_char + end_offset

        # Return a pseudo-span (we'll use the text slice)
        return self._create_span_from_chars(sent.doc, abs_start, abs_end)

    def _find_location_near_indicator(self, sent: Span, indicator: str) -> Span | None:
        """Find location entity near a location indicator phrase."""
        sent_text_lower = sent.text.lower()

        # Find indicator position
        ind_start = sent_text_lower.find(indicator)
        if ind_start == -1:
            return None

        # Look for entities within 50 characters after the indicator
        search_window = sent.text[ind_start : ind_start + 50]

        # Find the first proper noun or existing NER entity
        for token in sent[sent.start :]:
            if token.idx < ind_start + len(indicator):
                continue

            if token.idx > ind_start + 50:
                break

            if token.pos_ == "PROPN" or token.ent_type_ in self.GEO_LABELS:
                # Expand to include compound nouns
                start_idx = token.idx
                end_idx = token.idx + len(token.text)

                # Expand forward
                next_token_idx = token.i + 1
                while next_token_idx < len(sent):
                    next_token = sent[next_token_idx]
                    if next_token.pos_ in ["PROPN", "NOUN"]:
                        end_idx = next_token.idx + len(next_token.text)
                        next_token_idx += 1
                    else:
                        break

                return self._create_span_from_chars(sent.doc, start_idx, end_idx)

        return None

    def _create_span_from_chars(self, doc: Doc, start_char: int, end_char: int) -> Span:
        """Create a spaCy Span from character positions."""
        # Find token indices
        start_token = None
        end_token = None

        for token in doc:
            if start_token is None and token.idx >= start_char:
                start_token = token.i
            if token.idx + len(token.text) >= end_char:
                end_token = token.i + 1
                break

        if start_token is None or end_token is None:
            # Fallback: return a span with the character positions
            return doc[0:1]  # Dummy span

        return doc[start_token:end_token]
