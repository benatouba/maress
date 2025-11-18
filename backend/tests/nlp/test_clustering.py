"""Tests for coordinate clustering logic.

Tests that:
- ALL coordinate entities are always kept
- Named entities and spatial relations: only largest cluster is kept
- Coordinates are converted to decimal format
"""

import pytest

from app.nlp.clustering import CoordinateClusterer
from app.nlp.domain_models import GeoEntity


class TestClusteringLogic:
    """Test clustering with separation of coordinates from other entities."""

    @pytest.fixture
    def clusterer(self) -> CoordinateClusterer:
        """Create a clusterer instance."""
        return CoordinateClusterer(eps_km=50.0, min_samples=1)

    def test_all_coordinates_always_kept(self, clusterer: CoordinateClusterer) -> None:
        """Test that ALL coordinate entities are always kept, regardless of clustering."""
        # Create entities with coordinates far apart (would be in different clusters)
        entities = [
            # Coordinates in cluster 1 (California)
            GeoEntity(
                text="37.7749, -122.4194",
                entity_type="COORDINATE",
                coordinates=(37.7749, -122.4194),  # San Francisco
                context="Site A",
                section="methods",
                confidence=0.95,
            ),
            # Coordinates in cluster 2 (New York) - far from cluster 1
            GeoEntity(
                text="40.7128, -74.0060",
                entity_type="COORDINATE",
                coordinates=(40.7128, -74.0060),  # New York
                context="Site B",
                section="methods",
                confidence=0.95,
            ),
            # Named entity in cluster 1
            GeoEntity(
                text="San Francisco",
                entity_type="GPE",
                coordinates=(37.7749, -122.4194),
                context="Located in San Francisco",
                section="methods",
                confidence=0.85,
            ),
            # Named entity in cluster 2
            GeoEntity(
                text="New York",
                entity_type="GPE",
                coordinates=(40.7128, -74.0060),
                context="Located in New York",
                section="methods",
                confidence=0.85,
            ),
        ]

        result_entities, cluster_info = clusterer.cluster_entities(entities)

        # ALL coordinates should be kept (both SF and NY)
        coordinate_results = [e for e in result_entities if e.entity_type == "COORDINATE"]
        assert len(coordinate_results) == 2, "All coordinates must be kept"

        # Only ONE cluster of named entities should be kept (the largest)
        named_entity_results = [e for e in result_entities if e.entity_type in ["GPE", "LOC"]]
        assert len(named_entity_results) == 1, "Only largest cluster of named entities should be kept"

        # Verify metadata
        assert cluster_info["coordinates_always_included"] == 2

    def test_largest_cluster_selected_for_named_entities(self, clusterer: CoordinateClusterer) -> None:
        """Test that only the largest cluster is selected for named entities."""
        entities = [
            # Cluster 1: 3 entities (California)
            GeoEntity(
                text="San Francisco",
                entity_type="GPE",
                coordinates=(37.7749, -122.4194),
                context="SF",
                section="methods",
                confidence=0.9,
            ),
            GeoEntity(
                text="Oakland",
                entity_type="GPE",
                coordinates=(37.8044, -122.2712),
                context="Oakland",
                section="methods",
                confidence=0.9,
            ),
            GeoEntity(
                text="Berkeley",
                entity_type="GPE",
                coordinates=(37.8715, -122.2730),
                context="Berkeley",
                section="methods",
                confidence=0.9,
            ),
            # Cluster 2: 2 entities (New York) - smaller cluster
            GeoEntity(
                text="New York",
                entity_type="GPE",
                coordinates=(40.7128, -74.0060),
                context="NY",
                section="methods",
                confidence=0.9,
            ),
            GeoEntity(
                text="Brooklyn",
                entity_type="GPE",
                coordinates=(40.6782, -73.9442),
                context="Brooklyn",
                section="methods",
                confidence=0.9,
            ),
        ]

        result_entities, cluster_info = clusterer.cluster_entities(entities)

        # Should have 3 entities from California cluster (largest)
        assert len(result_entities) == 3, "Should keep only the largest cluster"

        # All results should be from California (lat ~37-38)
        for entity in result_entities:
            if entity.coordinates:
                lat, _ = entity.coordinates
                assert 37 <= lat <= 38, "Should only have California entities"

        assert cluster_info["largest_cluster_size"] == 3

    def test_coordinates_kept_even_with_small_cluster(self, clusterer: CoordinateClusterer) -> None:
        """Test that coordinates are kept even if their cluster is smaller."""
        entities = [
            # Large cluster of named entities (California) - 3 entities
            GeoEntity(
                text="San Francisco",
                entity_type="GPE",
                coordinates=(37.7749, -122.4194),
                context="SF",
                section="methods",
                confidence=0.9,
            ),
            GeoEntity(
                text="Oakland",
                entity_type="GPE",
                coordinates=(37.8044, -122.2712),
                context="Oakland",
                section="methods",
                confidence=0.9,
            ),
            GeoEntity(
                text="Berkeley",
                entity_type="GPE",
                coordinates=(37.8715, -122.2730),
                context="Berkeley",
                section="methods",
                confidence=0.9,
            ),
            # Coordinate in small cluster (New York) - just 1 entity
            GeoEntity(
                text="40.7128, -74.0060",
                entity_type="COORDINATE",
                coordinates=(40.7128, -74.0060),
                context="NY Site",
                section="methods",
                confidence=0.95,
            ),
        ]

        result_entities, cluster_info = clusterer.cluster_entities(entities)

        # Should have 3 from largest cluster + 1 coordinate from smaller cluster
        assert len(result_entities) == 4

        # Verify the NY coordinate is included despite being in smaller cluster
        ny_coords = [e for e in result_entities if e.entity_type == "COORDINATE"]
        assert len(ny_coords) == 1
        assert ny_coords[0].text == "40.7128, -74.0060"

    def test_spatial_relations_follow_clustering(self, clusterer: CoordinateClusterer) -> None:
        """Test that spatial relations follow the clustering logic (largest cluster only)."""
        entities = [
            # Cluster 1: California
            GeoEntity(
                text="10 km north of San Francisco",
                entity_type="SPATIAL_RELATION",
                coordinates=(37.8749, -122.4194),  # 10 km north of SF
                context="Study site near SF",
                section="methods",
                confidence=0.85,
            ),
            GeoEntity(
                text="near Oakland",
                entity_type="SPATIAL_RELATION",
                coordinates=(37.8044, -122.2712),
                context="Oakland area",
                section="methods",
                confidence=0.85,
            ),
            # Cluster 2: New York (smaller cluster)
            GeoEntity(
                text="adjacent to Brooklyn",
                entity_type="SPATIAL_RELATION",
                coordinates=(40.6782, -73.9442),
                context="Near Brooklyn",
                section="methods",
                confidence=0.85,
            ),
        ]

        result_entities, cluster_info = clusterer.cluster_entities(entities)

        # Should only keep the 2 from California (largest cluster)
        assert len(result_entities) == 2

        # Verify they're all California entities
        for entity in result_entities:
            if entity.coordinates:
                lat, _ = entity.coordinates
                assert 37 <= lat <= 38

    def test_no_coordinates_only_named_entities(self, clusterer: CoordinateClusterer) -> None:
        """Test clustering when there are no coordinate entities, only named entities."""
        entities = [
            # Cluster 1
            GeoEntity(
                text="San Francisco",
                entity_type="GPE",
                coordinates=(37.7749, -122.4194),
                context="SF",
                section="methods",
                confidence=0.9,
            ),
            # Cluster 2
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

        # Should have only 1 entity (largest cluster - but both are same size, so first one)
        assert len(result_entities) >= 1
        assert cluster_info["coordinates_always_included"] == 0

    def test_entities_without_coordinates_are_kept(self, clusterer: CoordinateClusterer) -> None:
        """Test that entities without coordinates are kept."""
        entities = [
            # Coordinate entities
            GeoEntity(
                text="37.7749, -122.4194",
                entity_type="COORDINATE",
                coordinates=(37.7749, -122.4194),
                context="SF site",
                section="methods",
                confidence=0.95,
            ),
            # Entity without coordinates
            GeoEntity(
                text="California",
                entity_type="LOC",
                coordinates=None,
                context="In California",
                section="methods",
                confidence=0.8,
            ),
        ]

        result_entities, cluster_info = clusterer.cluster_entities(entities)

        # Should have both: 1 coordinate + 1 without coordinates
        assert len(result_entities) == 2

        entities_without_coords = [e for e in result_entities if e.coordinates is None]
        assert len(entities_without_coords) == 1

    def test_single_coordinate_entity(self, clusterer: CoordinateClusterer) -> None:
        """Test with a single coordinate entity (no clustering needed)."""
        entities = [
            GeoEntity(
                text="37.7749, -122.4194",
                entity_type="COORDINATE",
                coordinates=(37.7749, -122.4194),
                context="Single site",
                section="methods",
                confidence=0.95,
            ),
        ]

        result_entities, cluster_info = clusterer.cluster_entities(entities)

        # Should return the single entity
        assert len(result_entities) == 1
        assert result_entities[0].entity_type == "COORDINATE"

    def test_empty_entities_list(self, clusterer: CoordinateClusterer) -> None:
        """Test with empty entities list."""
        entities = []

        result_entities, cluster_info = clusterer.cluster_entities(entities)

        assert len(result_entities) == 0
        assert cluster_info == {}


class TestCoordinateFormat:
    """Test that coordinates are in correct decimal format."""

    @pytest.fixture
    def clusterer(self) -> CoordinateClusterer:
        """Create a clusterer instance."""
        return CoordinateClusterer(eps_km=50.0, min_samples=1)

    def test_coordinates_are_decimal_tuples(self, clusterer: CoordinateClusterer) -> None:
        """Test that all coordinates are (lat, lon) tuples with decimal values."""
        entities = [
            GeoEntity(
                text="37.7749, -122.4194",
                entity_type="COORDINATE",
                coordinates=(37.7749, -122.4194),
                context="Site",
                section="methods",
                confidence=0.95,
            ),
        ]

        result_entities, _ = clusterer.cluster_entities(entities)

        for entity in result_entities:
            if entity.coordinates:
                lat, lon = entity.coordinates
                # Check types
                assert isinstance(lat, (int, float))
                assert isinstance(lon, (int, float))
                # Check ranges
                assert -90 <= lat <= 90
                assert -180 <= lon <= 180

    def test_coordinates_have_precision(self, clusterer: CoordinateClusterer) -> None:
        """Test that coordinates maintain their precision."""
        entities = [
            GeoEntity(
                text="37.774929, -122.419418",
                entity_type="COORDINATE",
                coordinates=(37.774929, -122.419418),
                context="Precise site",
                section="methods",
                confidence=0.95,
            ),
        ]

        result_entities, _ = clusterer.cluster_entities(entities)

        coord_entity = result_entities[0]
        lat, lon = coord_entity.coordinates

        # Verify precision is maintained
        assert abs(lat - 37.774929) < 0.000001
        assert abs(lon - (-122.419418)) < 0.000001


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
