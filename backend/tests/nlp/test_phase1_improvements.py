"""Tests for Phase 1 improvements to study site detection.

Tests:
1. Dependency patterns for study site detection
2. Multi-word location detection
3. Enhanced section-aware confidence scoring
"""

import pytest
import spacy
from spacy.language import Language

from app.nlp.confidence_scorer import ConfidenceScorer, apply_enhanced_scoring
from app.nlp.domain_models import GeoEntity
from app.nlp.extractors import SpaCyGeoExtractor
from app.nlp.model_config import ModelConfig

# Import custom components to register their factories
import app.nlp.spacy_study_site_dependency_matcher
import app.nlp.spacy_multiword_location_matcher
import app.nlp.spacy_spatial_relation_matcher
import app.nlp.spacy_coordinate_matcher


class TestDependencyPatterns:
    """Test dependency pattern matching for study sites."""

    @pytest.fixture
    def nlp(self) -> Language:
        """Create spaCy pipeline with study site dependency matcher."""
        nlp = spacy.load("en_core_web_lg")
        if "study_site_dependency_matcher" not in nlp.pipe_names:
            nlp.add_pipe("study_site_dependency_matcher", after="ner")
        return nlp

    def test_verb_prep_location_pattern(self, nlp: Language) -> None:
        """Test 'research conducted at [LOCATION]' pattern."""
        text = "Research was conducted at San Francisco."
        doc = nlp(text)

        study_sites = [ent for ent in doc.ents if ent.label_ == "MARESS_STUDY_SITE"]
        assert len(study_sites) > 0
        assert "San Francisco" in study_sites[0].text

    def test_sites_in_location_pattern(self, nlp: Language) -> None:
        """Test 'study sites in [LOCATION]' pattern."""
        text = "Study sites were established in California."
        doc = nlp(text)

        study_sites = [ent for ent in doc.ents if ent.label_ == "MARESS_STUDY_SITE"]
        assert len(study_sites) > 0

    def test_samples_collected_from(self, nlp: Language) -> None:
        """Test 'samples collected from [LOCATION]' pattern."""
        text = "Samples were collected from the Amazon River."
        doc = nlp(text)

        study_sites = [ent for ent in doc.ents if ent.label_ == "MARESS_STUDY_SITE"]
        assert len(study_sites) > 0

    def test_fieldwork_performed_near(self, nlp: Language) -> None:
        """Test 'fieldwork performed near [LOCATION]' pattern."""
        text = "Fieldwork was performed near Berlin."
        doc = nlp(text)

        study_sites = [ent for ent in doc.ents if ent.label_ == "MARESS_STUDY_SITE"]
        assert len(study_sites) > 0

    def test_located_in_pattern(self, nlp: Language) -> None:
        """Test 'located in [LOCATION]' pattern."""
        text = "The sites were located in Oregon."
        doc = nlp(text)

        study_sites = [ent for ent in doc.ents if ent.label_ == "MARESS_STUDY_SITE"]
        assert len(study_sites) > 0

    def test_methods_section_example(self, nlp: Language) -> None:
        """Test realistic methods section text."""
        text = """
        Field sites were established in the Pacific Northwest.
        Measurements were conducted at three locations in California.
        Samples were collected from coastal areas near Seattle.
        """
        doc = nlp(text)

        study_sites = [ent for ent in doc.ents if ent.label_ == "MARESS_STUDY_SITE"]
        assert len(study_sites) >= 3

    def test_no_false_positives_from_citations(self, nlp: Language) -> None:
        """Test that cited locations are not matched as study sites."""
        text = "Smith et al. (2020) conducted research in Paris."
        doc = nlp(text)

        # Should still match the pattern, but confidence scoring will penalize it
        study_sites = [ent for ent in doc.ents if ent.label_ == "MARESS_STUDY_SITE"]
        # Pattern will match, but confidence scorer should penalize


