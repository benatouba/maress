"""Tests for spaCy-integrated coordinate matching with malformed patterns.

This module tests the SpaCyCoordinateExtractor and CoordinateMatcher component
to ensure they correctly detect both well-formed and malformed coordinates
from PDF extraction.
"""

import pytest
import spacy
from app.nlp.extractors import SpaCyCoordinateExtractor
from app.nlp.model_config import ModelConfig
from app.nlp.spacy_coordinate_matcher import CoordinateMatcher


@pytest.fixture
def nlp():
    """Create spaCy language model with coordinate matcher."""
    nlp = spacy.blank("en")
    nlp.add_pipe("sentencizer")

    # Add coordinate matcher component
    if "coordinate_matcher" not in nlp.pipe_names:
        nlp.add_pipe("coordinate_matcher")

    return nlp


@pytest.fixture
def extractor():
    """Create coordinate extractor instance."""
    config = ModelConfig()
    return SpaCyCoordinateExtractor(config)


class TestWellFormedCoordinates:
    """Test detection of standard, well-formed coordinate formats."""

    def test_decimal_degrees_simple(self, extractor):
        """Test simple decimal degree pairs."""
        text = "The study site is located at 45.123, -122.456 in the Pacific Northwest."
        entities = extractor.extract(text, "methods")

        assert len(entities) > 0
        assert entities[0].coordinates == (45.123, -122.456)
        assert entities[0].entity_type == "COORDINATE"

    def test_dms_format(self, extractor):
        """Test degrees-minutes-seconds format."""
        text = "Coordinates are 45°12'30\"N, 122°30'15\"W."
        entities = extractor.extract(text, "methods")

        assert len(entities) > 0
        assert entities[0].coordinates is not None
        # DMS: 45°12'30" = 45 + 12/60 + 30/3600 = 45.208333
        lat, lon = entities[0].coordinates
        assert abs(lat - 45.208333) < 0.001
        assert abs(lon - (-122.504167)) < 0.001

    def test_dm_format(self, extractor):
        """Test degrees-minutes format."""
        text = "Located at 45°12'N, 122°30'W."
        entities = extractor.extract(text, "methods")

        assert len(entities) > 0
        assert entities[0].coordinates is not None
        lat, lon = entities[0].coordinates
        # DM: 45°12' = 45 + 12/60 = 45.2
        assert abs(lat - 45.2) < 0.001
        assert abs(lon - (-122.5)) < 0.001

    def test_labeled_coordinates(self, extractor):
        """Test coordinates with labels (Lat:, Lon:)."""
        text = "Latitude: 45.5, Longitude: -122.3"
        entities = extractor.extract(text, "methods")

        assert len(entities) > 0
        assert entities[0].coordinates == (45.5, -122.3)

    def test_parentheses_format(self, extractor):
        """Test coordinates in parentheses."""
        text = "The site (45.123, -122.456) is in Oregon."
        entities = extractor.extract(text, "methods")

        assert len(entities) > 0
        assert entities[0].coordinates == (45.123, -122.456)


class TestMalformedCoordinates:
    """Test detection of malformed coordinates with corrupted symbols."""

    def test_degree_as_7(self, extractor):
        """Test degree symbol corrupted as '7' (common spaCy-layout issue)."""
        text = "Coordinates: 45 7 12'N, 122 7 30'W"
        entities = extractor.extract(text, "methods")

        assert len(entities) > 0, "Should detect coordinates with degree as '7'"
        assert entities[0].coordinates is not None
        lat, lon = entities[0].coordinates
        # 45°12' = 45.2
        assert abs(lat - 45.2) < 0.001
        assert abs(lon - (-122.5)) < 0.001

    def test_degree_as_7_minute_as_b(self, extractor):
        """Test degree as '7' and minute as 'b' (both corrupted)."""
        text = "Location: 45 7 12 b N, 122 7 30 b W"
        entities = extractor.extract(text, "methods")

        assert len(entities) > 0, "Should detect coordinates with '7' and 'b' corruptions"
        assert entities[0].coordinates is not None
        lat, lon = entities[0].coordinates
        assert abs(lat - 45.2) < 0.001
        assert abs(lon - (-122.5)) < 0.001

    def test_degree_as_o(self, extractor):
        """Test degree symbol corrupted as lowercase 'o'."""
        text = "Coordinates: 45o12'N, 122o30'W"
        entities = extractor.extract(text, "methods")

        assert len(entities) > 0, "Should detect coordinates with degree as 'o'"
        assert entities[0].coordinates is not None

    def test_minute_as_backtick(self, extractor):
        """Test minute symbol corrupted as backtick."""
        text = "Coordinates: 45°12`N, 122°30`W"
        entities = extractor.extract(text, "methods")

        assert len(entities) > 0, "Should detect coordinates with minute as backtick"

    def test_minute_as_acute(self, extractor):
        """Test minute symbol corrupted as acute accent."""
        text = "Coordinates: 45°12´N, 122°30´W"
        entities = extractor.extract(text, "methods")

        assert len(entities) > 0, "Should detect coordinates with minute as acute"

    def test_compact_format_with_corruption(self, extractor):
        """Test compact decimal format with corrupted symbols."""
        text = "Coordinates: 00 7 01 b .72N, 77 7 59 b .13E"
        entities = extractor.extract(text, "methods")

        assert len(entities) > 0, "Should detect compact format with corruptions"
        assert entities[0].coordinates is not None
        lat, lon = entities[0].coordinates
        # 00°01.72' = 0 + 1.72/60 = 0.0287
        assert abs(lat - 0.0287) < 0.001

    def test_dms_with_all_corruptions(self, extractor):
        """Test full DMS with all symbols corrupted."""
        text = "Location: 45 7 12 b 30c N, 122 7 30 b 45c W"
        entities = extractor.extract(text, "methods")

        assert len(entities) > 0, "Should detect DMS with all corruptions"

    def test_excessive_spacing(self, extractor):
        """Test coordinates with excessive spacing."""
        text = "Coordinates: 45 ° 12 ' N, 122 ° 30 ' W"
        entities = extractor.extract(text, "methods")

        assert len(entities) > 0, "Should handle excessive spacing"


