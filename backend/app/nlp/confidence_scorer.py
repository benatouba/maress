"""Enhanced confidence scoring for study site detection.

Provides context-aware, linguistic-feature-based confidence scoring
that improves upon simple rule-based approaches.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.nlp.domain_models import GeoEntity

if TYPE_CHECKING:
    from spacy.tokens import Doc, Span


class ConfidenceScorer:
    """Enhanced confidence scorer using linguistic features and context.

    Scores entities based on:
    1. Section relevance
    2. Syntactic role
    3. Contextual keywords
    4. Entity type
    5. Dependency patterns
    """

    # Section multipliers (enhanced from orchestrator)
    SECTION_MULTIPLIERS = {
        # High confidence sections
        "study area": 2.5,
        "study site": 2.5,
        "study sites": 2.5,
        "study_area": 2.5,
        "study_site": 2.5,
        "data and methods": 2.0,
        "materials and methods": 2.0,
        "methods": 2.0,
        "materials": 1.8,
        "data collection": 2.0,
        "field methods": 2.2,
        "site description": 2.3,

        # Medium confidence sections
        "results": 1.3,
        "abstract": 1.2,
        "figure": 1.5,
        "caption": 1.4,
        "table": 1.3,

        # Lower confidence sections
        "introduction": 0.8,
        "background": 0.7,
        "discussion": 0.7,
        "conclusion": 0.6,
        "conclusions": 0.6,

        # Very low confidence
        "references": 0.1,
        "bibliography": 0.1,
        "acknowledgments": 0.2,
        "acknowledgements": 0.2,
    }

    # Positive context keywords (boosting)
    TIER1_KEYWORDS = {
        # Very high confidence (0.7 boost)
        "study site", "study area", "study location", "our study site",
        "our study area", "study sites were", "study area was",
        "sites were located", "area was located", "research site",
        "sampling site", "field site", "collection site",
        "data collection site", "study was conducted",
    }

    TIER2_KEYWORDS = {
        # High confidence (0.5 boost)
        "sampling location", "sampling station", "sample site",
        "sample location", "sample collection", "samples were collected",
        "field station", "research station", "research area",
        "experimental site", "observation site", "monitoring site",
        "monitoring station", "collected at", "measurement site",
        "survey site", "our site", "our sites", "our location",
    }

    TIER3_KEYWORDS = {
        # Medium confidence (0.3 boost)
        "plot", "transect", "quadrat", "study region",
        "sites", "location", "locations", "station", "stations",
        "site", "area", "region", "conducted", "performed",
        "established", "located", "situated",
    }

    # Negative context keywords (penalties)
    CITATION_KEYWORDS = {
        # Heavy penalty (-0.5)
        "et al", "et al.", "cited", "reported", "described by",
        "according to", "previous study", "earlier work",
        "prior study", "literature", "published", "similar to",
        "compared to", "following", "referenced",
    }

    INSTITUTION_KEYWORDS = {
        # Penalty for institutional affiliations (-0.4)
        "author", "affiliation", "department", "university",
        "address", "correspondence", "laboratory", "institute",
        "institution", "research center", "research centre",
        "funded by", "supported by", "grant",
    }

    # Syntactic role boosters
    SYNTACTIC_BOOSTERS = {
        "pobj": 1.2,  # Object of preposition (e.g., "at California")
        "dobj": 1.2,  # Direct object (e.g., "visited California")
        "nsubj": 1.1,  # Subject (e.g., "California was studied")
        "appos": 1.3,  # Apposition (e.g., "our site, California,")
    }

    def __init__(self) -> None:
        """Initialize the confidence scorer."""
        pass

    def score_entity(
        self,
        entity: GeoEntity,
        doc: Doc | None = None,
        entity_span: Span | None = None,
    ) -> float:
        """Calculate enhanced confidence score for an entity.

        Args:
            entity: GeoEntity to score
            doc: spaCy Doc (optional, for linguistic features)
            entity_span: spaCy Span corresponding to entity (optional)

        Returns:
            Enhanced confidence score (0.0 to 1.0+)
        """
        # Start with base confidence
        score = entity.confidence

        # Apply section multiplier
        section_multiplier = self._get_section_multiplier(entity.section)
        score *= section_multiplier

        # Apply context-based adjustments
        context_adjustment = self._score_context(entity.context)
        score += context_adjustment

        # Apply syntactic role boost (if span available)
        if entity_span is not None:
            syntactic_boost = self._score_syntactic_role(entity_span)
            score *= syntactic_boost

        # Apply entity type adjustments
        type_boost = self._score_entity_type(entity.entity_type)
        score *= type_boost

        # Apply special boosts for specific patterns
        if hasattr(entity_span, "_") and hasattr(entity_span._, "dependency_pattern"):
            score *= 1.3  # Boost for dependency pattern matches

        if hasattr(entity_span, "_") and hasattr(entity_span._, "is_multiword_location"):
            if entity_span._.is_multiword_location:
                score *= 1.2  # Boost for known multi-word locations

        # Ensure score is in valid range (0.0 to 1.0 as per GeoEntity validation)
        return min(max(score, 0.0), 1.0)

    def _get_section_multiplier(self, section: str) -> float:
        """Get confidence multiplier based on document section.

        Args:
            section: Section name

        Returns:
            Multiplier (0.1 to 2.5)
        """
        section_lower = section.lower().strip()

        # Exact match
        if section_lower in self.SECTION_MULTIPLIERS:
            return self.SECTION_MULTIPLIERS[section_lower]

        # Partial match for flexibility
        for key, multiplier in self.SECTION_MULTIPLIERS.items():
            if key in section_lower or section_lower in key:
                return multiplier

        # Default multiplier
        return 1.0

    def _score_context(self, context: str) -> float:
        """Score based on context keywords.

        Args:
            context: Entity context string

        Returns:
            Adjustment score (-0.5 to +0.7)
        """
        context_lower = context.lower()
        adjustment = 0.0

        # Check for positive keywords (only apply highest tier)
        for keyword in self.TIER1_KEYWORDS:
            if keyword in context_lower:
                adjustment = max(adjustment, 0.7)
                break

        if adjustment == 0.0:  # No tier 1 match
            for keyword in self.TIER2_KEYWORDS:
                if keyword in context_lower:
                    adjustment = max(adjustment, 0.5)
                    break

        if adjustment == 0.0:  # No tier 1 or 2 match
            for keyword in self.TIER3_KEYWORDS:
                if keyword in context_lower:
                    adjustment = max(adjustment, 0.3)
                    break

        # Check for negative keywords (apply penalties)
        for keyword in self.CITATION_KEYWORDS:
            if keyword in context_lower:
                adjustment -= 0.5
                break  # Only apply once

        for keyword in self.INSTITUTION_KEYWORDS:
            if keyword in context_lower:
                adjustment -= 0.4
                break

        return adjustment

    def _score_syntactic_role(self, span: Span) -> float:
        """Score based on syntactic dependency role.

        Args:
            span: spaCy Span

        Returns:
            Multiplier (0.8 to 1.3)
        """
        # Get the root token's dependency
        root = span.root
        dep = root.dep_

        return self.SYNTACTIC_BOOSTERS.get(dep, 1.0)

    def _score_entity_type(self, entity_type: str) -> float:
        """Score based on entity type.

        Args:
            entity_type: Entity type string

        Returns:
            Multiplier (0.8 to 1.5)
        """
        type_multipliers = {
            "COORDINATE": 1.5,  # Highest - explicit coordinates
            "STUDY_SITE": 1.4,  # Very high - identified by dependency patterns
            "MULTIWORD_LOCATION": 1.3,  # High - known complex locations
            "SPATIAL_RELATION": 1.2,  # Good - spatial context
            "GPE": 1.1,  # Good - specific places
            "FAC": 1.1,  # Good - facilities
            "LOC": 1.0,  # Medium - general locations
            "CONTEXTUAL_LOCATION": 0.9,  # Lower - need more validation
        }

        return type_multipliers.get(entity_type, 1.0)

    def score_and_rank_entities(
        self,
        entities: list[GeoEntity],
        doc: Doc | None = None,
    ) -> list[tuple[GeoEntity, float]]:
        """Score and rank a list of entities.

        Args:
            entities: List of GeoEntity objects
            doc: spaCy Doc (optional)

        Returns:
            List of (entity, score) tuples, sorted by score (highest first)
        """
        scored = []

        for entity in entities:
            # Find corresponding span in doc if available
            entity_span = None
            if doc is not None:
                for ent in doc.ents:
                    if (ent.start_char == entity.start_char and
                        ent.end_char == entity.end_char):
                        entity_span = ent
                        break

            score = self.score_entity(entity, doc, entity_span)
            scored.append((entity, score))

        # Sort by score (highest first)
        return sorted(scored, key=lambda x: x[1], reverse=True)


def apply_enhanced_scoring(entities: list[GeoEntity], doc: Doc | None = None) -> list[GeoEntity]:
    """Apply enhanced confidence scoring to entities and return updated list.

    Args:
        entities: List of GeoEntity objects
        doc: spaCy Doc (optional)

    Returns:
        List of GeoEntity objects with updated confidence scores
    """
    scorer = ConfidenceScorer()

    updated_entities = []
    for entity in entities:
        # Find corresponding span
        entity_span = None
        if doc is not None:
            for ent in doc.ents:
                if (ent.start_char == entity.start_char and
                    ent.end_char == entity.end_char):
                    entity_span = ent
                    break

        # Calculate new score
        new_score = scorer.score_entity(entity, doc, entity_span)

        # Create updated entity with new confidence
        updated_entity = GeoEntity(
            text=entity.text,
            entity_type=entity.entity_type,
            context=entity.context,
            section=entity.section,
            confidence=new_score,
            start_char=entity.start_char,
            end_char=entity.end_char,
            coordinates=entity.coordinates,
        )
        updated_entities.append(updated_entity)

    return updated_entities
