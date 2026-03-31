from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.config import settings
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