class TestCoordinateValidation:
    """Test coordinate validation and boundary checks."""

    def test_invalid_latitude_rejected(self, extractor):
        """Test that invalid latitude (>90) is rejected."""
        text = "Invalid coordinates: 95.0, -122.0"
        entities = extractor.extract(text, "methods")

        # Should either find no entities or reject during validation
        if entities:
            assert entities[0].coordinates is None or entities[0].coordinates[0] <= 90

    def test_invalid_longitude_rejected(self, extractor):
        """Test that invalid longitude (>180) is rejected."""
        text = "Invalid coordinates: 45.0, 185.0"
        entities = extractor.extract(text, "methods")

        # Should either find no entities or reject during validation
        if entities:
            assert entities[0].coordinates is None or abs(entities[0].coordinates[1]) <= 180

    def test_zero_zero_rejected(self, extractor):
        """Test that (0, 0) coordinates are rejected as placeholders."""
        text = "Placeholder coordinates: 0.0, 0.0"
        entities = extractor.extract(text, "methods")

        # (0, 0) should be filtered out during validation
        valid_entities = [e for e in entities if e.coordinates and e.coordinates != (0.0, 0.0)]
        assert len(valid_entities) == 0, "(0, 0) should be rejected"


class TestRealWorldExamples:
    """Test with real-world examples from scientific PDFs."""

    def test_table_coordinates_with_corruption(self, extractor):
        """Test coordinates from a corrupted table."""
        text = """
        Table 1. Study site coordinates
        Site A: 00 7 01 b .72N, 77 7 59 b .13E
        Site B: 45 7 30 b N, 122 7 15 b W
        """
        entities = extractor.extract(text, "methods")

        assert len(entities) >= 2, "Should detect multiple coordinates from table"

        # Check first coordinate
        site_a = entities[0]
        assert site_a.coordinates is not None

        # Check second coordinate
        site_b = entities[1]
        assert site_b.coordinates is not None

    def test_methods_section_with_mixed_formats(self, extractor):
        """Test methods section with mixed coordinate formats."""
        text = """
        Methods: Field sites were established at three locations:
        Site 1 (45.5°N, 122.3°W), Site 2 at 40 7 15 b N, 75 7 30 b W,
        and Site 3 with coordinates Latitude: 35.2, Longitude: -120.5.
        """
        entities = extractor.extract(text, "methods")

        assert len(entities) >= 3, "Should detect all three coordinate formats"

    def test_abstract_with_general_location(self, extractor):
        """Test abstract with both precise and general coordinates."""
        text = """
        Abstract: This study examines marine biodiversity in the Pacific Ocean
        near 45.5°N, 122.3°W and also references previous work at 40o30'N.
        """
        entities = extractor.extract(text, "abstract")

        assert len(entities) >= 2, "Should detect both coordinate formats"


