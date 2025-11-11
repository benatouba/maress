"""Tests for study site extraction task."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from pydantic_extra_types.coordinate import Latitude, Longitude

from app.models import Item
from app.models import StudySite
from app.nlp.domain_models import ExtractionResult, GeoEntity
from app.tasks.extract import extract_study_site_task
from maress_types import (
    CoordinateExtractionMethod,
    CoordinateSourceType,
    PaperSections,
)
from tests.utils.item import create_random_item

if TYPE_CHECKING:
    from sqlmodel import Session


@pytest.fixture
def mock_pdf_path(tmp_path: Path) -> Path:
    """Create a mock PDF file for testing."""
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_text("Mock PDF content")
    return pdf_file


@pytest.fixture
def item_with_pdf(db_session: Session, mock_pdf_path: Path) -> Item:
    """Create an item with a PDF attachment."""
    item = create_random_item(db_session)
    item.attachment = str(mock_pdf_path)
    item.title = "Test Study in Ecuador"
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    return item


@pytest.fixture
def mock_single_site_result(mock_pdf_path: Path) -> ExtractionResult:
    """Mock extraction result with a single study site."""
    entity = GeoEntity(
        text="Main Site",
        entity_type="COORDINATE",
        confidence=0.9,
        section="methods",
        context="Study site located at coordinates",
        coordinates=(-0.5, -78.5),
        start_char=0,
        end_char=9,
    )

    return ExtractionResult(
        pdf_path=mock_pdf_path,
        entities=[entity],
        total_sections_processed=1,
        extraction_metadata={
            "total_entities": 1,
            "coordinates": 1,
            "spatial_relations": 0,
            "locations": 0,
            "clusters": 1,
        },
        doc=None,
        title="Test Study in Ecuador",
        cluster_info={"cluster_1": 1},
        average_text_quality=0.95,
        section_quality_scores={},
    )


@pytest.fixture
def mock_multi_site_result(mock_pdf_path: Path) -> ExtractionResult:
    """Mock extraction result with multiple study sites across different clusters."""
    # Primary site - Ecuador
    entity_1 = GeoEntity(
        text="Ecuador Site",
        entity_type="COORDINATE",
        confidence=0.9,
        section="methods",
        context="Study site located at coordinates",
        coordinates=(-0.5, -78.5),
        start_char=0,
        end_char=12,
    )

    # Second site - Ecuador (same cluster)
    entity_2 = GeoEntity(
        text="Ecuador Site 2",
        entity_type="GPE",
        confidence=0.85,
        section="methods",
        context="Additional sampling location",
        coordinates=(-0.52, -78.48),
        start_char=100,
        end_char=114,
    )

    # Third site - Peru (different cluster)
    entity_3 = GeoEntity(
        text="Peru Site",
        entity_type="COORDINATE",
        confidence=0.80,
        section="methods",
        context="Table 1, Row 1",
        coordinates=(-12.0, -77.0),
        start_char=200,
        end_char=209,
    )

    # Fourth site - Chile (different cluster)
    entity_4 = GeoEntity(
        text="Chile Site",
        entity_type="LOC",
        confidence=0.88,
        section="abstract",
        context="Geocoded from Santiago mention",
        coordinates=(-33.5, -70.6),
        start_char=300,
        end_char=310,
    )

    return ExtractionResult(
        pdf_path=mock_pdf_path,
        entities=[entity_1, entity_2, entity_3, entity_4],
        total_sections_processed=2,
        extraction_metadata={
            "total_entities": 4,
            "coordinates": 4,
            "spatial_relations": 0,
            "locations": 2,
            "clusters": 3,
        },
        doc=None,
        title="Test Study in Multiple Countries",
        cluster_info={"cluster_1": 2, "cluster_2": 1, "cluster_3": 1},
        average_text_quality=0.92,
        section_quality_scores={},
    )


class TestExtractStudySiteTask:
    """Test suite for study site extraction task."""

    def test_extract_single_study_site(
        self,
        db_session: Session,
        item_with_pdf: Item,
        mock_single_site_result: ExtractionResult,
    ) -> None:
        """Test extraction and storage of a single study site."""
        with patch("app.tasks.extract.PipelineFactory.create_pipeline_for_api") as mock_factory:
            mock_pipeline = MagicMock()
            mock_pipeline.extract_from_pdf.return_value = mock_single_site_result
            mock_factory.return_value = mock_pipeline

            result = extract_study_site_task(
                item_id=str(item_with_pdf.id),
                user_id=str(item_with_pdf.owner_id),
                is_superuser=True,
                _test_session=db_session,
            )

            # Verify task result
            assert result["status"] == "created"
            assert result["count"] == 1
            assert "primary_site_id" in result
            assert len(result["study_site_ids"]) == 1

            # Verify database
            db_session.expire_all()
            item = db_session.get(Item, item_with_pdf.id)
            assert item is not None
            assert item.study_sites is not None
            assert len(item.study_sites) == 1

            study_site = item.study_sites[0]
            assert study_site.confidence_score == 0.9
            assert float(study_site.location.latitude) == -0.5
            assert float(study_site.location.longitude) == -78.5

    def test_extract_multiple_study_sites(
        self,
        db_session: Session,
        item_with_pdf: Item,
        mock_multi_site_result: ExtractionResult,
    ) -> None:
        """Test extraction and storage of multiple study sites from different clusters.

        This is the critical fix - verifying all sites are saved, not just primary.
        """
        with patch("app.tasks.extract.PipelineFactory.create_pipeline_for_api") as mock_factory:
            mock_pipeline = MagicMock()
            mock_pipeline.extract_from_pdf.return_value = mock_multi_site_result
            mock_factory.return_value = mock_pipeline

            # Execute task
            result = extract_study_site_task(
                item_id=str(item_with_pdf.id),
                user_id=str(item_with_pdf.owner_id),
                is_superuser=True,
                force=False,
                _test_session=db_session,
            )

            # Verify task result
            assert result["status"] == "created"
            assert result["count"] == 4  # All 4 sites should be saved
            assert "4 study site(s)" in result["message"]
            assert len(result["study_site_ids"]) == 4

            # Verify database - all sites should be present
            db_session.expire_all()
            item = db_session.get(Item, item_with_pdf.id)
            assert item is not None
            assert item.study_sites is not None
            assert len(item.study_sites) == 4

            # Verify all sites have correct data
            sites = item.study_sites
            latitudes = {float(site.location.latitude) for site in sites}
            assert -0.5 in latitudes  # Ecuador primary
            assert -0.52 in latitudes  # Ecuador secondary
            assert -12.0 in latitudes  # Peru
            assert -33.5 in latitudes  # Chile

    def test_skip_existing_sites_without_force(
        self,
        db_session: Session,
        item_with_pdf: Item,
    ) -> None:
        """Test that extraction is skipped when sites exist and force=False."""
        # Create existing study site
        from app.crud import create_study_site
        from app.models import StudySiteCreate

        existing_site = StudySiteCreate(
            name="Existing Site",
            latitude=Latitude(-1.0),
            longitude=Longitude(-79.0),
            confidence_score=0.8,
            context="Pre-existing context",
            extraction_method=CoordinateExtractionMethod.MANUAL,
            section=PaperSections.OTHER,
            source_type=CoordinateSourceType.MANUAL,
            validation_score=1.0,
            item_id=item_with_pdf.id,
        )
        create_study_site(db_session, existing_site)
        db_session.commit()

        with patch("app.tasks.extract.PipelineFactory.create_pipeline_for_api") as mock_factory:
            # Execute task without force
            result = extract_study_site_task(
                item_id=str(item_with_pdf.id),
                user_id=str(item_with_pdf.owner_id),
                is_superuser=True,
                force=False,
                _test_session=db_session,
            )

            # Verify extraction was skipped
            assert result["status"] == "skipped"
            assert "already has" in result["message"]
            mock_factory.assert_not_called()

            # Verify only original site remains
            db_session.expire_all()
            item = db_session.get(Item, item_with_pdf.id)
            assert item is not None
            assert item.study_sites is not None
            assert len(item.study_sites) == 1

    def test_force_reextraction(
        self,
        db_session: Session,
        item_with_pdf: Item,
        mock_multi_site_result: ExtractionResult,
    ) -> None:
        """Test that force=True triggers re-extraction even with existing sites."""
        # Create existing study site
        from app.crud import create_study_site
        from app.models import StudySiteCreate

        existing_site = StudySiteCreate(
            name="Old Site",
            latitude=Latitude(-1.0),
            longitude=Longitude(-79.0),
            confidence_score=0.5,
            context="Old context",
            extraction_method=CoordinateExtractionMethod.MANUAL,
            section=PaperSections.OTHER,
            source_type=CoordinateSourceType.MANUAL,
            validation_score=0.5,
            item_id=item_with_pdf.id,
        )
        create_study_site(db_session, existing_site)
        db_session.commit()

        with patch("app.tasks.extract.PipelineFactory.create_pipeline_for_api") as mock_factory:
            mock_pipeline = MagicMock()
            mock_pipeline.extract_from_pdf.return_value = mock_multi_site_result
            mock_factory.return_value = mock_pipeline

            # Execute task with force=True
            result = extract_study_site_task(
                item_id=str(item_with_pdf.id),
                user_id=str(item_with_pdf.owner_id),
                is_superuser=True,
                force=True,
                _test_session=db_session,
            )

            # Verify extraction was performed
            assert result["status"] == "created"
            mock_factory.assert_called_once()

            # Note: Old site might still exist unless we add deletion logic
            # For now, we just add new sites

    def test_no_pdf_attachment(self, db_session: Session) -> None:
        """Test handling of item without PDF attachment."""
        item = create_random_item(db_session)
        item.attachment = None
        db_session.add(item)
        db_session.commit()

        result = extract_study_site_task(
            item_id=str(item.id),
            user_id=str(item.owner_id),
            is_superuser=True,
            force=False,
            _test_session=db_session,
        )

        assert result["status"] == "no_attachment"
        assert result["count"] == 0
        assert "no PDF attachment" in result["message"]

    def test_pdf_not_found(self, db_session: Session) -> None:
        """Test handling of missing PDF file."""
        item = create_random_item(db_session)
        item.attachment = "/nonexistent/path/file.pdf"
        db_session.add(item)
        db_session.commit()

        with pytest.raises(FileNotFoundError):
            extract_study_site_task(
                item_id=str(item.id),
                user_id=str(item.owner_id),
                is_superuser=True,
                force=False,
                _test_session=db_session,
            )

    def test_no_study_sites_found(
        self,
        db_session: Session,
        item_with_pdf: Item,
        mock_pdf_path: Path,
    ) -> None:
        """Test handling when no study sites are extracted."""
        empty_result = ExtractionResult(
            pdf_path=mock_pdf_path,
            entities=[],
            total_sections_processed=5,
            extraction_metadata={
                "total_entities": 0,
                "coordinates": 0,
                "spatial_relations": 0,
                "locations": 0,
                "clusters": 0,
            },
            doc=None,
            title="Test Study with No Sites",
            cluster_info={},
            average_text_quality=0.85,
            section_quality_scores={},
        )

        with patch("app.tasks.extract.PipelineFactory.create_pipeline_for_api") as mock_factory:
            mock_pipeline = MagicMock()
            mock_pipeline.extract_from_pdf.return_value = empty_result
            mock_factory.return_value = mock_pipeline

            result = extract_study_site_task(
                item_id=str(item_with_pdf.id),
                user_id=str(item_with_pdf.owner_id),
                is_superuser=True,
                force=False,
                _test_session=db_session,
            )

            assert result["status"] == "not_found"
            assert result["count"] == 0
            assert "No study sites found" in result["message"]

    def test_permission_denied(self, db_session: Session, item_with_pdf: Item) -> None:
        """Test that non-owner cannot extract study sites from item."""
        other_user_id = uuid.uuid4()

        with pytest.raises(PermissionError):
            extract_study_site_task(
                item_id=str(item_with_pdf.id),
                user_id=str(other_user_id),
                is_superuser=False,
                force=False,
                _test_session=db_session,
            )

    def test_location_deduplication(
        self,
        db_session: Session,
        item_with_pdf: Item,
        mock_pdf_path: Path,
    ) -> None:
        """Test that identical coordinates share the same Location record."""
        # Create result with duplicate coordinates
        entity_1 = GeoEntity(
            text="Site 1",
            entity_type="COORDINATE",
            confidence=0.9,
            section="methods",
            context="Context 1",
            coordinates=(-0.5, -78.5),
            start_char=0,
            end_char=6,
        )

        entity_2 = GeoEntity(
            text="Site 2",
            entity_type="GPE",
            confidence=0.8,
            section="results",
            context="Context 2",
            coordinates=(-0.5, -78.5),  # Same coordinates
            start_char=100,
            end_char=106,
        )

        result = ExtractionResult(
            pdf_path=mock_pdf_path,
            entities=[entity_1, entity_2],
            total_sections_processed=2,
            extraction_metadata={
                "total_entities": 2,
                "coordinates": 2,
                "spatial_relations": 0,
                "locations": 1,
                "clusters": 1,
            },
            doc=None,
            title="Test Deduplication",
            cluster_info={"cluster_1": 2},
            average_text_quality=0.90,
            section_quality_scores={},
        )

        with patch("app.tasks.extract.PipelineFactory.create_pipeline_for_api") as mock_factory:
            mock_pipeline = MagicMock()
            mock_pipeline.extract_from_pdf.return_value = result
            mock_factory.return_value = mock_pipeline

            extract_study_site_task(
                item_id=str(item_with_pdf.id),
                user_id=str(item_with_pdf.owner_id),
                is_superuser=True,
                force=False,
                _test_session=db_session,
            )

            # Verify both sites exist
            db_session.expire_all()
            item = db_session.get(Item, item_with_pdf.id)
            assert item is not None
            assert item.study_sites is not None
            assert len(item.study_sites) == 2

            # Verify they share the same location (deduplication)
            location_ids = {site.location_id for site in item.study_sites}
            assert len(location_ids) == 1  # Only one unique location
