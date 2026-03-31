from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic_extra_types.coordinate import Latitude, Longitude

from app.core.config import settings
from app.crud import create_study_site
from app.models import StudySiteCreate
from maress_types import CoordinateExtractionMethod, CoordinateSourceType, PaperSections
from tests.utils.item import create_random_item, create_random_tag

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from sqlmodel import Session


def test_anonymous_can_read_tags(
    client: TestClient,
    db_session: Session,
) -> None:
    tag = create_random_tag(db_session)

    response = client.get(f"{settings.API_V1_STR}/tags/")
    assert response.status_code == 200
    content = response.json()

    assert "data" in content
    assert "count" in content
    assert any(entry["id"] == tag.id for entry in content["data"])


def test_anonymous_can_read_single_tag(
    client: TestClient,
    db_session: Session,
) -> None:
    tag = create_random_tag(db_session)

    response = client.get(f"{settings.API_V1_STR}/tags/{tag.id}")
    assert response.status_code == 200
    content = response.json()

    assert content["id"] == tag.id
    assert content["name"] == tag.name


def test_tag_mutations_require_authentication(
    client: TestClient,
    db_session: Session,
) -> None:
    item = create_random_item(db_session)
    tag = create_random_tag(db_session)

    create_response = client.post(
        f"{settings.API_V1_STR}/tags/",
        json={"name": "unauthorized-create", "item_ids": []},
    )
    assert create_response.status_code == 401

    update_response = client.put(
        f"{settings.API_V1_STR}/tags/{tag.id}",
        json={"name": "unauthorized-update", "item_ids": []},
    )
    assert update_response.status_code == 401

    delete_response = client.delete(f"{settings.API_V1_STR}/tags/{tag.id}")
    assert delete_response.status_code == 401

    add_item_response = client.post(
        f"{settings.API_V1_STR}/tags/{tag.id}/items/{item.id}",
    )
    assert add_item_response.status_code == 401

    remove_item_response = client.delete(
        f"{settings.API_V1_STR}/tags/{tag.id}/items/{item.id}",
    )
    assert remove_item_response.status_code == 401


def test_anonymous_can_read_map_points(client: TestClient) -> None:
    response = client.get(f"{settings.API_V1_STR}/study-sites/map-points")
    assert response.status_code == 200
    content = response.json()

    assert "data" in content
    assert "count" in content


def test_anonymous_can_read_map_item_summary(client: TestClient) -> None:
    response = client.get(f"{settings.API_V1_STR}/items/map-summary")
    assert response.status_code == 200
    content = response.json()

    assert "data" in content
    assert "count" in content
    if content["data"]:
        sample = content["data"][0]
        assert "id" in sample
        assert "title" in sample
        assert "study_site_count" in sample


def test_non_owner_can_read_map_points(
    client: TestClient,
    db_session: Session,
    normal_user_token_headers: dict[str, str],
) -> None:
    item = create_random_item(db_session)

    site = StudySiteCreate(
        name="Public map point",
        latitude=Latitude(-10.5),
        longitude=Longitude(-70.2),
        confidence_score=0.9,
        context="Public visibility test",
        extraction_method=CoordinateExtractionMethod.REGEX,
        section=PaperSections.METHODS,
        source_type=CoordinateSourceType.TEXT,
        validation_score=0.8,
        item_id=item.id,
    )
    create_study_site(db_session, site)
    db_session.commit()

    response = client.get(
        f"{settings.API_V1_STR}/study-sites/map-points",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    content = response.json()

    assert "data" in content
    assert any(point["item_id"] == str(item.id) for point in content["data"])


def test_map_points_supports_bbox_filter(
    client: TestClient,
    db_session: Session,
) -> None:
    item = create_random_item(db_session)

    inside = StudySiteCreate(
        name="Inside viewport",
        latitude=Latitude(10.0),
        longitude=Longitude(20.0),
        confidence_score=0.9,
        context="inside",
        extraction_method=CoordinateExtractionMethod.REGEX,
        section=PaperSections.METHODS,
        source_type=CoordinateSourceType.TEXT,
        validation_score=0.8,
        item_id=item.id,
    )

    outside = StudySiteCreate(
        name="Outside viewport",
        latitude=Latitude(-45.0),
        longitude=Longitude(120.0),
        confidence_score=0.7,
        context="outside",
        extraction_method=CoordinateExtractionMethod.REGEX,
        section=PaperSections.METHODS,
        source_type=CoordinateSourceType.TEXT,
        validation_score=0.6,
        item_id=item.id,
    )

    create_study_site(db_session, inside)
    create_study_site(db_session, outside)
    db_session.commit()

    response = client.get(
        f"{settings.API_V1_STR}/study-sites/map-points",
        params={"bbox": "15,5,25,15"},
    )

    assert response.status_code == 200
    content = response.json()

    names = [point["name"] for point in content["data"]]
    assert "Inside viewport" in names
    assert "Outside viewport" not in names


def test_map_points_rejects_invalid_bbox(client: TestClient) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/study-sites/map-points",
        params={"bbox": "not-a-bbox"},
    )

    assert response.status_code == 400


def test_manual_study_site_creation_requires_authentication(
    client: TestClient,
    db_session: Session,
) -> None:
    item = create_random_item(db_session)

    response = client.post(
        f"{settings.API_V1_STR}/study-sites/items/{item.id}/study-sites",
        json={
            "name": "Unauthorized manual site",
            "latitude": 10.0,
            "longitude": 20.0,
            "context": "unauthorized",
            "confidence_score": 1.0,
            "validation_score": 1.0,
        },
    )
    assert response.status_code == 401
