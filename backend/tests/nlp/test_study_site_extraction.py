"""Tests for study site extraction components."""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pandas as pd
import pytest
from geopy.location import Location as GeopyLocation
from pydantic_extra_types.coordinate import Latitude, Longitude
from spacy.tokens import Span

from app.core.config import settings
from app.nlp.find_my_home import (
    CoordinateCandidate,
    CoordinateClusterer,
    CoordinateExtractor,
    LocationCandidate,
    LocationExtractor,
    StudySiteExtractor,
)
from maress_types import (
    CoordinateExtractionMethod,
    CoordinateSourceType,
    PaperSections,
)

if TYPE_CHECKING:
    from app.services import SpaCyModelManager


class TestLocationExtractorCache:
    """Test geocoding cache and rate limiting."""

    def test_geocoding_cache_hit(self, model_manager: SpaCyModelManager) -> None:
        """Test that geocoding results are cached and reused."""
        extractor = LocationExtractor(settings.SPACY_MODEL)

        location = LocationCandidate(
            name="Quito",
            confidence_score=0.8,
            priority_score=80,
            source_type=CoordinateSourceType.TEXT,
            context="Study conducted in Quito",
            section=PaperSections.METHODS,
        )

        # Mock geocoder
        mock_result = Mock(spec=GeopyLocation)
        mock_result.latitude = -0.1807
        mock_result.longitude = -78.4678

        with patch.object(extractor.geocoder, "geocode") as mock_geocode:
            mock_geocode.return_value = mock_result

            # First call - should hit geocoder
            result1 = extractor.geocode_with_bias([location], bias_point=None)
            assert mock_geocode.call_count == 1
            assert result1[0].coordinates is not None

            # Second call with same location - should use cache
            location2 = LocationCandidate(
                name="Quito",
                confidence_score=0.7,
                priority_score=70,
                source_type=CoordinateSourceType.TEXT,
                context="Another mention of Quito",
                section=PaperSections.ABSTRACT,
            )
            result2 = extractor.geocode_with_bias([location2], bias_point=None)
            # Should still be 1 - used cache
            assert mock_geocode.call_count == 1
            assert result2[0].coordinates is not None
            assert result2[0].coordinates.latitude == result1[0].coordinates.latitude

    def test_geocoding_cache_negative_result(
        self,
        model_manager: SpaCyModelManager,
    ) -> None:
        """Test that failed geocoding is also cached."""
        extractor = LocationExtractor(settings.SPACY_MODEL)

        location = LocationCandidate(
            name="NonexistentPlace12345",
            confidence_score=0.5,
            priority_score=40,
            source_type=CoordinateSourceType.TEXT,
            context="Study at NonexistentPlace12345",
            section=PaperSections.METHODS,
        )

        with patch.object(extractor.geocoder, "geocode") as mock_geocode:
            mock_geocode.return_value = None  # Not found

            # First call
            result1 = extractor.geocode_with_bias([location], bias_point=None)
            assert mock_geocode.call_count == 1
            assert result1[0].coordinates is None

            # Second call - should use cached negative result
            location2 = LocationCandidate(
                name="NonexistentPlace12345",
                confidence_score=0.5,
                priority_score=40,
                source_type=CoordinateSourceType.TEXT,
                context="Another mention",
                section=PaperSections.METHODS,
            )
            result2 = extractor.geocode_with_bias([location2], bias_point=None)
            # Should still be 1 - used cache
            assert mock_geocode.call_count == 1
            assert result2[0].coordinates is None

    def test_geocoding_rate_limiting(self, model_manager: SpaCyModelManager) -> None:
        """Test that rate limiting enforces minimum delay between requests."""
        extractor = LocationExtractor(settings.SPACY_MODEL)

        locations = [
            LocationCandidate(
                name=f"Place{i}",
                confidence_score=0.8,
                priority_score=80,
                source_type=CoordinateSourceType.TEXT,
                context=f"Context {i}",
                section=PaperSections.METHODS,
            )
            for i in range(3)
        ]

        mock_result = Mock(spec=GeopyLocation)
        mock_result.latitude = -0.1807
        mock_result.longitude = -78.4678

        with patch.object(extractor.geocoder, "geocode") as mock_geocode:
            mock_geocode.return_value = mock_result

            start_time = time.time()
            extractor.geocode_with_bias(locations, bias_point=None)
            elapsed = time.time() - start_time

            # With rate limiting at 1 req/sec, 3 requests should take ~2 seconds
            # (first is immediate, then 1s delay, then 1s delay)
            assert elapsed >= 2.0, f"Rate limiting not working: elapsed={elapsed:.2f}s"
            assert mock_geocode.call_count == 3


