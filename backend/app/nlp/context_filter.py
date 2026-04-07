"""Context-based filtering for entity extraction.

This module provides filters to exclude entities extracted from
irrelevant contexts like:
- References and citations
- Author affiliations and addresses
- Figure and table captions (when not about study sites)
- DOIs and URLs
- Footnotes and acknowledgments

These filters improve precision by removing false positives.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from app.nlp.domain_models import GeoEntity


class ContextFilter:
    """Filter entities based on context patterns.

    Removes entities that appear in contexts where they are unlikely
    to represent actual study site locations.
    """

    # Patterns indicating reference/citation context
    REFERENCE_PATTERNS: ClassVar[list[re.Pattern[str]]] = [
        # DOI patterns
        re.compile(r"doi[:\s]*10\.\d{4,}", re.IGNORECASE),
        re.compile(r"https?://doi\.org/", re.IGNORECASE),
        # Citation brackets
        re.compile(r"\[\d+(?:[-–,\s]*\d+)*\]"),
        re.compile(r"\(\d{4}[a-z]?\)"),  # Year in parentheses
        # Journal references
        re.compile(r"et\s+al\.?\s*[,\(]?\s*\d{4}", re.IGNORECASE),
        re.compile(r"pp?\.\s*\d+[-–]\d+"),  # Page numbers
        re.compile(r"vol\.?\s*\d+", re.IGNORECASE),
        # ISBN/ISSN
        re.compile(r"ISBN[-:\s]*[\d-]+", re.IGNORECASE),
        re.compile(r"ISSN[-:\s]*[\d-]+", re.IGNORECASE),
        re.compile(r"\b(?:references?|bibliography)\b", re.IGNORECASE),
    ]

    # Patterns indicating affiliation/address context
    AFFILIATION_PATTERNS: ClassVar[list[re.Pattern[str]]] = [
        # Email addresses
        re.compile(r"[\w.+-]+@[\w.-]+\.\w{2,}"),
        # University/institution markers
        re.compile(r"(?:department|dept\.?)\s+of", re.IGNORECASE),
        re.compile(r"(?:university|institut[eo]?|college)\s+of", re.IGNORECASE),
        re.compile(r"(?:faculty|school)\s+of", re.IGNORECASE),
        # Address markers
        re.compile(r"^\s*\d+\s+[A-Z][a-z]+\s+(?:street|st\.?|avenue|ave\.?|road|rd\.?)", re.IGNORECASE),
        re.compile(r"\b(?:zip|postal)\s*code", re.IGNORECASE),
        # Correspondence markers
        re.compile(r"corresponding\s+author", re.IGNORECASE),
        re.compile(r"^\*?\s*(?:e-?mail|email)", re.IGNORECASE),
    ]

    # Patterns indicating figure/table caption (non-study-site)
    CAPTION_PATTERNS: ClassVar[list[re.Pattern[str]]] = [
        # Figure/table labels at start
        re.compile(r"^(?:fig(?:ure)?|table|tab\.?)\s*\.?\s*\d+", re.IGNORECASE),
        # Figure/table labels inline
        re.compile(r"\b(?:fig(?:ure)?|table|tab\.?)\s*\.?\s*\d+[a-z]?\b", re.IGNORECASE),
        # Supplementary material
        re.compile(r"^(?:supplementary|supporting)\s+(?:fig|table|material)", re.IGNORECASE),
        re.compile(r"\b(?:supplementary|supporting)\s+(?:fig|figure|table|material)\b", re.IGNORECASE),
        # Graph/chart descriptions (likely not location data)
        re.compile(r"(?:x[-\s]?axis|y[-\s]?axis|legend|scale\s+bar)", re.IGNORECASE),
    ]

    # Patterns indicating footnotes/acknowledgments
    FOOTNOTE_PATTERNS: ClassVar[list[re.Pattern[str]]] = [
        re.compile(r"^[\*†‡§¶#]+\s*", re.MULTILINE),
        re.compile(r"acknowledg(?:e|ment)", re.IGNORECASE),
        re.compile(r"(?:funded|supported)\s+by", re.IGNORECASE),
        re.compile(r"grant\s+(?:no\.?|number)", re.IGNORECASE),
    ]

    # Patterns that indicate a coordinate is metadata, not study data
    METADATA_PATTERNS: ClassVar[list[re.Pattern[str]]] = [
        # Satellite/sensor metadata
        re.compile(r"(?:landsat|modis|sentinel|aster)\s+\d*", re.IGNORECASE),
        re.compile(r"(?:path|row|tile)\s*[:=]?\s*\d+", re.IGNORECASE),
        # Grid/projection metadata
        re.compile(r"(?:utm|wgs[-\s]?84|epsg)\s*[:=]?\s*\d*", re.IGNORECASE),
        re.compile(r"projection\s*[:=]", re.IGNORECASE),
        # Software/tool output
        re.compile(r"(?:arcgis|qgis|gdal|r\s+package)", re.IGNORECASE),
    ]

    # Allowed caption patterns (study site descriptions in captions)
    ALLOWED_CAPTION_PATTERNS: ClassVar[list[re.Pattern[str]]] = [
        re.compile(r"(?:study|sampling|research)\s+(?:site|area|location)", re.IGNORECASE),
        re.compile(r"(?:map|location)\s+of\s+(?:the\s+)?(?:study|sampling|field)", re.IGNORECASE),
        re.compile(r"(?:overview|satellite)\s+(?:image|view)\s+of", re.IGNORECASE),
        re.compile(r"\b(?:located|location)\s+at\b", re.IGNORECASE),
        re.compile(r"\b\d{1,2}(?:\.\d+)?\s*[°º]?\s*[NS]\b", re.IGNORECASE),
    ]

    # Section-level precision filtering
    SECTION_BLOCKLIST: ClassVar[set[str]] = {
        "references",
        "bibliography",
        "acknowledgments",
        "acknowledgements",
        "author information",
        "author contributions",
        "funding",
        "appendix",
        "supplementary",
    }

    LOW_SIGNAL_SECTIONS: ClassVar[set[str]] = {
        "introduction",
        "background",
        "discussion",
        "conclusion",
        "conclusions",
        "other",
    }

    STUDY_SITE_CUE_PATTERNS: ClassVar[list[re.Pattern[str]]] = [
        re.compile(
            r"(?:study|sampling|field|research)\s+(?:site|sites|area|location|station|plot)",
            re.IGNORECASE,
        ),
        re.compile(r"\b(?:located|situated|established|collected|sampled)\s+(?:at|in|near)\b", re.IGNORECASE),
        re.compile(r"\b(?:coordinates?|latitude|longitude|lat\.?|lon\.?)\b", re.IGNORECASE),
        re.compile(r"\b\d{1,2}(?:\.\d+)?\s*[°º]?\s*[NS]\b", re.IGNORECASE),
    ]

    GENERIC_LOCATION_TERMS: ClassVar[set[str]] = {
        "study area",
        "study site",
        "study sites",
        "study location",
        "study region",
        "site",
        "sites",
        "area",
        "region",
        "location",
        "locations",
        "station",
        "stations",
        "this study",
        "our study",
    }

    def __init__(
        self,
        *,
        filter_references: bool = True,
        filter_affiliations: bool = True,
        filter_captions: bool = True,
        filter_footnotes: bool = True,
        filter_metadata: bool = True,
    ) -> None:
        """Initialize the context filter.

        Args:
            filter_references: Filter entities in reference contexts
            filter_affiliations: Filter entities in affiliation/address contexts
            filter_captions: Filter entities in figure/table captions
            filter_footnotes: Filter entities in footnotes/acknowledgments
            filter_metadata: Filter coordinates that appear to be metadata
        """
        self.filter_references = filter_references
        self.filter_affiliations = filter_affiliations
        self.filter_captions = filter_captions
        self.filter_footnotes = filter_footnotes
        self.filter_metadata = filter_metadata

    def should_filter(self, entity: GeoEntity) -> bool:
        """Check if an entity should be filtered based on context.

        Args:
            entity: Entity to check

        Returns:
            True if entity should be filtered out, False if it should be kept
        """
        context = entity.context or ""
        section = entity.section.lower().strip()

        # Hard section-level exclusions
        if section in self.SECTION_BLOCKLIST:
            return True

        # Generic placeholders are almost always false positives when extracted
        # as location entities.
        if self._is_generic_location_entity(entity):
            return True

        # In low-signal sections, require explicit study-site cues unless this
        # is an explicit coordinate.
        if section in self.LOW_SIGNAL_SECTIONS and entity.entity_type != "COORDINATE":
            if not self._matches_any(context, self.STUDY_SITE_CUE_PATTERNS):
                return True

        if not context:
            return False

        # Check reference patterns
        if self.filter_references and self._matches_any(context, self.REFERENCE_PATTERNS):
            return True

        # Check affiliation patterns
        if self.filter_affiliations and self._matches_any(context, self.AFFILIATION_PATTERNS):
            return True

        # Check footnote patterns
        if self.filter_footnotes and self._matches_any(context, self.FOOTNOTE_PATTERNS):
            return True

        # Check metadata patterns (only for coordinates)
        if self.filter_metadata and entity.entity_type == "COORDINATE":
            if self._matches_any(context, self.METADATA_PATTERNS):
                return True

        # Check caption patterns (with exceptions for study site captions)
        if self.filter_captions and self._matches_any(context, self.CAPTION_PATTERNS):
            # Allow if context indicates study site description
            if not self._matches_any(context, self.ALLOWED_CAPTION_PATTERNS):
                return True

        return False

    def filter_entities(self, entities: list[GeoEntity]) -> list[GeoEntity]:
        """Filter a list of entities based on context.

        Args:
            entities: List of entities to filter

        Returns:
            Filtered list with irrelevant entities removed
        """
        return [e for e in entities if not self.should_filter(e)]

    def _matches_any(self, text: str, patterns: list[re.Pattern[str]]) -> bool:
        """Check if text matches any of the patterns.

        Args:
            text: Text to check
            patterns: List of compiled regex patterns

        Returns:
            True if any pattern matches
        """
        return any(pattern.search(text) for pattern in patterns)

    def _is_generic_location_entity(self, entity: GeoEntity) -> bool:
        """Return whether the entity text is a generic non-toponym phrase."""
        if entity.entity_type not in {"LOC", "GPE", "CONTEXTUAL_LOCATION", "STUDY_SITE"}:
            return False

        normalized = " ".join(entity.text.lower().split())
        return normalized in self.GENERIC_LOCATION_TERMS

    def get_filter_reason(self, entity: GeoEntity) -> str | None:
        """Get the reason why an entity would be filtered.

        Useful for debugging and logging.

        Args:
            entity: Entity to check

        Returns:
            Filter reason string, or None if not filtered
        """
        context = entity.context or ""
        section = entity.section.lower().strip()

        if section in self.SECTION_BLOCKLIST:
            return "blocked_section"

        if self._is_generic_location_entity(entity):
            return "generic_location_term"

        if section in self.LOW_SIGNAL_SECTIONS and entity.entity_type != "COORDINATE":
            if not self._matches_any(context, self.STUDY_SITE_CUE_PATTERNS):
                return "low_signal_section_without_study_cue"

        if not context:
            return None

        if self.filter_references and self._matches_any(context, self.REFERENCE_PATTERNS):
            return "reference_context"

        if self.filter_affiliations and self._matches_any(context, self.AFFILIATION_PATTERNS):
            return "affiliation_context"

        if self.filter_footnotes and self._matches_any(context, self.FOOTNOTE_PATTERNS):
            return "footnote_context"

        if self.filter_metadata and entity.entity_type == "COORDINATE":
            if self._matches_any(context, self.METADATA_PATTERNS):
                return "metadata_context"

        if self.filter_captions and self._matches_any(context, self.CAPTION_PATTERNS):
            if not self._matches_any(context, self.ALLOWED_CAPTION_PATTERNS):
                return "caption_context"

        return None


# Singleton instance with default configuration
_default_filter: ContextFilter | None = None


def get_context_filter() -> ContextFilter:
    """Get the default context filter instance."""
    global _default_filter
    if _default_filter is None:
        _default_filter = ContextFilter()
    return _default_filter