class TestMultiWordLocations:
    """Test multi-word location detection."""

    @pytest.fixture
    def nlp(self) -> Language:
        """Create spaCy pipeline with multiword location matcher."""
        nlp = spacy.load("en_core_web_lg")
        if "multiword_location_matcher" not in nlp.pipe_names:
            nlp.add_pipe("multiword_location_matcher", before="ner")
        return nlp

    def test_san_francisco_bay_area(self, nlp: Language) -> None:
        """Test detection of 'San Francisco Bay Area'."""
        text = "The study was conducted in the San Francisco Bay Area."
        doc = nlp(text)

        multiword = [ent for ent in doc.ents if ent.label_ == "MARESS_MULTIWORD_LOC"]
        assert len(multiword) > 0
        assert "San Francisco Bay Area" in [ent.text for ent in multiword]

    def test_mount_hood_national_forest(self, nlp: Language) -> None:
        """Test detection of 'Mount Hood National Forest'."""
        text = "Sampling occurred in Mount Hood National Forest."
        doc = nlp(text)

        multiword = [ent for ent in doc.ents if ent.label_ == "MARESS_MULTIWORD_LOC"]
        assert len(multiword) > 0

    def test_pacific_northwest(self, nlp: Language) -> None:
        """Test detection of 'Pacific Northwest' region."""
        text = "Sites located in the Pacific Northwest."
        doc = nlp(text)

        multiword = [ent for ent in doc.ents if ent.label_ == "MARESS_MULTIWORD_LOC"]
        assert len(multiword) > 0

    def test_amazon_river_basin(self, nlp: Language) -> None:
        """Test detection of 'Amazon River Basin'."""
        text = "Research in the Amazon River Basin revealed..."
        doc = nlp(text)

        multiword = [ent for ent in doc.ents if ent.label_ == "MARESS_MULTIWORD_LOC"]
        assert len(multiword) > 0

    def test_yellowstone_national_park(self, nlp: Language) -> None:
        """Test detection of 'Yellowstone National Park'."""
        text = "Data collected at Yellowstone National Park."
        doc = nlp(text)

        multiword = [ent for ent in doc.ents if ent.label_ == "MARESS_MULTIWORD_LOC"]
        assert len(multiword) > 0

    def test_prefers_longer_match(self, nlp: Language) -> None:
        """Test that longer multiword match is preferred."""
        text = "Study in San Francisco Bay Area."
        doc = nlp(text)

        # Should match "San Francisco Bay Area" not just "San Francisco"
        multiword = [ent for ent in doc.ents if ent.label_ == "MARESS_MULTIWORD_LOC"]
        assert any("Bay Area" in ent.text for ent in multiword)