class TestCoordinateClusterer:
    """Test clustering that returns largest cluster."""

    def test_single_cluster_preservation(self) -> None:
        """Test clustering with single geographic region."""
        clusterer = CoordinateClusterer(eps_km=50.0)

        candidates = [
            CoordinateCandidate(
                latitude=Latitude(-0.5),
                longitude=Longitude(-78.5),
                confidence_score=0.9,
                priority_score=100,
                source_type=CoordinateSourceType.TEXT,
                context="Site 1",
                section=PaperSections.METHODS,
                name="Site 1",
                extraction_method=CoordinateExtractionMethod.REGEX,
            ),
            CoordinateCandidate(
                latitude=Latitude(-0.51),  # Very close
                longitude=Longitude(-78.51),
                confidence_score=0.85,
                priority_score=90,
                source_type=CoordinateSourceType.TEXT,
                context="Site 2",
                section=PaperSections.METHODS,
                name="Site 2",
                extraction_method=CoordinateExtractionMethod.REGEX,
            ),
        ]

        result, cluster_info = clusterer.cluster_coordinates(candidates)

        # Both should be in cluster 0
        assert len(result) == 2
        assert len(cluster_info) == 1
        assert "cluster_0" in cluster_info
        assert cluster_info["cluster_0"] == 2

        # Verify cluster labels assigned
        assert result[0].cluster_label is not None
        assert result[1].cluster_label is not None
        assert result[0].cluster_label == result[1].cluster_label

    def test_multiple_clusters_largest_only(self) -> None:
        """Test that only the largest cluster is returned.

        When multiple geographic regions are detected, we keep only the largest cluster.
        """
        clusterer = CoordinateClusterer(eps_km=50.0)

        candidates = [
            # Cluster 0: Ecuador (2 sites)
            CoordinateCandidate(
                latitude=Latitude(-0.5),
                longitude=Longitude(-78.5),
                confidence_score=0.9,
                priority_score=100,
                source_type=CoordinateSourceType.TEXT,
                context="Ecuador Site 1",
                section=PaperSections.METHODS,
                name="Ecuador 1",
                extraction_method=CoordinateExtractionMethod.REGEX,
            ),
            CoordinateCandidate(
                latitude=Latitude(-0.52),
                longitude=Longitude(-78.48),
                confidence_score=0.85,
                priority_score=95,
                source_type=CoordinateSourceType.TEXT,
                context="Ecuador Site 2",
                section=PaperSections.METHODS,
                name="Ecuador 2",
                extraction_method=CoordinateExtractionMethod.REGEX,
            ),
            # Cluster 1: Peru (1 site)
            CoordinateCandidate(
                latitude=Latitude(-12.0),
                longitude=Longitude(-77.0),
                confidence_score=0.88,
                priority_score=98,
                source_type=CoordinateSourceType.TEXT,
                context="Peru Site",
                section=PaperSections.METHODS,
                name="Peru",
                extraction_method=CoordinateExtractionMethod.REGEX,
            ),
            # Cluster 2: Chile (1 site)
            CoordinateCandidate(
                latitude=Latitude(-33.5),
                longitude=Longitude(-70.6),
                confidence_score=0.82,
                priority_score=92,
                source_type=CoordinateSourceType.TEXT,
                context="Chile Site",
                section=PaperSections.METHODS,
                name="Chile",
                extraction_method=CoordinateExtractionMethod.REGEX,
            ),
        ]

        result, cluster_info = clusterer.cluster_coordinates(candidates)

        # Only largest cluster (Ecuador with 2 sites) should be returned
        assert len(result) == 2

        # Should detect 3 clusters in cluster_info
        assert len(cluster_info) == 3
        assert cluster_info.get("cluster_0", 0) == 2  # Ecuador cluster (largest)
        assert cluster_info.get("cluster_1", 0) == 1  # Peru cluster
        assert cluster_info.get("cluster_2", 0) == 1  # Chile cluster

        # Verify all returned candidates are from the same (largest) cluster
        cluster_labels = {c.cluster_label for c in result}
        assert len(cluster_labels) == 1  # All from same cluster

        # Verify both Ecuador sites are returned
        assert result[0].cluster_label == result[1].cluster_label
        assert "Ecuador" in result[0].name
        assert "Ecuador" in result[1].name

    def test_cluster_returns_largest_only(self) -> None:
        """Test that only the largest cluster is returned."""
        clusterer = CoordinateClusterer(eps_km=50.0)

        candidates = [
            # Small cluster (1 site)
            CoordinateCandidate(
                latitude=Latitude(-33.5),
                longitude=Longitude(-70.6),
                confidence_score=0.95,
                priority_score=100,
                source_type=CoordinateSourceType.TEXT,
                context="Chile",
                section=PaperSections.METHODS,
                name="Chile",
                extraction_method=CoordinateExtractionMethod.REGEX,
            ),
            # Large cluster (3 sites) - should come first despite being added last
            CoordinateCandidate(
                latitude=Latitude(-0.5),
                longitude=Longitude(-78.5),
                confidence_score=0.8,
                priority_score=90,
                source_type=CoordinateSourceType.TEXT,
                context="Ecuador 1",
                section=PaperSections.METHODS,
                name="Ecuador 1",
                extraction_method=CoordinateExtractionMethod.REGEX,
            ),
            CoordinateCandidate(
                latitude=Latitude(-0.51),
                longitude=Longitude(-78.49),
                confidence_score=0.75,
                priority_score=85,
                source_type=CoordinateSourceType.TEXT,
                context="Ecuador 2",
                section=PaperSections.METHODS,
                name="Ecuador 2",
                extraction_method=CoordinateExtractionMethod.REGEX,
            ),
            CoordinateCandidate(
                latitude=Latitude(-0.52),
                longitude=Longitude(-78.48),
                confidence_score=0.7,
                priority_score=80,
                source_type=CoordinateSourceType.TEXT,
                context="Ecuador 3",
                section=PaperSections.METHODS,
                name="Ecuador 3",
                extraction_method=CoordinateExtractionMethod.REGEX,
            ),
        ]

        result, cluster_info = clusterer.cluster_coordinates(candidates)

        # Only the 3 Ecuador sites should be returned (largest cluster)
        assert len(result) == 3

        # All results should be from the same (largest) cluster
        ecuador_cluster_label = result[0].cluster_label
        assert result[1].cluster_label == ecuador_cluster_label
        assert result[2].cluster_label == ecuador_cluster_label

        # Verify all are Ecuador sites
        assert all("Ecuador" in c.name for c in result)

    def test_noise_points_handling(self) -> None:
        """Test handling of noise points (cluster label -1)."""
        clusterer = CoordinateClusterer(eps_km=50.0, min_samples=2)

        candidates = [
            # Cluster (2 close points)
            CoordinateCandidate(
                latitude=Latitude(-0.5),
                longitude=Longitude(-78.5),
                confidence_score=0.9,
                priority_score=100,
                source_type=CoordinateSourceType.TEXT,
                context="Site 1",
                section=PaperSections.METHODS,
                name="Site 1",
                extraction_method=CoordinateExtractionMethod.REGEX,
            ),
            CoordinateCandidate(
                latitude=Latitude(-0.51),
                longitude=Longitude(-78.49),
                confidence_score=0.85,
                priority_score=95,
                source_type=CoordinateSourceType.TEXT,
                context="Site 2",
                section=PaperSections.METHODS,
                name="Site 2",
                extraction_method=CoordinateExtractionMethod.REGEX,
            ),
            # Noise point (isolated)
            CoordinateCandidate(
                latitude=Latitude(-33.5),
                longitude=Longitude(-70.6),
                confidence_score=0.8,
                priority_score=90,
                source_type=CoordinateSourceType.TEXT,
                context="Isolated",
                section=PaperSections.METHODS,
                name="Isolated",
                extraction_method=CoordinateExtractionMethod.REGEX,
            ),
        ]

        result, cluster_info = clusterer.cluster_coordinates(candidates)

        # Only the largest cluster (2 points) should be returned, not noise
        assert len(result) == 2

        # All returned points should be from the same valid cluster (not noise)
        cluster_labels = {c.cluster_label for c in result}
        assert len(cluster_labels) == 1
        assert -1 not in cluster_labels  # Noise points excluded


