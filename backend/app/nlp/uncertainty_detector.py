"""Uncertainty detection for study site mentions.

Identifies whether location mentions are:
- Confirmed study sites (high certainty)
- Tentative/proposed sites (low certainty)
- Potential/candidate sites (medium certainty)

This helps distinguish between actual research locations and hypothetical ones,
improving precision by adjusting confidence scores accordingly.

This is a Priority 4 improvement that refines confidence estimation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

from app.nlp.domain_models import GeoEntity
from app.nlp.nlp_logger import logger


class CertaintyLevel(Enum):
    """Certainty level for location mentions."""

    CONFIRMED = "confirmed"  # Definitely the study site
    LIKELY = "likely"  # Probably the study site
    TENTATIVE = "tentative"  # Possibly the study site
    PROPOSED = "proposed"  # Future/hypothetical site
    UNCERTAIN = "uncertain"  # Cannot determine


@dataclass
class UncertaintyAssessment:
    """Assessment of certainty for a location mention."""

    certainty_level: CertaintyLevel
    confidence_multiplier: float  # Multiply entity confidence by this
    indicators: list[str]  # Phrases that led to this assessment


class UncertaintyDetector:
    """Detect uncertainty in location mentions.

    Analyzes linguistic markers to determine if a location is:
    - Actually used in the study
    - Tentatively proposed
    - Hypothetically mentioned
    """

    # High certainty indicators
    CONFIRMED_INDICATORS: ClassVar[list[re.Pattern[str]]] = [
        # Strong statements
        re.compile(r"\b(we|our)\s+(studied|sampled|collected|measured|observed)\b", re.I),
        re.compile(r"\bdata\s+(were|was)\s+collected\s+(?:from|at|in)\b", re.I),
        re.compile(r"\bfield\s+work\s+was\s+conducted\s+(?:at|in)\b", re.I),
        re.compile(r"\bsamples?\s+(were|was)\s+(collected|taken|obtained)\s+(?:from|at)\b", re.I),
        re.compile(r"\bmeasurements?\s+(were|was)\s+(made|taken|recorded)\s+(?:at|in)\b", re.I),

        # Site establishment
        re.compile(r"\bsites?\s+(were|was)\s+(established|selected|installed)\s+(?:at|in)\b", re.I),
        re.compile(r"\bthe\s+study\s+(?:was|is)\s+conducted\s+(?:at|in)\b", re.I),

        # Definite present/past tense
        re.compile(r"\b(?:is|was)\s+located\s+(?:at|in)\b", re.I),
        re.compile(r"\b(?:is|are)\s+situated\s+(?:at|in)\b", re.I),
    ]

    # Medium certainty indicators
    LIKELY_INDICATORS: ClassVar[list[re.Pattern[str]]] = [
        re.compile(r"\bthe\s+study\s+(?:area|site|region)\s+(?:is|was)\b", re.I),
        re.compile(r"\bin\s+this\s+(?:study|research|work)\b", re.I),
        re.compile(r"\bour\s+(?:site|area|region)\b", re.I),
    ]

    # Low certainty indicators
    TENTATIVE_INDICATORS: ClassVar[list[re.Pattern[str]]] = [
        # Modal verbs
        re.compile(r"\b(may|might|could|possibly)\s+(?:be|have)\b", re.I),
        re.compile(r"\b(perhaps|potentially|possibly)\b", re.I),

        # Hedging
        re.compile(r"\b(suggests?|indicates?|implies?)\s+that\b", re.I),
        re.compile(r"\b(appears?|seems?)\s+to\b", re.I),
        re.compile(r"\b(likely|probably|presumably)\b", re.I),

        # Approximations
        re.compile(r"\b(approximately|roughly|about|around)\b", re.I),
    ]

    # Proposed/future indicators
    PROPOSED_INDICATORS: ClassVar[list[re.Pattern[str]]] = [
        re.compile(r"\b(will|would|should)\s+(?:be|have)\b", re.I),
        re.compile(r"\b(future|planned|proposed|potential)\s+(?:study|site|research)\b", re.I),
        re.compile(r"\b(recommend|suggest)\s+(?:studying|investigating)\b", re.I),
        re.compile(r"\b(?:could|should)\s+be\s+(?:studied|investigated|sampled)\b", re.I),
    ]

    # Uncertainty markers
    UNCERTAINTY_INDICATORS: ClassVar[list[re.Pattern[str]]] = [
        re.compile(r"\b(unclear|unknown|uncertain|undetermined)\b", re.I),
        re.compile(r"\b(needs?|requires?)\s+(?:further|more)\s+(?:study|research|investigation)\b", re.I),
    ]

    def __init__(self, default_multiplier: float = 1.0) -> None:
        """Initialize the uncertainty detector.

        Args:
            default_multiplier: Default confidence multiplier when no indicators found
        """
        self.default_multiplier = default_multiplier

    def assess_certainty(self, entity: GeoEntity) -> UncertaintyAssessment:
        """Assess certainty level for an entity.

        Args:
            entity: Entity to assess

        Returns:
            UncertaintyAssessment with certainty level and confidence adjustment
        """
        context = entity.context or ""

        # Check for each type of indicator
        confirmed_matches = self._find_matches(context, self.CONFIRMED_INDICATORS)
        likely_matches = self._find_matches(context, self.LIKELY_INDICATORS)
        tentative_matches = self._find_matches(context, self.TENTATIVE_INDICATORS)
        proposed_matches = self._find_matches(context, self.PROPOSED_INDICATORS)
        uncertain_matches = self._find_matches(context, self.UNCERTAINTY_INDICATORS)

        # Determine certainty level based on matches
        if uncertain_matches:
            return UncertaintyAssessment(
                certainty_level=CertaintyLevel.UNCERTAIN,
                confidence_multiplier=0.5,
                indicators=uncertain_matches,
            )

        if proposed_matches:
            return UncertaintyAssessment(
                certainty_level=CertaintyLevel.PROPOSED,
                confidence_multiplier=0.6,
                indicators=proposed_matches,
            )

        if confirmed_matches:
            # Strong confirmation
            multiplier = 1.1 if len(confirmed_matches) > 1 else 1.05
            return UncertaintyAssessment(
                certainty_level=CertaintyLevel.CONFIRMED,
                confidence_multiplier=multiplier,
                indicators=confirmed_matches,
            )

        if tentative_matches:
            return UncertaintyAssessment(
                certainty_level=CertaintyLevel.TENTATIVE,
                confidence_multiplier=0.8,
                indicators=tentative_matches,
            )

        if likely_matches:
            return UncertaintyAssessment(
                certainty_level=CertaintyLevel.LIKELY,
                confidence_multiplier=0.95,
                indicators=likely_matches,
            )

        # No indicators - return default
        return UncertaintyAssessment(
            certainty_level=CertaintyLevel.LIKELY,
            confidence_multiplier=self.default_multiplier,
            indicators=[],
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

    def adjust_entity_confidence(
        self,
        entities: list[GeoEntity],
    ) -> list[GeoEntity]:
        """Adjust entity confidence scores based on uncertainty assessment.

        Args:
            entities: List of entities

        Returns:
            List of entities with adjusted confidence scores
        """
        adjusted: list[GeoEntity] = []
        adjustment_count = 0

        for entity in entities:
            assessment = self.assess_certainty(entity)

            # Create new entity with adjusted confidence
            new_confidence = min(1.0, entity.confidence * assessment.confidence_multiplier)

            # Only create new entity if confidence changed
            if abs(new_confidence - entity.confidence) > 0.01:
                adjusted_entity = GeoEntity(
                    text=entity.text,
                    entity_type=entity.entity_type,
                    context=entity.context,
                    section=entity.section,
                    confidence=new_confidence,
                    start_char=entity.start_char,
                    end_char=entity.end_char,
                    coordinates=entity.coordinates,
                    bounding_box=entity.bounding_box,
                )
                adjusted.append(adjusted_entity)
                adjustment_count += 1

                logger.debug(
                    f"Adjusted confidence for '{entity.text[:30]}...' "
                    f"from {entity.confidence:.2f} to {new_confidence:.2f} "
                    f"({assessment.certainty_level.value})"
                )
            else:
                adjusted.append(entity)

        if adjustment_count > 0:
            logger.info(
                f"Uncertainty detection: adjusted confidence for {adjustment_count} entities"
            )

        return adjusted

    def filter_by_certainty(
        self,
        entities: list[GeoEntity],
        min_certainty: CertaintyLevel = CertaintyLevel.TENTATIVE,
    ) -> list[GeoEntity]:
        """Filter entities by minimum certainty level.

        Args:
            entities: List of entities
            min_certainty: Minimum certainty level to keep

        Returns:
            Filtered entities
        """
        certainty_order = {
            CertaintyLevel.CONFIRMED: 5,
            CertaintyLevel.LIKELY: 4,
            CertaintyLevel.TENTATIVE: 3,
            CertaintyLevel.PROPOSED: 2,
            CertaintyLevel.UNCERTAIN: 1,
        }

        min_level = certainty_order.get(min_certainty, 3)

        filtered: list[GeoEntity] = []
        removed_count = 0

        for entity in entities:
            assessment = self.assess_certainty(entity)
            entity_level = certainty_order.get(assessment.certainty_level, 3)

            if entity_level >= min_level:
                filtered.append(entity)
            else:
                removed_count += 1

        if removed_count > 0:
            logger.info(
                f"Certainty filtering: removed {removed_count} low-certainty entities"
            )

        return filtered


# Singleton instance
_detector: UncertaintyDetector | None = None


def get_uncertainty_detector() -> UncertaintyDetector:
    """Get the uncertainty detector instance."""
    global _detector
    if _detector is None:
        _detector = UncertaintyDetector()
    return _detector