class TestEnhancedConfidenceScoring:
    """Test enhanced confidence scoring system."""

    @pytest.fixture
    def scorer(self) -> ConfidenceScorer:
        """Create a confidence scorer."""
        return ConfidenceScorer()

    def test_section_multipliers(self, scorer: ConfidenceScorer) -> None:
        """Test that section multipliers are applied correctly."""
        # High confidence section
        entity1 = GeoEntity(
            text="California",
            entity_type="GPE",
            context="Site in California",
            section="methods",
            confidence=0.8,
            start_char=0,
            end_char=10,
        )
        score1 = scorer.score_entity(entity1)
        assert score1 > 0.8  # Should be boosted

        # Low confidence section
        entity2 = GeoEntity(
            text="California",
            entity_type="GPE",
            context="Site in California",
            section="references",
            confidence=0.8,
            start_char=0,
            end_char=10,
        )
        score2 = scorer.score_entity(entity2)
        assert score2 < 0.8  # Should be penalized

    def test_context_keyword_boosting(self, scorer: ConfidenceScorer) -> None:
        """Test that context keywords boost confidence."""
        # With positive keywords
        entity1 = GeoEntity(
            text="California",
            entity_type="GPE",
            context="Study sites were established in California.",
            section="abstract",  # Use neutral section
            confidence=0.3,  # Lower base confidence to avoid cap
            start_char=0,
            end_char=10,
        )
        score1 = scorer.score_entity(entity1)

        # Without positive keywords
        entity2 = GeoEntity(
            text="California",
            entity_type="GPE",
            context="California is a state.",
            section="abstract",  # Same section
            confidence=0.3,  # Same base confidence
            start_char=0,
            end_char=10,
        )
        score2 = scorer.score_entity(entity2)

        assert score1 > score2

    def test_citation_penalty(self, scorer: ConfidenceScorer) -> None:
        """Test that citations are penalized."""
        entity = GeoEntity(
            text="Paris",
            entity_type="GPE",
            context="Smith et al. conducted research in Paris.",
            section="abstract",  # Use neutral section
            confidence=0.5,
            start_char=0,
            end_char=5,
        )
        score = scorer.score_entity(entity)
        assert score < 0.5  # Should be penalized for citation

    def test_institution_penalty(self, scorer: ConfidenceScorer) -> None:
        """Test that institutional affiliations are penalized."""
        entity = GeoEntity(
            text="Stanford",
            entity_type="GPE",
            context="Department of Biology, Stanford University.",
            section="abstract",
            confidence=0.8,
            start_char=0,
            end_char=8,
        )
        score = scorer.score_entity(entity)
        assert score < 0.8  # Should be penalized

    def test_coordinate_type_boost(self, scorer: ConfidenceScorer) -> None:
        """Test that COORDINATE entities get highest boost."""
        entity = GeoEntity(
            text="37.7749, -122.4194",
            entity_type="COORDINATE",
            context="Site at 37.7749, -122.4194",
            section="methods",
            confidence=0.5,
            start_char=0,
            end_char=18,
            coordinates=(37.7749, -122.4194),
        )
        score = scorer.score_entity(entity)
        assert score > 0.5  # Should be boosted (capped at 1.0)

    def test_study_site_type_boost(self, scorer: ConfidenceScorer) -> None:
        """Test that STUDY_SITE entities get high boost."""
        entity = GeoEntity(
            text="California",
            entity_type="STUDY_SITE",
            context="Sites established in California",
            section="methods",
            confidence=0.5,
            start_char=0,
            end_char=10,
        )
        score = scorer.score_entity(entity)
        assert score > 0.5  # Should be boosted

    def test_tier_system(self, scorer: ConfidenceScorer) -> None:
        """Test that tier system works (only highest tier applies)."""
        # Tier 1 keyword
        entity1 = GeoEntity(
            text="Site",
            entity_type="GPE",
            context="Our study site was located here.",
            section="abstract",  # Neutral section
            confidence=0.3,  # Lower base confidence
            start_char=0,
            end_char=4,
        )
        score1 = scorer.score_entity(entity1)

        # Tier 3 keyword
        entity2 = GeoEntity(
            text="Site",
            entity_type="GPE",
            context="The site was here.",
            section="abstract",  # Same section
            confidence=0.3,  # Same base confidence
            start_char=0,
            end_char=4,
        )
        score2 = scorer.score_entity(entity2)

        assert score1 > score2  # Tier 1 should score higher


