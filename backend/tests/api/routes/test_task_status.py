"""Tests for task status API endpoints."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest
from celery.result import AsyncResult

from app.core.config import settings
from app.models import Item
from app.models import StudySite
from maress_types import CoordinateExtractionMethod
from tests.utils.item import create_random_item

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from sqlmodel import Session


class TestTaskStatusEndpoint:
    """Test GET /api/v1/items/tasks/{task_id} endpoint."""

    def test_get_pending_task_status(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
    ) -> None:
        """Test retrieving status of a pending task."""
        task_id = str(uuid.uuid4())

        mock_result = Mock(spec=AsyncResult)
        mock_result.status = "PENDING"
        mock_result.ready.return_value = False
        mock_result.successful.return_value = False
        mock_result.failed.return_value = False

        with patch("app.api.routes.items.AsyncResult", return_value=mock_result):
            response = client.get(
                f"{settings.API_V1_STR}/items/tasks/{task_id}",
                headers=superuser_token_headers,
            )

            assert response.status_code == 200
            data = response.json()

            assert data["task_id"] == task_id
            assert data["status"] == "PENDING"
            assert data["ready"] is False
            assert data["successful"] is None

    def test_get_successful_task_status(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
    ) -> None:
        """Test retrieving status of a successfully completed task."""
        task_id = str(uuid.uuid4())
        item_id = str(uuid.uuid4())

        task_result = {
            "item_id": item_id,
            "study_site_ids": [str(uuid.uuid4())],
            "count": 1,
            "status": "created",
            "message": "Successfully created 1 study site(s)",
        }

        mock_result = Mock(spec=AsyncResult)
        mock_result.status = "SUCCESS"
        mock_result.ready.return_value = True
        mock_result.successful.return_value = True
        mock_result.failed.return_value = False
        mock_result.result = task_result

        with patch("app.api.routes.items.AsyncResult", return_value=mock_result):
            response = client.get(
                f"{settings.API_V1_STR}/items/tasks/{task_id}",
                headers=superuser_token_headers,
            )

            assert response.status_code == 200
            data = response.json()

            assert data["task_id"] == task_id
            assert data["status"] == "SUCCESS"
            assert data["ready"] is True
            assert data["successful"] is True
            assert "result" in data
            assert data["result"]["item_id"] == item_id
            assert data["result"]["count"] == 1

    def test_get_failed_task_status(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
    ) -> None:
        """Test retrieving status of a failed task."""
        task_id = str(uuid.uuid4())

        error_info = {
            "reason": "file_not_found",
            "message": "PDF file not found",
            "item_id": str(uuid.uuid4()),
        }

        mock_result = Mock(spec=AsyncResult)
        mock_result.status = "FAILURE"
        mock_result.ready.return_value = True
        mock_result.successful.return_value = False
        mock_result.failed.return_value = True
        mock_result.info = error_info

        with patch("app.api.routes.items.AsyncResult", return_value=mock_result):
            response = client.get(
                f"{settings.API_V1_STR}/items/tasks/{task_id}",
                headers=superuser_token_headers,
            )

            assert response.status_code == 200
            data = response.json()

            assert data["task_id"] == task_id
            assert data["status"] == "FAILURE"
            assert data["ready"] is True
            assert data["failed"] is True
            assert "error" in data
            assert data["error"]["reason"] == "file_not_found"

    def test_get_task_status_requires_auth(
        self,
        client: TestClient,
    ) -> None:
        """Test that task status endpoint requires authentication."""
        task_id = str(uuid.uuid4())

        response = client.get(
            f"{settings.API_V1_STR}/items/tasks/{task_id}",
        )

        assert response.status_code == 401


class TestBatchTaskStatusEndpoint:
    """Test GET /api/v1/items/tasks/batch/ endpoint."""

    def test_get_batch_task_status_multiple_tasks(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
    ) -> None:
        """Test retrieving status of multiple tasks."""
        task_ids = [str(uuid.uuid4()) for _ in range(3)]
        task_ids_str = ",".join(task_ids)

        # Mock results for 3 tasks: SUCCESS, PENDING, FAILURE
        def mock_async_result(task_id: str, *args, **kwargs) -> Mock:
            idx = task_ids.index(task_id)
            mock = Mock(spec=AsyncResult)

            if idx == 0:  # SUCCESS
                mock.status = "SUCCESS"
                mock.ready.return_value = True
                mock.successful.return_value = True
                mock.result = {
                    "item_id": str(uuid.uuid4()),
                    "count": 2,
                    "status": "created",
                }
            elif idx == 1:  # PENDING
                mock.status = "PENDING"
                mock.ready.return_value = False
                mock.successful.return_value = False
            else:  # FAILURE
                mock.status = "FAILURE"
                mock.ready.return_value = True
                mock.successful.return_value = False

            return mock

        with patch("app.api.routes.items.AsyncResult", side_effect=mock_async_result):
            response = client.get(
                f"{settings.API_V1_STR}/items/tasks/batch/?task_ids={task_ids_str}",
                headers=superuser_token_headers,
            )

            assert response.status_code == 200
            data = response.json()

            # Verify all tasks are in response
            assert "tasks" in data
            assert len(data["tasks"]) == 3
            assert all(tid in data["tasks"] for tid in task_ids)

            # Verify summary statistics
            assert "summary" in data
            summary = data["summary"]
            assert summary["total"] == 3
            assert summary["success"] == 1
            assert summary["pending"] == 1
            assert summary["failure"] == 1
            assert summary["ready"] == 2
            assert summary["successful"] == 1
            assert summary["failed"] == 1

    def test_batch_task_status_empty_ids(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
    ) -> None:
        """Test that empty task IDs returns error."""
        response = client.get(
            f"{settings.API_V1_STR}/items/tasks/batch/?task_ids=",
            headers=superuser_token_headers,
        )

        assert response.status_code == 400
        data = response.json()
        assert "No task IDs provided" in data["detail"]

    def test_batch_task_status_too_many_ids(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
    ) -> None:
        """Test that too many task IDs returns error."""
        task_ids = ",".join([str(uuid.uuid4()) for _ in range(101)])

        response = client.get(
            f"{settings.API_V1_STR}/items/tasks/batch/?task_ids={task_ids}",
            headers=superuser_token_headers,
        )

        assert response.status_code == 400
        data = response.json()
        assert "Maximum 100 tasks" in data["detail"]

    def test_batch_task_status_comma_separated(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
    ) -> None:
        """Test handling of comma-separated task IDs with spaces."""
        task_ids = [str(uuid.uuid4()) for _ in range(2)]
        # Add spaces around commas
        task_ids_str = f" {task_ids[0]} , {task_ids[1]} "

        mock_result = Mock(spec=AsyncResult)
        mock_result.status = "SUCCESS"
        mock_result.ready.return_value = True
        mock_result.successful.return_value = True
        mock_result.result = {"status": "created"}

        with patch("app.api.routes.items.AsyncResult", return_value=mock_result):
            response = client.get(
                f"{settings.API_V1_STR}/items/tasks/batch/?task_ids={task_ids_str}",
                headers=superuser_token_headers,
            )

            assert response.status_code == 200
            data = response.json()

            # Should handle spaces correctly
            assert len(data["tasks"]) == 2


class TestExtractionSummaryEndpoint:
    """Test GET /api/v1/items/tasks/summary/ endpoint."""

    def test_get_extraction_summary(
        self,
        client: TestClient,
        db_session: Session,
        normal_user_token_headers: dict[str, str],
    ) -> None:
        """Test retrieving extraction summary statistics."""
        # Create items with study sites
        from app.crud import create_study_site
        from app.models import StudySiteCreate
        from pydantic_extra_types.coordinate import Latitude, Longitude

        # Create 3 items, 2 with study sites
        item1 = create_random_item(db_session)
        item2 = create_random_item(db_session)
        item3 = create_random_item(db_session)

        # Add study sites to item1 and item2
        site1 = StudySiteCreate(
            name="Site 1",
            latitude=Latitude(-0.5),
            longitude=Longitude(-78.5),
            confidence_score=0.9,
            context="Context 1",
            extraction_method=CoordinateExtractionMethod.REGEX,
            section="methods",
            source_type="text",
            validation_score=0.85,
            item_id=item1.id,
        )
        create_study_site(db_session, site1)

        site2 = StudySiteCreate(
            name="Site 2",
            latitude=Latitude(-12.0),
            longitude=Longitude(-77.0),
            confidence_score=0.8,
            context="Context 2",
            extraction_method=CoordinateExtractionMethod.TABLE_PARSING,
            section="methods",
            source_type="table",
            validation_score=0.80,
            item_id=item2.id,
        )
        create_study_site(db_session, site2)

        response = client.get(
            f"{settings.API_V1_STR}/items/tasks/summary/",
            headers=normal_user_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify summary statistics
        assert "total_study_sites" in data
        assert data["total_study_sites"] >= 2

        assert "total_items" in data
        assert data["total_items"] >= 3

        assert "items_with_study_sites" in data
        assert data["items_with_study_sites"] >= 2

        assert "coverage_percentage" in data
        assert isinstance(data["coverage_percentage"], float)

        assert "average_confidence" in data
        assert isinstance(data["average_confidence"], float)

        assert "average_validation_score" in data
        assert isinstance(data["average_validation_score"], float)

        assert "by_extraction_method" in data
        assert isinstance(data["by_extraction_method"], dict)

    def test_extraction_summary_empty_database(
        self,
        client: TestClient,
        superuser_token_headers: dict[str, str],
    ) -> None:
        """Test summary with no study sites."""
        response = client.get(
            f"{settings.API_V1_STR}/items/tasks/summary/",
            headers=superuser_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Should return zeros for empty database
        assert data["total_study_sites"] == 0
        assert data["average_confidence"] == 0
        assert data["average_validation_score"] == 0

    def test_extraction_summary_requires_auth(
        self,
        client: TestClient,
    ) -> None:
        """Test that summary endpoint requires authentication."""
        response = client.get(
            f"{settings.API_V1_STR}/items/tasks/summary/",
        )

        assert response.status_code == 401

    def test_extraction_summary_by_method_breakdown(
        self,
        client: TestClient,
        db_session: Session,
        superuser_token_headers: dict[str, str],
    ) -> None:
        """Test that summary breaks down sites by extraction method."""
        from app.crud import create_study_site
        from app.models import StudySiteCreate
        from pydantic_extra_types.coordinate import Latitude, Longitude

        item = create_random_item(db_session)

        # Create sites with different extraction methods
        methods = [
            CoordinateExtractionMethod.REGEX,
            CoordinateExtractionMethod.TABLE_PARSING,
            CoordinateExtractionMethod.GEOCODED,
        ]

        for i, method in enumerate(methods):
            site = StudySiteCreate(
                name=f"Site {i}",
                latitude=Latitude(-0.5 - i),
                longitude=Longitude(-78.5 - i),
                confidence_score=0.8,
                context=f"Context {i}",
                extraction_method=method,
                section="methods",
                source_type="text",
                validation_score=0.8,
                item_id=item.id,
            )
            create_study_site(db_session, site)

        response = client.get(
            f"{settings.API_V1_STR}/items/tasks/summary/",
            headers=superuser_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify breakdown by method
        by_method = data["by_extraction_method"]
        assert "regex" in by_method or "REGEX" in by_method
        assert "table_parsing" in by_method or "TABLE_PARSING" in by_method
        assert "geocoded" in by_method or "GEOCODED" in by_method


class TestTaskStatusIntegration:
    """Integration tests for task status with actual extraction."""

    def test_task_status_after_extraction(
        self,
        client: TestClient,
        db_session: Session,
        superuser_token_headers: dict[str, str],
        tmp_path,
    ) -> None:
        """Test checking task status after triggering extraction."""
        from pathlib import Path

        # Create item with PDF
        item = create_random_item(db_session)
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_text("mock pdf")
        item.attachment = str(pdf_path)
        db_session.add(item)
        db_session.commit()

        # Mock the extraction result
        with patch("app.tasks.extract.StudySiteExtractor") as mock_extractor_class:
            from app.nlp.find_my_home import (
                CoordinateCandidate,
                StudySiteResult,
            )
            from pydantic_extra_types.coordinate import Latitude, Longitude

            mock_site = CoordinateCandidate(
                latitude=Latitude(-0.5),
                longitude=Longitude(-78.5),
                confidence_score=0.9,
                priority_score=100,
                source_type="text",
                context="Test context",
                section="methods",
                name="Test Site",
                extraction_method=CoordinateExtractionMethod.REGEX,
            )

            mock_result = StudySiteResult(
                coordinates=[mock_site],
                locations=[],
                validation_score=0.85,
                primary_study_site=mock_site,
                cluster_info={"cluster_0": 1},
            )

            mock_extractor = mock_extractor_class.return_value
            mock_extractor.extract_study_sites.return_value = mock_result

            # Trigger extraction
            response = client.post(
                f"{settings.API_V1_STR}/items/study_sites/?id={item.id}",
                headers=superuser_token_headers,
            )

            assert response.status_code == 202
            data = response.json()
            task_id = data["data"][0]["task_id"]

            # Check task status (would be async in real scenario)
            # For now, just verify the endpoint works
            status_response = client.get(
                f"{settings.API_V1_STR}/items/tasks/{task_id}",
                headers=superuser_token_headers,
            )

            assert status_response.status_code == 200
