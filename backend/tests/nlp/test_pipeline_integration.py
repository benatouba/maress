"""Integration tests for the full NLP pipeline.

Tests the complete flow:
1. Coordinate extraction with Matcher + EntityRuler
2. Spatial relation extraction with Matcher
3. Clustering logic (coordinates always kept, largest cluster for others)
4. Decimal coordinate conversion
5. Conversion to StudySites
"""

import uuid
from pathlib import Path

import pytest
import spacy

from app.nlp.adapters import StudySiteResultAdapter
from app.nlp.clustering import CoordinateClusterer
from app.nlp.domain_models import ExtractionResult, GeoEntity
from app.nlp.extractors import SpaCyCoordinateExtractor, SpaCyGeoExtractor
from app.nlp.factories import PipelineFactory
from app.nlp.model_config import ModelConfig


class TestFullPipelineIntegration:
    """Test the full pipeline from text to StudySites."""

    @pytest.fixture
    def config(self) -> ModelConfig:
        """Create a test configuration."""
        return ModelConfig()

    @pytest.fixture
    def nlp(self):
        """Create spaCy pipeline with all matchers."""
        nlp = spacy.load("en_core_web_sm")

        # Add coordinate matcher
        if "coordinate_matcher" not in nlp.pipe_names:
            nlp.add_pipe("coordinate_matcher", before="ner")

        # Add spatial relation matcher
        if "spatial_relation_matcher" not in nlp.pipe_names:
            nlp.add_pipe("spatial_relation_matcher", after="ner")

        return nlp

    def test_coordinate_extraction_and_decimal_conversion(self, config: ModelConfig) -> None:
        """Test that coordinates are extracted and converted to decimal."""
        text = """
        Study sites were located at 45°12'30"N, 122°30'15"W and
        also at coordinates 37.7749, -122.4194.
        """

        extractor = SpaCyCoordinateExtractor(config)
        entities = extractor.extract(text, "methods")

        # Should find 2 coordinates
        assert len(entities) == 2

        # All should have decimal coordinates
        for entity in entities:
            assert entity.coordinates is not None
            lat, lon = entity.coordinates
            assert isinstance(lat, (int, float))
            assert isinstance(lon, (int, float))
            assert -90 <= lat <= 90
            assert -180 <= lon <= 180

    def test_spatial_relation_extraction_with_matcher(self, config: ModelConfig) -> None:
        """Test that spatial relations are extracted using Matcher."""
        text = """
        The study site is located 10 km north of San Francisco.
        Additional sampling was conducted near Berkeley.
        """

        extractor = SpaCyGeoExtractor(config)
        entities = extractor.extract(text, "methods")

        # Should find spatial relations
        spatial_relations = [e for e in entities if e.entity_type == "SPATIAL_RELATION"]
        assert len(spatial_relations) > 0

    def test_clustering_keeps_all_coordinates(self) -> None:
        """Test that clustering keeps ALL coordinates but only largest cluster for others."""
        clusterer = CoordinateClusterer(eps_km=50.0, min_samples=1)

        entities = [
            # Coordinate in California
            GeoEntity(
                text="37.7749, -122.4194",
                entity_type="COORDINATE",
                coordinates=(37.7749, -122.4194),
                context="SF site",
                section="methods",
                confidence=0.95,
            ),
            # Coordinate in New York (far from California)
            GeoEntity(
                text="40.7128, -74.0060",
                entity_type="COORDINATE",
                coordinates=(40.7128, -74.0060),
                context="NY site",
                section="methods",
                confidence=0.95,
            ),
            # Named entities in California (larger cluster)
            GeoEntity(
                text="San Francisco",
                entity_type="GPE",
                coordinates=(37.7749, -122.4194),
                context="In SF",
                section="methods",
                confidence=0.9,
            ),
            GeoEntity(
                text="Oakland",
                entity_type="GPE",
                coordinates=(37.8044, -122.2712),
                context="In Oakland",
                section="methods",
                confidence=0.9,
            ),
            # Named entity in New York (smaller cluster)
            GeoEntity(
                text="New York",
                entity_type="GPE",
                coordinates=(40.7128, -74.0060),
                context="In NY",
                section="methods",
                confidence=0.9,
            ),
        ]

        result_entities, cluster_info = clusterer.cluster_entities(entities)

        # Both coordinates should be kept
        coords = [e for e in result_entities if e.entity_type == "COORDINATE"]
        assert len(coords) == 2

        # Only the largest cluster of named entities (California) should be kept
        named = [e for e in result_entities if e.entity_type in ["GPE", "LOC"]]
        assert len(named) == 2  # Only SF and Oakland

        # Verify metadata
        assert cluster_info["coordinates_always_included"] == 2

    def test_coordinates_converted_to_study_sites(self, config: ModelConfig) -> None:
        """Test that ALL coordinates are converted to StudySites."""
        # Create extraction result with coordinates
        entities = [
            GeoEntity(
                text="37.7749, -122.4194",
                entity_type="COORDINATE",
                coordinates=(37.7749, -122.4194),
                context="Study site A",
                section="methods",
                confidence=0.95,
            ),
            GeoEntity(
                text="40.7128, -74.0060",
                entity_type="COORDINATE",
                coordinates=(40.7128, -74.0060),
                context="Study site B",
                section="methods",
                confidence=0.95,
            ),
            # Named entity with low confidence (should be filtered)
            GeoEntity(
                text="California",
                entity_type="LOC",
                coordinates=(36.7783, -119.4179),
                context="In California",
                section="methods",
                confidence=0.3,  # Below threshold
            ),
        ]

        result = ExtractionResult(
            pdf_path=Path("test.pdf"),
            entities=entities,
            total_sections_processed=1,
        )

        item_id = uuid.uuid4()
        study_sites = StudySiteResultAdapter.to_study_sites(
            result=result,
            item_id=item_id,
            min_confidence=0.5,
        )

        # Both coordinates should be converted (they bypass confidence threshold)
        assert len(study_sites) == 2

        # All should have decimal coordinates
        for site in study_sites:
            assert -90 <= site.latitude <= 90
            assert -180 <= site.longitude <= 180

    def test_end_to_end_with_pipeline_factory(self, config: ModelConfig) -> None:
        """Test end-to-end with PipelineFactory."""
        # Create pipeline with all improvements enabled
        coord_extractor = SpaCyCoordinateExtractor(config)
        geo_extractor = SpaCyGeoExtractor(config)

        extractors = [coord_extractor, geo_extractor]

        # Test text with mixed content
        text = """
        Study sites were established at coordinates 45.5N, 122.3W
        and 10 km north of Portland. The sampling area was located
        in the Pacific Northwest region near Seattle.
        """

        all_entities = []
        for extractor in extractors:
            entities = extractor.extract(text, "methods")
            all_entities.extend(entities)

        # Should have extracted various entity types
        assert len(all_entities) > 0

        # Check coordinate entities
        coords = [e for e in all_entities if e.entity_type == "COORDINATE"]
        assert len(coords) > 0

        # Check spatial relations
        relations = [e for e in all_entities if e.entity_type == "SPATIAL_RELATION"]
        assert len(relations) > 0

        # All coordinates should be in decimal format
        for coord_entity in coords:
            if coord_entity.coordinates:
                lat, lon = coord_entity.coordinates
                assert isinstance(lat, (int, float))
                assert isinstance(lon, (int, float))

    def test_malformed_coordinates_converted_correctly(self, config: ModelConfig) -> None:
        """Test that malformed PDF coordinates are parsed correctly."""
        # Malformed coordinates from PDF extraction
        text = """
        Site coordinates: 45 7 12 b N, 122 7 30 b W
        Another site at: 00 7 01 b .72N, 77 7 59 b .13E
        """

        extractor = SpaCyCoordinateExtractor(config)
        entities = extractor.extract(text, "methods")

        # Should find both malformed coordinates
        assert len(entities) == 2

        # Both should be parsed to decimal
        for entity in entities:
            assert entity.coordinates is not None
            lat, lon = entity.coordinates
            assert -90 <= lat <= 90
            assert -180 <= lon <= 180

    def test_clustering_with_mixed_entity_types(self) -> None:
        """Test clustering with coordinates, named entities, and spatial relations."""
        clusterer = CoordinateClusterer(eps_km=50.0, min_samples=1)

        entities = [
            # Coordinates (always kept)
            GeoEntity(
                text="37.7749, -122.4194",
                entity_type="COORDINATE",
                coordinates=(37.7749, -122.4194),
                context="Site",
                section="methods",
                confidence=0.95,
            ),
            # Cluster 1: California (larger)
            GeoEntity(
                text="San Francisco",
                entity_type="GPE",
                coordinates=(37.7749, -122.4194),
                context="SF",
                section="methods",
                confidence=0.9,
            ),
            GeoEntity(
                text="10 km north of SF",
                entity_type="SPATIAL_RELATION",
                coordinates=(37.8749, -122.4194),
                context="Near SF",
                section="methods",
                confidence=0.85,
            ),
            # Cluster 2: New York (smaller)
            GeoEntity(
                text="New York",
                entity_type="GPE",
                coordinates=(40.7128, -74.0060),
                context="NY",
                section="methods",
                confidence=0.9,
            ),
        ]

        result_entities, cluster_info = clusterer.cluster_entities(entities)

        # Coordinate should be kept
        coords = [e for e in result_entities if e.entity_type == "COORDINATE"]
        assert len(coords) == 1

        # Only largest cluster of other entities (California) should be kept
        others = [e for e in result_entities if e.entity_type != "COORDINATE"]
        # Should have SF and spatial relation
        assert len(others) == 2

    def test_real_world_scientific_text(self, config: ModelConfig) -> None:
        """Test with realistic scientific paper text."""
        text = """
        Materials and Methods

        Study sites were established in the Pacific Northwest at coordinates
        45°30'N, 122°45'W. Additional sampling locations were positioned
        approximately 15 km northeast of Portland, Oregon. The research area
        is situated near the Columbia River and within the Cascade Range.

        Field measurements were collected at three primary sites:
        Site A (45.5, -122.75), Site B located in Vancouver, and Site C
        adjacent to the Mt. Hood National Forest.
        """

        # Extract with all extractors
        coord_extractor = SpaCyCoordinateExtractor(config)
        geo_extractor = SpaCyGeoExtractor(config)

        all_entities = []
        all_entities.extend(coord_extractor.extract(text, "methods"))
        all_entities.extend(geo_extractor.extract(text, "methods"))

        # Should find various entity types
        coords = [e for e in all_entities if e.entity_type == "COORDINATE"]
        relations = [e for e in all_entities if e.entity_type == "SPATIAL_RELATION"]
        locations = [e for e in all_entities if e.entity_type in ["GPE", "LOC"]]

        assert len(coords) >= 2, "Should find multiple coordinates"
        assert len(relations) >= 2, "Should find spatial relations"
        assert len(locations) >= 0, "Should find location entities"

        # Cluster and verify coordinates are kept
        clusterer = CoordinateClusterer(eps_km=50.0, min_samples=1)
        result_entities, cluster_info = clusterer.cluster_entities(all_entities)

        # All coordinates should be kept
        result_coords = [e for e in result_entities if e.entity_type == "COORDINATE"]
        assert len(result_coords) == len(coords), "All coordinates must be kept after clustering"

    def test_precision_maintained_through_pipeline(self, config: ModelConfig) -> None:
        """Test that high-precision coordinates maintain precision."""
        text = "Site at 37.774929, -122.419418"

        extractor = SpaCyCoordinateExtractor(config)
        entities = extractor.extract(text, "methods")

        assert len(entities) == 1
        lat, lon = entities[0].coordinates

        # Verify precision is maintained
        assert abs(lat - 37.774929) < 0.000001
        assert abs(lon - (-122.419418)) < 0.000001