class TestTableExtraction:
    """Test table coordinate extraction."""

    def test_extract_coordinates_from_table(self) -> None:
        """Test extraction of coordinates from DataFrame with lat/lon columns."""
        extractor = CoordinateExtractor()

        # Create mock table
        df = pd.DataFrame(
            {
                "Site": ["Site A", "Site B", "Site C"],
                "Latitude": [-0.5, -12.0, -33.5],
                "Longitude": [-78.5, -77.0, -70.6],
                "Elevation": [2000, 3000, 500],
            },
        )

        result = extractor.extract_coordinates_from_tables([df])

        assert len(result) == 3

        # Verify coordinates
        coords = [(float(c.latitude), float(c.longitude)) for c in result]
        assert (-0.5, -78.5) in coords
        assert (-12.0, -77.0) in coords
        assert (-33.5, -70.6) in coords

        # Verify metadata
        assert all(c.extraction_method == CoordinateExtractionMethod.TABLE_PARSING for c in result)
        assert all(c.source_type == CoordinateSourceType.TABLE for c in result)
        assert all(c.confidence_score == 0.9 for c in result)  # High confidence for tables
        assert all(c.priority_score == 50 for c in result)  # TABLE_COORDINATES priority

    def test_table_with_alternative_column_names(self) -> None:
        """Test table extraction with various column name formats."""
        extractor = CoordinateExtractor()

        df = pd.DataFrame(
            {
                "lat": [-0.5, -12.0],
                "lon": [-78.5, -77.0],
            },
        )

        result = extractor.extract_coordinates_from_tables([df])
        assert len(result) == 2

        # Test with different naming
        df2 = pd.DataFrame(
            {
                "Y": [-0.5],
                "X": [-78.5],
            },
        )

        result2 = extractor.extract_coordinates_from_tables([df2])
        assert len(result2) == 1

    def test_table_with_site_names(self) -> None:
        """Test extraction of site names from tables."""
        extractor = CoordinateExtractor()

        df = pd.DataFrame(
            {
                "Site Name": ["Ecuador Site", "Peru Site"],
                "Latitude": [-0.5, -12.0],
                "Longitude": [-78.5, -77.0],
            },
        )

        result = extractor.extract_coordinates_from_tables([df])

        assert len(result) == 2
        assert result[0].name == "Ecuador Site"
        assert result[1].name == "Peru Site"

    def test_table_with_invalid_coordinates(self) -> None:
        """Test that invalid coordinates are skipped."""
        extractor = CoordinateExtractor()

        df = pd.DataFrame(
            {
                "Latitude": [-0.5, 999.0, -12.0, "invalid"],  # 999 and "invalid" are bad
                "Longitude": [-78.5, -77.0, -77.0, -70.0],
            },
        )

        result = extractor.extract_coordinates_from_tables([df])

        # Only 2 valid coordinates
        assert len(result) == 2
        assert float(result[0].latitude) == -0.5
        assert float(result[1].latitude) == -12.0

    def test_table_without_coordinate_columns(self) -> None:
        """Test that tables without coordinate columns are skipped."""
        extractor = CoordinateExtractor()

        df = pd.DataFrame(
            {
                "Sample ID": ["A", "B", "C"],
                "Temperature": [20, 25, 30],
                "pH": [7.0, 7.5, 8.0],
            },
        )

        result = extractor.extract_coordinates_from_tables([df])
        assert len(result) == 0

    def test_multiple_tables(self) -> None:
        """Test extraction from multiple tables."""
        extractor = CoordinateExtractor()

        df1 = pd.DataFrame(
            {
                "Latitude": [-0.5],
                "Longitude": [-78.5],
            },
        )

        df2 = pd.DataFrame(
            {
                "lat": [-12.0, -33.5],
                "lon": [-77.0, -70.6],
            },
        )

        result = extractor.extract_coordinates_from_tables([df1, df2])

        # 1 from first table + 2 from second table
        assert len(result) == 3