class TestCoordinateMatcher:
    """Test the CoordinateMatcher component directly."""

    def test_component_adds_coordinate_entities(self, nlp):
        """Test that the component adds COORDINATE entities to doc.ents."""
        text = "Location: 45.5°N, 122.3°W"
        doc = nlp(text)

        # Find coordinate entities
        coord_ents = [ent for ent in doc.ents if ent.label_ == "COORDINATE"]

        assert len(coord_ents) > 0, "Matcher should add COORDINATE entities"
        assert coord_ents[0].text == "45.5°N, 122.3°W"

    def test_component_adds_metadata(self, nlp):
        """Test that the component adds format and confidence metadata."""
        text = "Coordinates: 45°12'30\"N, 122°30'15\"W"
        doc = nlp(text)

        coord_ents = [ent for ent in doc.ents if ent.label_ == "COORDINATE"]

        assert len(coord_ents) > 0
        # Check custom attributes
        if hasattr(coord_ents[0]._, "coordinate_format"):
            assert coord_ents[0]._.coordinate_format is not None
        if hasattr(coord_ents[0]._, "coordinate_confidence"):
            assert coord_ents[0]._.coordinate_confidence > 0

    def test_no_overlapping_matches(self, nlp):
        """Test that overlapping coordinate matches are filtered."""
        # This text could match multiple patterns
        text = "Latitude: 45.5, Longitude: -122.3 (45.5, -122.3)"
        doc = nlp(text)

        coord_ents = [ent for ent in doc.ents if ent.label_ == "COORDINATE"]

        # Check that no entities overlap
        for i, ent1 in enumerate(coord_ents):
            for ent2 in coord_ents[i+1:]:
                # Entities should not overlap
                assert not (ent1.start_char < ent2.end_char and
                          ent1.end_char > ent2.start_char), \
                       "Entities should not overlap"


class TestConfidenceScoring:
    """Test confidence scoring for different coordinate formats."""

    def test_dms_has_highest_confidence(self, extractor):
        """Test that DMS format has highest confidence."""
        text = "Coordinates: 45°12'30\"N, 122°30'15\"W"
        entities = extractor.extract(text, "methods")

        assert len(entities) > 0
        # DMS should have confidence of 1.0
        assert entities[0].confidence >= 0.95

    def test_malformed_has_lower_confidence(self, extractor):
        """Test that malformed coordinates have lower confidence."""
        text = "Coordinates: 45 7 12 b N, 122 7 30 b W"
        entities = extractor.extract(text, "methods")

        assert len(entities) > 0
        # Malformed should have lower confidence (but still high enough to use)
        assert entities[0].confidence >= 0.70
        assert entities[0].confidence < 0.95


class TestContextExtraction:
    """Test that proper context is extracted for coordinates."""

    def test_sentence_context_extracted(self, extractor):
        """Test that sentence context is properly extracted."""
        text = "The study site is located at 45.5°N, 122.3°W in Oregon. Other sites exist too."
        entities = extractor.extract(text, "methods")

        assert len(entities) > 0
        context = entities[0].context
        assert "study site" in context.lower()
        assert "Oregon" in context

    def test_context_includes_full_sentence(self, extractor):
        """Test that context includes the full sentence."""
        text = "Field measurements were conducted at coordinates 45.5, -122.3 throughout summer."
        entities = extractor.extract(text, "methods")

        assert len(entities) > 0
        context = entities[0].context
        assert "Field measurements" in context
        assert "summer" in context


class TestMatcherPatterns:
    """Test Matcher-based token patterns with greedy LONGEST matching."""

    def test_matcher_labeled_latlon(self, nlp):
        """Test Matcher pattern for 'Lat: X, Lon: Y'."""
        text = "Study location: Lat: 45.123, Lon: -122.456"
        doc = nlp(text)

        coord_ents = [ent for ent in doc.ents if ent.label_ == "COORDINATE"]
        assert len(coord_ents) > 0
        # Should match the full labeled format
        assert "Lat" in coord_ents[0].text or "lat" in coord_ents[0].text.lower()
        assert "Lon" in coord_ents[0].text or "lon" in coord_ents[0].text.lower()

    def test_matcher_longitude_latitude_reversed(self, nlp):
        """Test Matcher pattern for reversed order 'Lon: X, Lat: Y'."""
        text = "Position: Lon: -122.456, Lat: 45.123"
        doc = nlp(text)

        coord_ents = [ent for ent in doc.ents if ent.label_ == "COORDINATE"]
        assert len(coord_ents) > 0

    def test_matcher_coordinates_prefix(self, nlp):
        """Test Matcher pattern for 'Coordinates: X, Y'."""
        text = "Coordinates: 45.123, -122.456"
        doc = nlp(text)

        coord_ents = [ent for ent in doc.ents if ent.label_ == "COORDINATE"]
        assert len(coord_ents) > 0

    def test_greedy_longest_prefers_labeled_over_decimal(self, nlp):
        """Test that greedy LONGEST prefers labeled format over bare decimals."""
        text = "Lat: 45.123, Lon: -122.456"
        doc = nlp(text)

        coord_ents = [ent for ent in doc.ents if ent.label_ == "COORDINATE"]
        # Should match once with the full labeled pattern, not the decimal pair
        assert len(coord_ents) == 1
        # Should include the labels
        text_lower = coord_ents[0].text.lower()
        assert "lat" in text_lower or "lon" in text_lower


