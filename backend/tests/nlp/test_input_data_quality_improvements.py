"""Tests for Phase 2 NLP improvements (Quick Wins).

Tests for:
1. Text Quality Assessment
2. Sentence Boundary Improvements
3. Enriched Context Extraction
"""

from __future__ import annotations

import pytest
import spacy

from app.nlp.context_extraction import ContextExtractor, EnrichedContext
from app.nlp.quality_assessment import QualityScore, TextQualityAssessor
from app.nlp.sentence_boundaries import improve_sentence_boundaries


class TestTextQualityAssessment:
    """Test text quality scoring."""

    def test_high_quality_text(self):
        """Test that high-quality scientific text scores well."""
        assessor = TextQualityAssessor()

        good_text = """
        Study sites were located in Ecuador at coordinates 45.5°N, 122.3°W.
        The research area encompassed three distinct ecological zones with
        varying elevation gradients. Data collection occurred from January
        to December 2020 using standardized protocols.
        """

        score = assessor.assess_quality(good_text)

        assert isinstance(score, QualityScore)
        assert score.overall_score > 0.7, "High quality text should score > 0.7"
        assert score.char_ratio > 0.8, "Should have high alphanumeric ratio"
        assert score.encoding_health > 0.9, "Should have no encoding issues"

    def test_low_quality_fragmented_text(self):
        """Test that fragmented text scores poorly."""
        assessor = TextQualityAssessor()

        # Simulated OCR garbage
        bad_text = "S t u d y   s i t e s   w e r e   l o c a t e d"

        score = assessor.assess_quality(bad_text)

        assert score.overall_score < 0.6, "Fragmented text should score poorly"
        assert score.line_fragmentation < 0.5, "Should detect fragmentation"

    def test_encoding_corruption_detection(self):
        """Test detection of mojibake and encoding issues."""
        assessor = TextQualityAssessor()

        # Text with UTF-8 mojibake
        mojibake_text = """
        Study sites were located in SÃ£o Paulo at coordinates 45Â°30â€²N.
        The research area encompassed â€œthree distinct ecological zonesâ€.
        """

        score = assessor.assess_quality(mojibake_text)

        assert score.encoding_health < 0.9, "Should detect encoding corruption"
        assert score.overall_score < 0.8, "Mojibake should lower overall score"

    def test_empty_text(self):
        """Test handling of empty text."""
        assessor = TextQualityAssessor()

        score = assessor.assess_quality("")

        assert score.overall_score == 0.0
        assert score.char_ratio == 0.0

    def test_assess_section_quality(self):
        """Test quality assessment for multiple sections."""
        assessor = TextQualityAssessor()

        sections = {
            "methods": "Study sites were located at 45.5°N. Sampling occurred monthly.",
            "results": "We found significant differences between sites (p < 0.05).",
            "corrupted": "S t u d y   s i t e s",
        }

        quality_scores = assessor.assess_section_quality(sections)

        assert len(quality_scores) == 3
        assert "methods" in quality_scores
        assert "results" in quality_scores
        assert "corrupted" in quality_scores

        # Methods and results should be good quality
        assert quality_scores["methods"].overall_score > 0.7
        assert quality_scores["results"].overall_score > 0.7

        # Corrupted section should be poor quality
        assert quality_scores["corrupted"].overall_score < 0.6

    def test_should_process_text(self):
        """Test decision to process text based on quality."""
        assessor = TextQualityAssessor()

        good_text = "Study sites were located in Ecuador at 45.5°N, 122.3°W."
        bad_text = "S t u d y"

        should_process_good, score_good = assessor.should_process_text(
            good_text, min_quality=0.5
        )
        should_process_bad, score_bad = assessor.should_process_text(bad_text, min_quality=0.5)

        assert should_process_good is True
        assert score_good.overall_score >= 0.5

        assert should_process_bad is False
        assert score_bad.overall_score < 0.5


