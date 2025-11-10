# pyright: reportAny=false
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from app import crud
from app.core.config import settings
from app.models import Item
from app.models import User, UserUpdate
from tests.factories import ItemFactory
from tests.utils.item import create_random_item

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from sqlmodel import Session

# TODO: Add tests for filtering, pagination, and sorting
# TODO: Add tests for more zotero import actions


def test_create_item(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    data = ItemFactory.build().model_dump(exclude_unset=True, mode="json")
    response = client.post(
        f"{settings.API_V1_STR}/items/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["title"] == data["title"]
    assert content["description"] == data["description"]
    assert "id" in content
    assert "owner_id" in content


def test_read_item(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db_session: Session,
) -> None:
    item = create_random_item(db_session)
    assert isinstance(item, Item)
    response = client.get(
        f"{settings.API_V1_STR}/items/{item.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["title"] == item.title
    assert content["description"] == item.description
    assert content["id"] == str(item.id)
    assert content["owner_id"] == str(item.owner_id)


def test_read_item_not_found(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/items/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Item not found"


def test_read_item_not_enough_permissions(
    client: TestClient,
    db_session: Session,
) -> None:
    from tests.utils.user import authentication_token_from_email, create_test_user

    item = create_random_item(db_session)
    other_user = create_test_user(db_session)
    token_headers = authentication_token_from_email(
        client=client,
        email=other_user.email,
        db=db_session,
    )
    assert isinstance(item, Item)
    response = client.get(
        f"{settings.API_V1_STR}/items/{item.id}",
        headers=token_headers,
    )
    assert response.status_code == 400, response.text
    content = response.json()
    assert content["detail"] == "Not enough permissions"


def test_read_items(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db_session: Session,
) -> None:
    create_random_item(db_session)
    create_random_item(db_session)
    response = client.get(
        f"{settings.API_V1_STR}/items/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert len(content["data"]) >= 2


def test_import_zotero_items(
    client: TestClient,
    db_session: Session,
    test_user: User,
    normal_user_token_headers: dict[str, str],
) -> None:
    user_in = UserUpdate(
        zotero_id=settings.ZOTERO_USER_ID,
        enc_zotero_api_key=settings.ZOTERO_API_KEY,
    )
    user = crud.update_user(
        session=db_session,
        db_user=test_user,
        user_in=user_in,
    )
    assert user is not None
    assert user.zotero_id is not None

    response = client.get(
        f"{settings.API_V1_STR}/items/import_from_zotero/?skip=0&limit=100&reload=false&library_type=group",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert "data" in content
    assert isinstance(content["data"], list)
    assert len(content["data"]) > 0, f"Response content: {content}"
    for item in content["data"]:
        assert "id" in item
        assert "title" in item
        assert "description" in item
        assert "owner_id" in item


def test_update_item(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db_session: Session,
) -> None:
    item = create_random_item(db_session)
    data = {"title": "Updated title", "description": "Updated description"}
    response = client.put(
        f"{settings.API_V1_STR}/items/{item.id}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["title"] == data["title"]
    assert content["description"] == data["description"]
    assert content["id"] == str(item.id)
    assert content["owner_id"] == str(item.owner_id)


def test_update_item_not_found(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    data = {"title": "Updated title", "description": "Updated description"}
    response = client.put(
        f"{settings.API_V1_STR}/items/{uuid.uuid4()}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Item not found"


def test_update_item_not_enough_permissions(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    test_superuser: User,
    test_user: User,
    db_session: Session,
) -> None:
    item = create_random_item(db_session)
    # Make sure the item is owned by a different user
    if item.owner_id == test_user.id:
        item.owner_id = test_superuser.id
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)
    data = {"title": "Updated title", "description": "Updated description"}
    response = client.put(
        f"{settings.API_V1_STR}/items/{item.id}",
        headers=normal_user_token_headers,
        json=data,
    )
    assert response.status_code == 400
    content = response.json()
    assert content["detail"] == "Not enough permissions"


def test_delete_item(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db_session: Session,
) -> None:
    item = create_random_item(db_session)
    response = client.delete(
        f"{settings.API_V1_STR}/items/{item.id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["message"] == "Item deleted successfully"


def test_delete_item_not_found(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = client.delete(
        f"{settings.API_V1_STR}/items/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    content = response.json()
    assert content["detail"] == "Item not found"


def test_delete_item_not_enough_permissions(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db_session: Session,
    test_user: User,
    test_superuser: User,
) -> None:
    item = create_random_item(db_session)
    if item.owner_id == test_user.id:
        item.owner_id = test_superuser.id
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)
    response = client.delete(
        f"{settings.API_V1_STR}/items/{item.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 400
    content = response.json()
    assert content["detail"] == "Not enough permissions"