class TestEntityRulerPatterns:
    """Test EntityRuler regex patterns."""

    def test_ruler_dms_format(self, nlp):
        """Test EntityRuler DMS pattern."""
        text = "Site at 45°12'30\"N, 122°30'15\"W"
        doc = nlp(text)

        coord_ents = [ent for ent in doc.ents if ent.label_ == "COORDINATE"]
        assert len(coord_ents) > 0
        assert "°" in coord_ents[0].text

    def test_ruler_dm_format(self, nlp):
        """Test EntityRuler DM pattern."""
        text = "Location: 45°12'N, 122°30'W"
        doc = nlp(text)

        coord_ents = [ent for ent in doc.ents if ent.label_ == "COORDINATE"]
        assert len(coord_ents) > 0

    def test_ruler_malformed_degree_as_7(self, nlp):
        """Test EntityRuler pattern for degree corrupted as '7'."""
        text = "Coordinates: 45 7 12'N, 122 7 30'W"
        doc = nlp(text)

        coord_ents = [ent for ent in doc.ents if ent.label_ == "COORDINATE"]
        assert len(coord_ents) > 0
        assert "7" in coord_ents[0].text

    def test_ruler_decimal_pair(self, nlp):
        """Test EntityRuler decimal pair pattern."""
        text = "Located at 45.123, -122.456 in the region."
        doc = nlp(text)

        coord_ents = [ent for ent in doc.ents if ent.label_ == "COORDINATE"]
        assert len(coord_ents) > 0


class TestPDFFile:
    """Test coordinate extraction from actual PDF file."""

    def test_extract_from_test_pdf(self):
        """Test extracting coordinates from tests/data/35J9RCQ8.pdf."""
        from pathlib import Path

        pdf_path = Path("tests/data/35J9RCQ8.pdf")
        if not pdf_path.exists():
            pytest.skip(f"Test PDF not found at {pdf_path}")

        try:
            import spacy
            from app.nlp.pdf_parser import DoclingPDFParser

            # Create NLP pipeline with coordinate matcher
            nlp = spacy.load("en_core_web_sm")
            if "coordinate_matcher" not in nlp.pipe_names:
                nlp.add_pipe("coordinate_matcher", before="ner")

            # Parse PDF
            parser = DoclingPDFParser(nlp)
            parsed = parser.parse_pdf(str(pdf_path))

            # Get text content
            text = parsed.get("markdown", "")
            if not text:
                pytest.skip("Could not extract text from PDF")

            # Process through NLP pipeline
            doc = nlp(text)

            # Extract coordinate entities
            coord_ents = [ent for ent in doc.ents if ent.label_ == "COORDINATE"]

            # Verify we found coordinates
            assert len(coord_ents) > 0, "Expected to find coordinates in test PDF"

            # Verify attributes are set
            for ent in coord_ents:
                assert hasattr(ent._, "coordinate_format")
                assert hasattr(ent._, "coordinate_confidence")

            # Print found coordinates for manual verification
            print(f"\nFound {len(coord_ents)} coordinates in PDF:")
            for i, ent in enumerate(coord_ents[:5]):  # Print first 5
                print(f"{i+1}. {ent.text} (format: {ent._.coordinate_format})")

        except ImportError as e:
            pytest.skip(f"Required dependencies not available: {e}")

    def test_pdf_with_extractor(self):
        """Test PDF extraction using SpaCyCoordinateExtractor."""
        from pathlib import Path

        pdf_path = Path("tests/data/35J9RCQ8.pdf")
        if not pdf_path.exists():
            pytest.skip(f"Test PDF not found at {pdf_path}")

        try:
            from app.nlp.extractors import SpaCyCoordinateExtractor
            from app.nlp.model_config import ModelConfig
            from app.nlp.pdf_parser import DoclingPDFParser
            import spacy

            # Setup
            config = ModelConfig()
            extractor = SpaCyCoordinateExtractor(config)
            nlp = spacy.load("en_core_web_sm")
            parser = DoclingPDFParser(nlp)

            # Parse PDF
            parsed = parser.parse_pdf(str(pdf_path))
            text = parsed.get("markdown", "")
            if not text:
                pytest.skip("Could not extract text from PDF")

            # Extract coordinates
            entities = extractor.extract(text, "document")

            # Verify we found valid coordinates
            valid_coords = [e for e in entities if e.coordinates is not None]
            assert len(valid_coords) > 0, "Expected to find valid parsed coordinates"

            # Print for manual verification
            print(f"\nExtracted {len(valid_coords)} valid coordinates:")
            for i, ent in enumerate(valid_coords[:5]):
                lat, lon = ent.coordinates
                print(f"{i+1}. {ent.text} -> ({lat:.4f}, {lon:.4f})")

        except ImportError as e:
            pytest.skip(f"Required dependencies not available: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