class TestStudySiteExtractorIntegration:
    """Integration tests for table extraction in main pipeline."""

    def test_table_extraction_integrated(
        self,
        tmp_path: Path,
        model_manager: SpaCyModelManager,
    ) -> None:
        """Test that table extraction is called in the main pipeline."""
        from app.nlp.pdf_text_extractor import ExtractedPDF

        extractor = StudySiteExtractor()

        # Create mock PDF with tables
        mock_tables = [
            Mock(
                spec=Span,
                text="""Site\tLatitude\tLongitude
Site A\t-0.5\t-78.5
Site B\t-12.0\t-77.0""",
            ),
        ]

        mock_extracted_pdf = Mock(spec=ExtractedPDF)
        mock_extracted_pdf.sections = {"methods": "Study conducted in the field."}
        mock_extracted_pdf.captions = []
        mock_extracted_pdf.tables = mock_tables
        mock_extracted_pdf.full_doc = Mock()

        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_text("mock")

        with patch.object(
            extractor.text_extractor,
            "process_scientific_pdf",
        ) as mock_process:
            mock_process.return_value = mock_extracted_pdf

            with patch.object(
                extractor,
                "_parse_table_to_dataframe",
            ) as mock_parse:
                mock_df = pd.DataFrame(
                    {
                        "Site": ["Site A", "Site B"],
                        "Latitude": [-0.5, -12.0],
                        "Longitude": [-78.5, -77.0],
                    },
                )
                mock_parse.return_value = mock_df

                result = extractor.extract_study_sites(pdf_path, title="Test Study")

                # Verify table parsing was called
                mock_parse.assert_called()

                # Verify coordinates from table are in results
                latitudes = [float(c.latitude) for c in result.coordinates]
                assert -0.5 in latitudes or -12.0 in latitudes
