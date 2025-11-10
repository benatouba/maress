"""Tests for study site extraction task."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from pydantic_extra_types.coordinate import Latitude, Longitude

from app.models.items import Item
from app.models.study_sites import StudySite
from app.nlp.find_my_home import (
    CoordinateCandidate,
    StudySiteResult,
)
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
def mock_single_site_result() -> StudySiteResult:
    """Mock extraction result with a single study site."""
    primary = CoordinateCandidate(
        latitude=Latitude(-0.5),
        longitude=Longitude(-78.5),
        confidence_score=0.9,
        priority_score=100,
        source_type=CoordinateSourceType.TEXT,
        context="Study site located at coordinates",
        section=PaperSections.METHODS,
        name="Main Site",
        extraction_method=CoordinateExtractionMethod.REGEX,
    )

    return StudySiteResult(
        coordinates=[primary],
        locations=[],
        validation_score=0.85,
        primary_study_site=primary,
        cluster_info={"cluster_0": 1},
    )


@pytest.fixture
def mock_multi_site_result() -> StudySiteResult:
    """Mock extraction result with multiple study sites across different clusters."""
    # Primary site - Ecuador
    primary = CoordinateCandidate(
        latitude=Latitude(-0.5),
        longitude=Longitude(-78.5),
        confidence_score=0.9,
        priority_score=100,
        source_type=CoordinateSourceType.TEXT,
        context="Study site located at coordinates",
        section=PaperSections.METHODS,
        name="Ecuador Site",
        extraction_method=CoordinateExtractionMethod.REGEX,
        cluster_label=0,
    )

    # Second site - Ecuador (same cluster)
    site_2 = CoordinateCandidate(
        latitude=Latitude(-0.52),
        longitude=Longitude(-78.48),
        confidence_score=0.85,
        priority_score=80,
        source_type=CoordinateSourceType.TEXT,
        context="Additional sampling location",
        section=PaperSections.METHODS,
        name="Ecuador Site 2",
        extraction_method=CoordinateExtractionMethod.NER,
        cluster_label=0,
    )

    # Third site - Peru (different cluster)
    site_3 = CoordinateCandidate(
        latitude=Latitude(-12.0),
        longitude=Longitude(-77.0),
        confidence_score=0.80,
        priority_score=100,
        source_type=CoordinateSourceType.TABLE,
        context="Table 1, Row 1",
        section=PaperSections.METHODS,
        name="Peru Site",
        extraction_method=CoordinateExtractionMethod.TABLE_PARSING,
        cluster_label=1,
    )

    # Fourth site - Chile (different cluster)
    site_4 = CoordinateCandidate(
        latitude=Latitude(-33.5),
        longitude=Longitude(-70.6),
        confidence_score=0.88,
        priority_score=80,
        source_type=CoordinateSourceType.TEXT,
        context="Geocoded from Santiago mention",
        section=PaperSections.ABSTRACT,
        name="Chile Site",
        extraction_method=CoordinateExtractionMethod.GEOCODED,
        cluster_label=2,
    )

    return StudySiteResult(
        coordinates=[primary, site_2, site_3, site_4],
        locations=[],
        validation_score=0.90,
        primary_study_site=primary,
        cluster_info={"cluster_0": 2, "cluster_1": 1, "cluster_2": 1},
    )


class TestExtractStudySiteTask:
    """Test suite for study site extraction task."""

    def test_extract_single_study_site(
        self,
        db_session: Session,
        item_with_pdf: Item,
        mock_single_site_result: StudySiteResult,
    ) -> None:
        """Test extraction and storage of a single study site."""
        with patch("app.tasks.extract.StudySiteExtractor.extract_study_sites") as mock_extract:
            mock_extract.return_value = mock_single_site_result

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
            assert study_site.extraction_method == CoordinateExtractionMethod.REGEX

    def test_extract_multiple_study_sites(
        self,
        db_session: Session,
        item_with_pdf: Item,
        mock_multi_site_result: StudySiteResult,
    ) -> None:
        """Test extraction and storage of multiple study sites from different clusters.

        This is the critical fix - verifying all sites are saved, not just primary.
        """
        with patch(
            "app.tasks.extract.StudySiteExtractor.extract_study_sites",
        ) as mock_extract:
            mock_extract.return_value = mock_multi_site_result

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
            assert "1 primary + 3 additional" in result["message"]
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

            # Verify different extraction methods
            methods = {site.extraction_method for site in sites}
            assert CoordinateExtractionMethod.REGEX in methods
            assert CoordinateExtractionMethod.NER in methods
            assert CoordinateExtractionMethod.TABLE_PARSING in methods
            assert CoordinateExtractionMethod.GEOCODED in methods

    def test_skip_existing_sites_without_force(
        self,
        db_session: Session,
        item_with_pdf: Item,
        mock_single_site_result: StudySiteResult,
    ) -> None:
        """Test that extraction is skipped when sites exist and force=False."""
        # Create existing study site
        from app.crud import create_study_site
        from app.models.study_sites import StudySiteCreate

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

        with patch(
            "app.tasks.extract.StudySiteExtractor.extract_study_sites",
        ) as mock_extract:
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
            mock_extract.assert_not_called()

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
        mock_multi_site_result: StudySiteResult,
    ) -> None:
        """Test that force=True triggers re-extraction even with existing sites."""
        # Create existing study site
        from app.crud import create_study_site
        from app.models.study_sites import StudySiteCreate

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

        with patch(
            "app.tasks.extract.StudySiteExtractor.extract_study_sites",
        ) as mock_extract:
            mock_extract.return_value = mock_multi_site_result

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
            mock_extract.assert_called_once()

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
    ) -> None:
        """Test handling when no study sites are extracted."""
        empty_result = StudySiteResult(
            coordinates=[],
            locations=[],
            validation_score=0.0,
            primary_study_site=None,
            cluster_info={},
        )

        with patch(
            "app.tasks.extract.StudySiteExtractor.extract_study_sites",
        ) as mock_extract:
            mock_extract.return_value = empty_result

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
    ) -> None:
        """Test that identical coordinates share the same Location record."""
        # Create result with duplicate coordinates
        site_1 = CoordinateCandidate(
            latitude=Latitude(-0.5),
            longitude=Longitude(-78.5),
            confidence_score=0.9,
            priority_score=100,
            source_type=CoordinateSourceType.TEXT,
            context="Context 1",
            section=PaperSections.METHODS,
            name="Site 1",
            extraction_method=CoordinateExtractionMethod.REGEX,
        )

        site_2 = CoordinateCandidate(
            latitude=Latitude(-0.5),  # Same coordinates
            longitude=Longitude(-78.5),  # Same coordinates
            confidence_score=0.8,
            priority_score=80,
            source_type=CoordinateSourceType.TEXT,
            context="Context 2",
            section=PaperSections.RESULTS,
            name="Site 2",
            extraction_method=CoordinateExtractionMethod.NER,
        )

        result = StudySiteResult(
            coordinates=[site_1, site_2],
            locations=[],
            validation_score=0.9,
            primary_study_site=site_1,
            cluster_info={"cluster_0": 2},
        )

        with patch(
            "app.tasks.extract.StudySiteExtractor.extract_study_sites",
        ) as mock_extract:
            mock_extract.return_value = result

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