class TestSentenceBoundaryImprovements:
    """Test improved sentence boundary detection."""

    @pytest.fixture
    def nlp(self):
        """Create spaCy model with improved sentence boundaries."""
        nlp = spacy.load("en_core_web_sm")
        return improve_sentence_boundaries(nlp)

    def test_et_al_not_split(self, nlp):
        """Test that 'et al.' doesn't cause sentence split."""
        text = "Study by Smith et al. The coordinates were recorded."

        doc = nlp(text)
        sentences = list(doc.sents)

        # Should be 2 sentences, not 3
        assert len(sentences) == 2
        assert "Smith et al." in sentences[0].text
        assert "The coordinates were recorded" in sentences[1].text

    def test_list_numbering_not_split(self, nlp):
        """Test that list numbering doesn't cause incorrect splits."""
        text = "Sites were: (1) Ecuador, (2) Peru, (3) Chile. Data was collected."

        doc = nlp(text)
        sentences = list(doc.sents)

        # Should be 2 sentences
        assert len(sentences) == 2
        # First sentence should contain all list items
        assert "(1)" in sentences[0].text
        assert "(2)" in sentences[0].text
        assert "(3)" in sentences[0].text

    def test_coordinate_comma_not_split(self, nlp):
        """Test that commas in coordinates don't split sentences."""
        text = "Location at 45°30'N, 122°30'W. The site was established."

        doc = nlp(text)
        sentences = list(doc.sents)

        # Should be 2 sentences
        assert len(sentences) == 2
        # Coordinate should be in first sentence
        assert "45°30'N, 122°30'W" in sentences[0].text

    def test_figure_references_not_split(self, nlp):
        """Test that figure references don't cause splits."""
        text = "As shown in Fig. 1A. The pattern is clear."

        doc = nlp(text)
        sentences = list(doc.sents)

        # Should be 2 sentences
        assert len(sentences) == 2
        assert "Fig. 1A" in sentences[0].text

    def test_months_not_split(self, nlp):
        """Test that month abbreviations don't cause splits."""
        text = "Sampling from Jan. 2020 to Dec. 2020 was conducted."

        doc = nlp(text)
        sentences = list(doc.sents)

        # Should be 1 sentence
        assert len(sentences) == 1
        assert "Jan. 2020" in sentences[0].text
        assert "Dec. 2020" in sentences[0].text

    def test_scientific_abbreviations(self, nlp):
        """Test that common scientific abbreviations are handled."""
        text = "Temperature was approx. 25°C. The e.g. measurements were accurate."

        doc = nlp(text)
        sentences = list(doc.sents)

        # Should be 2 sentences
        assert len(sentences) == 2
        assert "approx. 25°C" in sentences[0].text
        assert "e.g. measurements" in sentences[1].text


