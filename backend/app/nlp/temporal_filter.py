"""Temporal context filtering for study site extraction.

This module differentiates between:
- Current study sites (locations where the research was actually conducted)
- Historical references (locations mentioned in literature review or comparisons)
- Future/hypothetical locations (proposed study sites)

This is a Priority 3 improvement that improves precision by focusing on
the actual study locations rather than references to other studies.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, ClassVar

from app.nlp.nlp_logger import logger

if TYPE_CHECKING:
    from app.nlp.domain_models import GeoEntity


class TemporalContext(Enum):
    """Temporal context categories for location mentions."""

    CURRENT_STUDY = "current_study"  # This study's locations
    HISTORICAL = "historical"  # Past studies, literature review
    COMPARATIVE = "comparative"  # Comparison with other studies
    FUTURE = "future"  # Proposed/future locations
    UNKNOWN = "unknown"  # Cannot determine


@dataclass
class TemporalClassification:
    """Result of temporal context classification."""

    context: TemporalContext
    confidence: float
    indicators: list[str]  # Phrases that led to this classification


class TemporalContextFilter:
    """Filter and classify entities based on temporal context.

    Identifies whether a location mention refers to:
    - The current study's actual research sites
    - Historical locations from previous research
    - Comparative references to other studies
    """

    # Indicators for current study locations (high priority)
    CURRENT_STUDY_INDICATORS: ClassVar[list[re.Pattern[str]]] = [
        # First person indicators
        re.compile(r"\b(we|our)\s+(studied|sampled|collected|measured|observed|conducted)", re.I),
        re.compile(r"\b(we|our)\s+\w+\s+(at|in|from|near)\b", re.I),
        re.compile(r"\b(our|this)\s+(study|research|work|investigation)\b", re.I),

        # Present/past tense of this study
        re.compile(r"\bthis\s+study\s+(was\s+conducted|took\s+place|focused)\b", re.I),
        re.compile(r"\bthe\s+present\s+study\b", re.I),
        re.compile(r"\bin\s+this\s+(paper|study|work|research)\b", re.I),

        # Site establishment for this study
        re.compile(r"\b(sites?|plots?|transects?)\s+were\s+(established|set\s+up|installed)\b", re.I),
        re.compile(r"\bwe\s+(established|selected|chose|identified)\s+\w*\s*(sites?|locations?)\b", re.I),

        # Data collection in this study
        re.compile(r"\bdata\s+(were|was)\s+collected\b", re.I),
        re.compile(r"\bsamples?\s+(were|was)\s+(collected|taken|obtained)\b", re.I),
        re.compile(r"\bmeasurements?\s+(were|was)\s+(made|taken|recorded)\b", re.I),

        # Field work
        re.compile(r"\bfield\s*(work|campaign|season)\s+(was|were)\s+conducted\b", re.I),
        re.compile(r"\bduring\s+(the\s+)?(field|study|sampling)\s+(campaign|period|season)\b", re.I),

        # Explicit current indicators
        re.compile(r"\b(currently|presently)\b", re.I),
        re.compile(r"\bfor\s+this\s+(analysis|study|investigation)\b", re.I),
    ]

    # Indicators for historical/previous studies (lower priority)
    HISTORICAL_INDICATORS: ClassVar[list[re.Pattern[str]]] = [
        # Citations and references
        re.compile(r"\b\([^)]*\d{4}[a-z]?\s*\)", re.I),  # (Author, 2020)
        re.compile(r"\b[A-Z][a-z]+\s+et\s+al\.?\s*\(?\d{4}", re.I),  # Smith et al. 2020
        re.compile(r"\baccording\s+to\b", re.I),
        re.compile(r"\breported\s+by\b", re.I),

        # Previous study indicators
        re.compile(r"\b(previous|earlier|prior|past)\s+(studies?|research|work|investigations?)\b", re.I),
        re.compile(r"\b(previously|earlier|formerly)\s+(studied|investigated|examined)\b", re.I),
        re.compile(r"\bhas\s+been\s+(studied|investigated|documented)\b", re.I),
        re.compile(r"\bwere\s+(first\s+)?(described|reported|documented)\s+by\b", re.I),

        # Historical time references
        re.compile(r"\bin\s+the\s+(past|1\d{3}s|early|late)\b", re.I),
        re.compile(r"\bhistorically\b", re.I),
        re.compile(r"\b(ancient|historical|prehistoric)\b", re.I),

        # Literature review phrases
        re.compile(r"\bliterature\s+(review|survey|search)\b", re.I),
        re.compile(r"\bexisting\s+(studies?|research|literature)\b", re.I),
    ]

    # Indicators for comparative references
    COMPARATIVE_INDICATORS: ClassVar[list[re.Pattern[str]]] = [
        # Comparison phrases
        re.compile(r"\b(compared\s+to|in\s+comparison\s+with|similar\s+to)\b", re.I),
        re.compile(r"\b(unlike|contrary\s+to|in\s+contrast\s+to)\b", re.I),
        re.compile(r"\b(elsewhere|other\s+regions?|other\s+areas?)\b", re.I),

        # Reference to other locations
        re.compile(r"\b(such\s+as|for\s+example|e\.g\.|including)\b", re.I),
        re.compile(r"\b(also|similarly)\s+(found|observed|reported)\s+in\b", re.I),
    ]

    # Indicators for future/proposed locations
    FUTURE_INDICATORS: ClassVar[list[re.Pattern[str]]] = [
        re.compile(r"\b(will|would|could|should|might)\s+(be\s+)?(studied|investigated)\b", re.I),
        re.compile(r"\b(future|planned|proposed|potential)\s+(study|research|work)\b", re.I),
        re.compile(r"\b(recommend|suggest)\s+(studying|investigating)\b", re.I),
    ]

    # Section-based context hints
    CURRENT_STUDY_SECTIONS: ClassVar[set[str]] = {
        "study_area", "study site", "methods", "materials and methods",
        "data", "data collection", "field methods", "sampling",
    }

    HISTORICAL_SECTIONS: ClassVar[set[str]] = {
        "introduction", "background", "literature review",
        "previous studies", "related work",
    }

    def __init__(
        self,
        prioritize_current: bool = True,
        min_confidence: float = 0.6,
    ) -> None:
        """Initialize the temporal context filter.

        Args:
            prioritize_current: If True, prioritize current study locations
            min_confidence: Minimum confidence for temporal classification
        """
        self.prioritize_current = prioritize_current
        self.min_confidence = min_confidence

    def classify(
        self,
        entity: GeoEntity,
    ) -> TemporalClassification:
        """Classify the temporal context of an entity.

        Args:
            entity: Entity to classify

        Returns:
            TemporalClassification with context and confidence
        """
        context = entity.context or ""
        section = entity.section.lower() if entity.section else ""

        # Count indicators for each category
        current_matches = self._find_matches(context, self.CURRENT_STUDY_INDICATORS)
        historical_matches = self._find_matches(context, self.HISTORICAL_INDICATORS)
        comparative_matches = self._find_matches(context, self.COMPARATIVE_INDICATORS)
        future_matches = self._find_matches(context, self.FUTURE_INDICATORS)

        # Section-based hints
        section_hint = None
        if any(s in section for s in self.CURRENT_STUDY_SECTIONS):
            section_hint = TemporalContext.CURRENT_STUDY
        elif any(s in section for s in self.HISTORICAL_SECTIONS):
            section_hint = TemporalContext.HISTORICAL

        # Determine context based on matches
        scores = {
            TemporalContext.CURRENT_STUDY: len(current_matches) * 2,  # Weighted higher
            TemporalContext.HISTORICAL: len(historical_matches),
            TemporalContext.COMPARATIVE: len(comparative_matches),
            TemporalContext.FUTURE: len(future_matches),
        }

        # Apply section hint bonus
        if section_hint:
            scores[section_hint] += 1.5

        # Find best match
        best_context = max(scores, key=scores.get)
        best_score = scores[best_context]
        total_score = sum(scores.values()) + 0.1  # Avoid division by zero

        # Calculate confidence
        if best_score == 0:
            return TemporalClassification(
                context=TemporalContext.UNKNOWN,
                confidence=0.5,
                indicators=[],
            )

        confidence = min(0.95, 0.5 + (best_score / total_score) * 0.5)

        # Get relevant indicators
        indicators_map = {
            TemporalContext.CURRENT_STUDY: current_matches,
            TemporalContext.HISTORICAL: historical_matches,
            TemporalContext.COMPARATIVE: comparative_matches,
            TemporalContext.FUTURE: future_matches,
        }

        return TemporalClassification(
            context=best_context,
            confidence=confidence,
            indicators=indicators_map.get(best_context, []),
        )

    def _find_matches(
        self,
        text: str,
        patterns: list[re.Pattern[str]],
    ) -> list[str]:
        """Find all pattern matches in text."""
        matches = []
        for pattern in patterns:
            for match in pattern.finditer(text):
                matches.append(match.group())
        return matches

    def filter_entities(
        self,
        entities: list[GeoEntity],
        keep_contexts: set[TemporalContext] | None = None,
    ) -> list[GeoEntity]:
        """Filter entities based on temporal context.

        Args:
            entities: List of entities to filter
            keep_contexts: Set of contexts to keep (default: CURRENT_STUDY only)

        Returns:
            Filtered list of entities
        """
        if keep_contexts is None:
            keep_contexts = {TemporalContext.CURRENT_STUDY, TemporalContext.UNKNOWN}

        filtered = []
        removed_count = 0

        for entity in entities:
            classification = self.classify(entity)

            # Keep if context matches or confidence is too low to filter
            if (
                classification.context in keep_contexts
                or classification.confidence < self.min_confidence
            ):
                filtered.append(entity)
            else:
                removed_count += 1
                logger.debug(
                    f"Filtered '{entity.text[:30]}...' as {classification.context.value} "
                    f"(confidence: {classification.confidence:.2f})"
                )

        if removed_count > 0:
            logger.info(
                f"Temporal filtering: removed {removed_count} historical/comparative references"
            )

        return filtered

    def annotate_entities(
        self,
        entities: list[GeoEntity],
    ) -> list[tuple[GeoEntity, TemporalClassification]]:
        """Annotate entities with temporal context (without filtering).

        Args:
            entities: List of entities to annotate

        Returns:
            List of (entity, classification) tuples
        """
        return [(entity, self.classify(entity)) for entity in entities]

    def get_current_study_entities(
        self,
        entities: list[GeoEntity],
    ) -> list[GeoEntity]:
        """Get only entities that refer to the current study.

        Args:
            entities: List of entities

        Returns:
            Entities classified as CURRENT_STUDY
        """
        return self.filter_entities(
            entities,
            keep_contexts={TemporalContext.CURRENT_STUDY},
        )


# Singleton instance
_filter: TemporalContextFilter | None = None


def get_temporal_filter() -> TemporalContextFilter:
    """Get the temporal context filter instance."""
    global _filter
    if _filter is None:
        _filter = TemporalContextFilter()
    return _filter
