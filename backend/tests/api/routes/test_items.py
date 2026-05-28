# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app import crud
from app.core.config import settings
from app.models import Item, User, UserUpdate
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


def test_read_item_non_owner_hides_attachment(
    client: TestClient,
    db_session: Session,
) -> None:
    from tests.utils.user import authentication_token_from_email, create_test_user

    item = create_random_item(db_session)
    item.attachment = "/tmp/licensed.pdf"
    db_session.add(item)
    db_session.commit()
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
    assert response.status_code == 200, response.text
    content = response.json()
    assert content["id"] == str(item.id)
    assert content["attachment"] is None


def test_read_items_non_owner_cannot_see_attachments(
    client: TestClient,
    db_session: Session,
    test_user: User,
    normal_user_token_headers: dict[str, str],
) -> None:
    own_item_in = ItemFactory.build()
    own_item = crud.create_item(
        session=db_session,
        item_in=own_item_in,
        owner_id=test_user.id,
    )
    assert isinstance(own_item, Item)
    own_item.attachment = "/tmp/own.pdf"

    other_item = create_random_item(db_session)
    other_item.attachment = "/tmp/foreign.pdf"

    db_session.add(own_item)
    db_session.add(other_item)
    db_session.commit()

    response = client.get(
        f"{settings.API_V1_STR}/items/",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    content = response.json()

    own_response_item = next((entry for entry in content["data"] if entry["id"] == str(own_item.id)), None)
    other_response_item = next((entry for entry in content["data"] if entry["id"] == str(other_item.id)), None)

    assert own_response_item is not None
    assert other_response_item is not None
    assert own_response_item["attachment"] == "/tmp/own.pdf"
    assert other_response_item["attachment"] is None


def test_read_search_non_owner_cannot_see_attachments(
    client: TestClient,
    db_session: Session,
    normal_user_token_headers: dict[str, str],
) -> None:
    item = create_random_item(db_session)
    item.title = "Visibility Search Item"
    item.attachment = "/tmp/licensed.pdf"
    db_session.add(item)
    db_session.commit()

    response = client.get(
        f"{settings.API_V1_STR}/items/search/",
        headers=normal_user_token_headers,
        params={"title": "Visibility Search Item"},
    )
    assert response.status_code == 200
    content = response.json()

    target = next((entry for entry in content["data"] if entry["id"] == str(item.id)), None)
    assert target is not None
    assert target["attachment"] is None


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


def test_read_items_includes_doi_value(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db_session: Session,
) -> None:
    item = create_random_item(db_session)
    item.doi = "10.1234/example-doi"
    db_session.add(item)
    db_session.commit()

    response = client.get(
        f"{settings.API_V1_STR}/items/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()

    target = next((entry for entry in content["data"] if entry["id"] == str(item.id)), None)
    assert target is not None
    assert target["DOI"] == "10.1234/example-doi"


def test_read_items_includes_issn_value(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db_session: Session,
) -> None:
    item = create_random_item(db_session)
    item.issn = "1234-5678"
    db_session.add(item)
    db_session.commit()

    response = client.get(
        f"{settings.API_V1_STR}/items/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()

    target = next((entry for entry in content["data"] if entry["id"] == str(item.id)), None)
    assert target is not None
    assert target["ISSN"] == "1234-5678"


def test_read_items_title_fulltext_search_mode_uses_parsed_text(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db_session: Session,
) -> None:
    target_item = create_random_item(db_session)
    target_item.title = "Unrelated title"
    target_item.parsed_text = "The study area focuses on Laguna Verde hydrology"

    control_item = create_random_item(db_session)
    control_item.title = "Another paper"
    control_item.parsed_text = "No matching terms here"

    db_session.add(target_item)
    db_session.add(control_item)
    db_session.commit()

    response = client.get(
        f"{settings.API_V1_STR}/items/",
        headers=superuser_token_headers,
        params={"search": "laguna verde", "search_mode": "title+fulltext", "limit": 50},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    ids = {entry["id"] for entry in data}
    assert str(target_item.id) in ids
    assert str(control_item.id) not in ids


def test_read_items_map_summary_title_fulltext_search_mode_uses_parsed_text(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db_session: Session,
) -> None:
    target_item = create_random_item(db_session)
    target_item.title = "Map paper"
    target_item.parsed_text = "Contains Atacama Basin sediment analysis"

    control_item = create_random_item(db_session)
    control_item.title = "Control map paper"
    control_item.parsed_text = "No relevant map search terms"

    db_session.add(target_item)
    db_session.add(control_item)
    db_session.commit()

    response = client.get(
        f"{settings.API_V1_STR}/items/map-summary",
        headers=superuser_token_headers,
        params={"search": "atacama basin", "search_mode": "title+fulltext", "limit": 50},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    ids = {entry["id"] for entry in data}
    assert str(target_item.id) in ids
    assert str(control_item.id) not in ids


def test_read_items_anonymous_hides_attachment(
    client: TestClient,
    db_session: Session,
) -> None:
    item = create_random_item(db_session)
    item.attachment = "/tmp/licensed.pdf"
    db_session.add(item)
    db_session.commit()

    response = client.get(f"{settings.API_V1_STR}/items/")
    assert response.status_code == 200
    content = response.json()

    target = next((entry for entry in content["data"] if entry["id"] == str(item.id)), None)
    assert target is not None
    assert target["attachment"] is None


def test_read_item_anonymous_hides_attachment(
    client: TestClient,
    db_session: Session,
) -> None:
    item = create_random_item(db_session)
    item.attachment = "/tmp/licensed.pdf"
    db_session.add(item)
    db_session.commit()

    response = client.get(f"{settings.API_V1_STR}/items/{item.id}")
    assert response.status_code == 200
    content = response.json()
    assert content["id"] == str(item.id)
    assert content["attachment"] is None


@pytest.mark.skip(reason="Requires valid Zotero API credentials - external service dependency")
def test_import_zotero_items(
    client: TestClient,
    db_session: Session,
    test_user: User,
    normal_user_token_headers: dict[str, str],
) -> None:
    """Test importing items from Zotero API.

    Note: This test is skipped by default because it requires:
    - Valid Zotero API credentials (ZOTERO_USER_ID and ZOTERO_API_KEY)
    - External network access to Zotero API
    - Proper API permissions

    To run this test, ensure credentials are configured and remove the @pytest.mark.skip decorator.
    """
    user_in = UserUpdate(
        zotero_id=settings.ZOTERO_USER_ID,
        zotero_api_key=settings.ZOTERO_API_KEY,
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


def test_delete_items_bulk_selected(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db_session: Session,
) -> None:
    item_one = create_random_item(db_session)
    item_two = create_random_item(db_session)

    response = client.delete(
        f"{settings.API_V1_STR}/items/bulk",
        headers=superuser_token_headers,
        params=[("item_ids", str(item_one.id)), ("item_ids", str(item_two.id))],
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Deleted 2 item(s) successfully"
    assert db_session.get(Item, item_one.id) is None
    assert db_session.get(Item, item_two.id) is None


def test_delete_items_bulk_all_deletes_only_owned_for_normal_user(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db_session: Session,
    test_user: User,
    test_superuser: User,
) -> None:
    own_item_in = ItemFactory.build()
    own_item = crud.create_item(
        session=db_session,
        item_in=own_item_in,
        owner_id=test_user.id,
    )

    other_item_in = ItemFactory.build()
    other_item = crud.create_item(
        session=db_session,
        item_in=other_item_in,
        owner_id=test_superuser.id,
    )

    response = client.delete(
        f"{settings.API_V1_STR}/items/bulk",
        headers=normal_user_token_headers,
        params={"all": "true"},
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Deleted 1 item(s) successfully"
    assert db_session.get(Item, own_item.id) is None
    assert db_session.get(Item, other_item.id) is not None


def test_delete_items_bulk_requires_selection_or_all(
    client: TestClient,
    superuser_token_headers: dict[str, str],
) -> None:
    response = client.delete(
        f"{settings.API_V1_STR}/items/bulk",
        headers=superuser_token_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Provide item_ids or set all=true"


def test_start_extract_requires_authentication(client: TestClient) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/items/study_sites/",
        json={"item_ids": None, "force": False},
    )
    assert response.status_code == 401


def test_start_enrich_requires_authentication(client: TestClient) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/items/enrich/",
        json={"item_ids": None},
    )
    assert response.status_code == 401


def test_download_attachments_requires_authentication(client: TestClient) -> None:
    response = client.post(f"{settings.API_V1_STR}/items/import_file_zotero/")
    assert response.status_code == 401