class TestEnrichedContextExtraction:
    """Test enriched context extraction."""

    @pytest.fixture
    def nlp(self):
        """Create spaCy model."""
        return spacy.load("en_core_web_sm")

    @pytest.fixture
    def extractor(self):
        """Create context extractor."""
        return ContextExtractor(context_window=50, max_paragraph_chars=500)

    def test_extract_basic_context(self, nlp, extractor):
        """Test extraction of basic context."""
        text = """
        Study sites were established in Ecuador at coordinates 45.5°N, 122.3°W.
        The research area encompassed three distinct ecological zones.
        """

        doc = nlp(text)

        # Manually create a span for the coordinate
        # (in real use, this would come from coordinate extraction)
        coord_start = text.find("45.5°N")
        coord_end = text.find("122.3°W") + len("122.3°W")

        # Find the span in the doc
        coord_span = None
        for token in doc:
            if token.idx >= coord_start and token.idx + len(token.text) <= coord_end:
                # Found start of coordinate, create span
                start_token = token.i
                end_token = start_token + 5  # Approximate
                coord_span = doc[start_token:end_token]
                break

        if coord_span is not None:
            context = extractor.extract_context(doc, coord_span, section="methods")

            assert isinstance(context, EnrichedContext)
            assert context.section == "methods"
            assert len(context.sentence) > 0
            assert len(context.paragraph) > 0
            assert context.context_quality > 0

    def test_extract_geographic_keywords(self, nlp, extractor):
        """Test extraction of geographic keywords."""
        text = """
        Study sites and sampling locations were established in Ecuador.
        The research area included multiple field stations and plots.
        """

        doc = nlp(text)

        # Get first entity span
        if doc.ents:
            entity_span = doc.ents[0]
            context = extractor.extract_context(doc, entity_span, section="methods")

            # Should find geographic keywords
            assert len(context.geographic_keywords) > 0
            # Should find terms like "sites", "sampling", "locations", "area", etc.
            assert any(kw in ["site", "sites", "sampling", "location", "locations", "area", "field", "station", "stations", "plot", "plots"] for kw in context.geographic_keywords)

    def test_extract_nearby_entities(self, nlp, extractor):
        """Test extraction of nearby entities."""
        text = """
        Study sites were established in Ecuador and Peru at coordinates 45.5°N, 122.3°W.
        The research spanned from Lima to Quito.
        """

        doc = nlp(text)

        # Find Ecuador entity
        ecuador_span = None
        for ent in doc.ents:
            if "Ecuador" in ent.text:
                ecuador_span = ent
                break

        if ecuador_span is not None:
            context = extractor.extract_context(doc, ecuador_span, section="methods")

            # Should have entities before and/or after
            total_entities = len(context.preceding_entities) + len(context.following_entities)
            assert total_entities > 0

    def test_find_figure_reference(self, nlp, extractor):
        """Test finding figure references in context."""
        text = """
        As shown in Figure 2, the study sites were distributed across elevation gradients.
        """

        doc = nlp(text)

        if doc.ents:
            context = extractor.extract_context(doc, doc.ents[0], section="results")

            # Should find figure reference
            assert context.figure_reference is not None
            assert "Figure 2" in context.figure_reference or "Fig" in context.figure_reference

    def test_context_quality_assessment(self, nlp, extractor):
        """Test context quality scoring."""
        # Good context
        good_text = """
        Study sites and sampling locations were established in Ecuador at coordinates 45.5°N, 122.3°W.
        The research area encompassed three distinct ecological zones located in the Andes mountains.
        """

        # Poor context (short)
        poor_text = "Ecuador site."

        doc_good = nlp(good_text)
        doc_poor = nlp(poor_text)

        if doc_good.ents:
            context_good = extractor.extract_context(doc_good, doc_good.ents[0], section="methods")
            assert context_good.context_quality > 0.5

        if doc_poor.ents:
            context_poor = extractor.extract_context(doc_poor, doc_poor.ents[0], section="methods")
            # Poor context should have lower quality
            assert context_poor.context_quality < context_good.context_quality


class TestIntegration:
    """Integration tests for Phase 2 improvements."""

    def test_quality_and_sentences_together(self):
        """Test that quality assessment works with improved sentences."""
        nlp = spacy.load("en_core_web_sm")
        nlp = improve_sentence_boundaries(nlp)

        assessor = TextQualityAssessor()

        text = "Study by Smith et al. conducted in Ecuador. Sites at 45°N, 122°W."

        doc = nlp(text)
        sentences = list(doc.sents)

        # Sentences should be correct
        assert len(sentences) >= 2

        # Quality should be good
        score = assessor.assess_quality(text)
        assert score.overall_score > 0.7

    def test_all_components_available(self):
        """Test that all Phase 2 components can be imported."""
        from app.nlp.context_extraction import ContextExtractor, EnrichedContext
        from app.nlp.quality_assessment import QualityScore, TextQualityAssessor
        from app.nlp.sentence_boundaries import (
            improve_sentence_boundaries,
            scientific_sentencizer,
        )

        assert ContextExtractor is not None
        assert EnrichedContext is not None
        assert TextQualityAssessor is not None
        assert QualityScore is not None
        assert improve_sentence_boundaries is not None
        assert scientific_sentencizer is not None