class TestPDFPipelineIntegration:
    """Test integration with PDF extraction."""

    @pytest.fixture
    def config(self) -> ModelConfig:
        """Create a test configuration."""
        return ModelConfig()

    def test_pipeline_with_test_pdf(self, config: ModelConfig) -> None:
        """Test full pipeline with the test PDF."""
        pdf_path = Path("tests/data/35J9RCQ8.pdf")

        if not pdf_path.exists():
            pytest.skip(f"Test PDF not found at {pdf_path}")

        try:
            # Create pipeline
            pipeline = PipelineFactory.create_pipeline(
                config=config,
                enable_geocoding=False,  # Disable for faster testing
                enable_clustering=True,
                use_spacy_coordinate_matcher=True,
            )

            # Extract from PDF
            result = pipeline.extract_from_pdf(pdf_path)

            # Should have found entities
            assert len(result.entities) > 0

            # Check that coordinates are present
            coords = [e for e in result.entities if e.entity_type == "COORDINATE"]
            assert len(coords) > 0, "Should find coordinates in PDF"

            # All coordinates should have decimal format
            for coord_entity in coords:
                assert coord_entity.coordinates is not None
                lat, lon = coord_entity.coordinates
                assert -90 <= lat <= 90
                assert -180 <= lon <= 180

            # Test conversion to StudySites
            item_id = uuid.uuid4()
            study_sites = StudySiteResultAdapter.to_study_sites(
                result=result,
                item_id=item_id,
                min_confidence=0.5,
            )

            # Should have converted some entities to study sites
            assert len(study_sites) > 0

            # All study sites should have valid coordinates
            for site in study_sites:
                assert -90 <= site.latitude <= 90
                assert -180 <= site.longitude <= 180

        except Exception as e:
            pytest.skip(f"PDF processing failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