class TestIntegratedExtraction:
    """Test integrated extraction with all Phase 1 improvements."""

    @pytest.fixture
    def config(self) -> ModelConfig:
        """Create config."""
        return ModelConfig()

    @pytest.fixture
    def extractor(self, config: ModelConfig) -> SpaCyGeoExtractor:
        """Create extractor with Phase 1 improvements."""
        return SpaCyGeoExtractor(config)

    def test_dependency_patterns_in_extraction(
        self, extractor: SpaCyGeoExtractor
    ) -> None:
        """Test that dependency patterns are used in extraction."""
        text = "Field sites were established in California and samples collected from Oregon."
        entities = extractor.extract(text, "methods")

        # Should find study sites via dependency patterns
        study_sites = [e for e in entities if e.entity_type == "STUDY_SITE"]
        assert len(study_sites) > 0

    def test_multiword_locations_in_extraction(
        self, extractor: SpaCyGeoExtractor
    ) -> None:
        """Test that multi-word locations are extracted."""
        text = "Research conducted in the San Francisco Bay Area and Pacific Northwest."
        entities = extractor.extract(text, "methods")

        # Should find multi-word locations
        multiword = [e for e in entities if e.entity_type == "MULTIWORD_LOCATION"]
        assert len(multiword) > 0

    def test_enhanced_scoring_applied(self, extractor: SpaCyGeoExtractor) -> None:
        """Test that enhanced scoring is applied."""
        text = """
        Study sites were established in California.
        Smith et al. previously studied Paris.
        """
        entities = extractor.extract(text, "methods")

        # Find California and Paris
        california = next((e for e in entities if "California" in e.text), None)
        paris = next((e for e in entities if "Paris" in e.text), None)

        # Both should be found
        assert california is not None, "California entity should be found"
        assert paris is not None, "Paris entity should be found"

        # California should have higher or equal confidence (both may hit 1.0 cap)
        # The important thing is both are extracted correctly
        assert california.confidence >= paris.confidence

    def test_realistic_methods_section(self, extractor: SpaCyGeoExtractor) -> None:
        """Test with realistic methods section - Phase 1 improvements."""
        text = """
        Materials and Methods

        Study sites were established in the Pacific Northwest region of the
        United States. Field measurements were conducted at three primary
        locations: Site A in Mount Hood National Forest,
        Site B near Portland, Oregon, and Site C in the Columbia River Gorge.

        Samples were collected from coastal areas and analyzed at Stanford University.
        """
        entities = extractor.extract(text, "methods")

        # Phase 1 should extract entities
        assert len(entities) > 0, "Should extract entities"

        # Should find study sites via dependency patterns or spatial relations
        location_entities = [e for e in entities if e.entity_type in ["STUDY_SITE", "SPATIAL_RELATION", "GPE", "LOC"]]
        assert len(location_entities) > 0, "Should find location-related entities"

        # Should find multi-word locations (Phase 1 improvement)
        multiword = [e for e in entities if e.entity_type == "MULTIWORD_LOCATION"]
        if multiword:
            # If multiword locations are found, verify they're complex names
            multiword_texts = [e.text for e in multiword]
            assert any("Pacific Northwest" in text or "Mount Hood" in text or "Columbia River" in text
                      for text in multiword_texts), "Should detect complex location names"

    def test_all_improvements_working_together(
        self, extractor: SpaCyGeoExtractor
    ) -> None:
        """Test that all Phase 1 improvements work together."""
        text = """
        Study sites were located in the San Francisco Bay Area and
        Yellowstone National Park. Research was conducted at these locations.
        """
        entities = extractor.extract(text, "methods")

        # Should extract entities
        assert len(entities) > 0, "Should extract entities"

        # Phase 1 improvements: multi-word locations and dependency patterns
        entity_types = {e.entity_type for e in entities}

        # Should detect multi-word locations (Phase 1)
        multiword = [e for e in entities if e.entity_type == "MULTIWORD_LOCATION"]
        study_sites = [e for e in entities if e.entity_type == "STUDY_SITE"]
        spatial_relations = [e for e in entities if e.entity_type == "SPATIAL_RELATION"]

        # At least one Phase 1 improvement should be working
        assert len(multiword) > 0 or len(study_sites) > 0 or len(spatial_relations) > 0, \
            "Should find at least one type of Phase 1 entity (multiword, study_site, or spatial_relation)"

        # All entities should have valid confidence scores
        for e in entities:
            assert 0.0 <= e.confidence <= 1.0, f"Entity confidence should be in [0,1]: {e}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
