"""Enriched context extraction for coordinates.

Extracts rich contextual information around coordinates to improve
ranking accuracy and provide better debugging information.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.nlp.nlp_logger import logger

if TYPE_CHECKING:
    from spacy.tokens import Doc, Span


@dataclass
class EnrichedContext:
    """Rich contextual information for a coordinate or location."""

    # Core context
    text: str  # The coordinate/location text itself
    sentence: str  # Full sentence containing the entity
    paragraph: str  # Paragraph context (up to 500 chars)
    section: str  # Document section (methods, results, etc.)

    # Entity context
    preceding_entities: list[str] = field(default_factory=list)  # Entities before coordinate
    following_entities: list[str] = field(default_factory=list)  # Entities after coordinate

    # Geographic context
    geographic_keywords: list[str] = field(default_factory=list)  # Nearby geographic terms
    figure_reference: str | None = None  # Reference to figure/table if any

    # Position context
    distance_from_section_start: int = 0  # Character distance from section start
    sentence_position: int = 0  # Sentence number in section
    token_position: int = 0  # Token position in document

    # Quality indicators
    context_quality: float = 1.0  # Quality score for context (0-1)

    def __str__(self) -> str:
        """Human-readable context summary."""
        return (
            f"Context for '{self.text}' in {self.section}:\n"
            f"  Sentence: {self.sentence[:100]}...\n"
            f"  Entities: {len(self.preceding_entities)} before, "
            f"{len(self.following_entities)} after\n"
            f"  Keywords: {', '.join(self.geographic_keywords[:5])}\n"
            f"  Figure ref: {self.figure_reference or 'None'}"
        )


class ContextExtractor:
    """Extract enriched context for coordinates and locations."""

    # Geographic keywords to look for in context
    GEOGRAPHIC_KEYWORDS = {
        # Location types
        "site",
        "sites",
        "location",
        "locations",
        "area",
        "areas",
        "region",
        "regions",
        "zone",
        "zones",
        "plot",
        "plots",
        "station",
        "stations",
        "transect",
        "transects",
        "quadrat",
        "quadrats",
        # Study descriptors
        "study",
        "sampling",
        "field",
        "research",
        "survey",
        "monitoring",
        "measurement",
        # Spatial terms
        "coordinate",
        "coordinates",
        "latitude",
        "longitude",
        "elevation",
        "altitude",
        "situated",
        "located",
        "positioned",
        "established",
        # Geographic features
        "forest",
        "mountain",
        "river",
        "lake",
        "ocean",
        "coast",
        "island",
        "valley",
        "plateau",
        "hill",
    }

    # Figure/table reference patterns
    FIGURE_PATTERNS = [
        re.compile(r"\b(Fig(?:ure)?\.?\s*\d+[A-Z]?)\b", re.IGNORECASE),
        re.compile(r"\b(Table\.?\s*\d+)\b", re.IGNORECASE),
        re.compile(r"\b(Supplementary\s+Fig(?:ure)?\.?\s*\d+)\b", re.IGNORECASE),
        re.compile(r"\b(Appendix\s+[A-Z]\d*)\b", re.IGNORECASE),
    ]

    def __init__(self, context_window: int = 50, max_paragraph_chars: int = 500):
        """Initialize context extractor.

        Args:
            context_window: Number of tokens to look at before/after entity
            max_paragraph_chars: Maximum paragraph context length
        """
        self.context_window = context_window
        self.max_paragraph_chars = max_paragraph_chars

    def extract_context(
        self, doc: Doc, entity_span: Span, section: str = "unknown"
    ) -> EnrichedContext:
        """Extract enriched context for an entity.

        Args:
            doc: spaCy Doc containing the entity
            entity_span: Span of the entity (coordinate or location)
            section: Document section name

        Returns:
            EnrichedContext with all extracted information
        """
        # Get sentence and paragraph
        sentence = self._get_sentence(entity_span)
        paragraph = self._get_paragraph(doc, entity_span)

        # Get nearby entities
        preceding_entities, following_entities = self._get_nearby_entities(
            doc, entity_span
        )

        # Extract geographic keywords
        keywords = self._extract_geographic_keywords(doc, entity_span)

        # Find figure references
        figure_ref = self._find_figure_reference(sentence)

        # Calculate position metrics
        distance = self._calculate_distance_from_section_start(entity_span, section)
        sent_pos = self._get_sentence_position(doc, entity_span)

        # Assess context quality
        quality = self._assess_context_quality(sentence, paragraph, keywords)

        return EnrichedContext(
            text=entity_span.text,
            sentence=sentence,
            paragraph=paragraph,
            section=section,
            preceding_entities=preceding_entities,
            following_entities=following_entities,
            geographic_keywords=keywords,
            figure_reference=figure_ref,
            distance_from_section_start=distance,
            sentence_position=sent_pos,
            token_position=entity_span.start,
            context_quality=quality,
        )

    def _get_sentence(self, span: Span) -> str:
        """Get the full sentence containing the span."""
        try:
            return span.sent.text.strip()
        except Exception:
            # Fallback if sentence detection fails
            return span.text

    def _get_paragraph(self, doc: Doc, span: Span) -> str:
        """Get paragraph context around the span.

        Args:
            doc: Full document
            span: Entity span

        Returns:
            Paragraph text (up to max_paragraph_chars)
        """
        # Get surrounding sentences (current + 1 before + 1 after)
        try:
            current_sent = span.sent
            sent_start = current_sent.start
            sent_end = current_sent.end

            # Try to get previous sentence
            if sent_start > 0:
                prev_sent = doc[sent_start - 1].sent
                sent_start = prev_sent.start

            # Try to get next sentence
            if sent_end < len(doc):
                try:
                    next_sent = doc[sent_end].sent
                    sent_end = next_sent.end
                except Exception:
                    pass

            paragraph = doc[sent_start:sent_end].text.strip()

            # Truncate if too long
            if len(paragraph) > self.max_paragraph_chars:
                paragraph = paragraph[: self.max_paragraph_chars] + "..."

            return paragraph

        except Exception as e:
            logger.debug(f"Error extracting paragraph: {e}")
            return span.sent.text if hasattr(span, "sent") else span.text

    def _get_nearby_entities(
        self, doc: Doc, span: Span
    ) -> tuple[list[str], list[str]]:
        """Extract named entities near the coordinate.

        Args:
            doc: Full document
            span: Entity span

        Returns:
            Tuple of (preceding_entities, following_entities)
        """
        window_start = max(0, span.start - self.context_window)
        window_end = min(len(doc), span.end + self.context_window)

        preceding = []
        following = []

        for ent in doc.ents:
            # Skip the entity itself
            if ent.start == span.start and ent.end == span.end:
                continue

            # Check if entity is in context window
            if window_start <= ent.start < window_end:
                if ent.start < span.start:
                    preceding.append(f"{ent.text} ({ent.label_})")
                elif ent.start >= span.end:
                    following.append(f"{ent.text} ({ent.label_})")

        return preceding, following

    def _extract_geographic_keywords(self, doc: Doc, span: Span) -> list[str]:
        """Extract geographic keywords near the entity.

        Args:
            doc: Full document
            span: Entity span

        Returns:
            List of geographic keywords found
        """
        window_start = max(0, span.start - self.context_window)
        window_end = min(len(doc), span.end + self.context_window)

        keywords = []
        for token in doc[window_start:window_end]:
            if token.text.lower() in self.GEOGRAPHIC_KEYWORDS:
                keywords.append(token.text.lower())

        # Deduplicate while preserving order
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)

        return unique_keywords

    def _find_figure_reference(self, text: str) -> str | None:
        """Find figure or table references in text.

        Args:
            text: Text to search

        Returns:
            Figure reference string or None
        """
        for pattern in self.FIGURE_PATTERNS:
            match = pattern.search(text)
            if match:
                return match.group(1)

        return None

    def _calculate_distance_from_section_start(
        self, span: Span, section: str
    ) -> int:
        """Calculate character distance from section start.

        Args:
            span: Entity span
            section: Section name

        Returns:
            Character distance from section start
        """
        # Simple approximation - use character position
        return span.start_char

    def _get_sentence_position(self, doc: Doc, span: Span) -> int:
        """Get sentence number in document.

        Args:
            doc: Full document
            span: Entity span

        Returns:
            Sentence position (0-indexed)
        """
        try:
            current_sent = span.sent
            sentences = list(doc.sents)
            for i, sent in enumerate(sentences):
                if sent.start == current_sent.start:
                    return i
            return 0
        except Exception:
            return 0

    def _assess_context_quality(
        self, sentence: str, paragraph: str, keywords: list[str]
    ) -> float:
        """Assess the quality of extracted context.

        Args:
            sentence: Sentence text
            paragraph: Paragraph text
            keywords: Geographic keywords found

        Returns:
            Quality score (0-1)
        """
        score = 0.0

        # Sentence length (prefer substantial sentences)
        if len(sentence) > 50:
            score += 0.3
        elif len(sentence) > 20:
            score += 0.15

        # Paragraph richness
        if len(paragraph) > 200:
            score += 0.3
        elif len(paragraph) > 100:
            score += 0.15

        # Geographic keywords
        if len(keywords) >= 3:
            score += 0.4
        elif len(keywords) >= 1:
            score += 0.2

        return min(1.0, score)


# Example usage
if __name__ == "__main__":
    import spacy

    nlp = spacy.load("en_core_web_sm")
    extractor = ContextExtractor()

    # Test text
    text = """
    Study sites were established in Ecuador at coordinates 45.5°N, 122.3°W.
    The research area encompassed three distinct ecological zones located in
    the Andes mountains. Sampling occurred at each site from January to
    December 2020. As shown in Figure 2, the sites were distributed across
    an elevation gradient from 1000m to 3000m above sea level.
    """

    doc = nlp(text)

    # Find coordinate-like text (simplified for demo)
    for ent in doc.ents:
        context = extractor.extract_context(doc, ent, section="methods")
        print(f"\n{context}")
        print("-" * 80)
