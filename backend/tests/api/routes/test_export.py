from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

from geoalchemy2.shape import from_shape
from pydantic_extra_types.coordinate import Latitude, Longitude
from shapely.geometry import MultiPolygon, Polygon

from app.core.config import settings
from app.crud import create_study_site
from app.models import Item, Region, StudySiteCreate
from maress_types import CoordinateExtractionMethod, CoordinateSourceType, PaperSections
from tests.utils.user import create_test_user

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from sqlmodel import Session

    from app.models import User


def _create_site(
    db_session: Session,
    *,
    item_id,
    lat: float,
    lon: float,
    name: str,
    confidence: float,
    is_manual: bool,
) -> None:
    site = StudySiteCreate(
        name=name,
        latitude=Latitude(lat),
        longitude=Longitude(lon),
        confidence_score=confidence,
        context=f"{name} context",
        extraction_method=CoordinateExtractionMethod.MANUAL if is_manual else CoordinateExtractionMethod.REGEX,
        section=PaperSections.METHODS,
        source_type=CoordinateSourceType.MANUAL if is_manual else CoordinateSourceType.TEXT,
        validation_score=confidence,
        item_id=item_id,
        is_manual=is_manual,
    )
    create_study_site(db_session, site)


def _create_region(
    db_session: Session,
    *,
    owner_id,
    name: str,
    min_lon: float,
    min_lat: float,
    max_lon: float,
    max_lat: float,
) -> Region:
    polygon = Polygon(
        [
            (min_lon, min_lat),
            (max_lon, min_lat),
            (max_lon, max_lat),
            (min_lon, max_lat),
            (min_lon, min_lat),
        ],
    )
    region = Region(
        name=name,
        description="",
        source_filename=None,
        properties_json=None,
        owner_id=owner_id,
        geom=from_shape(MultiPolygon([polygon]), srid=4326),
    )
    db_session.add(region)
    db_session.commit()
    db_session.refresh(region)
    return region


def test_export_regions_geojson_owner_scoped(
    client: TestClient,
    db_session: Session,
    test_user: User,
    normal_user_token_headers: dict[str, str],
) -> None:
    own_region = _create_region(
        db_session,
        owner_id=test_user.id,
        name="Owned region",
        min_lon=11.4,
        min_lat=48.0,
        max_lon=11.8,
        max_lat=48.3,
    )
    foreign_user = create_test_user(db_session)
    _create_region(
        db_session,
        owner_id=foreign_user.id,
        name="Foreign region",
        min_lon=8.4,
        min_lat=50.0,
        max_lon=8.8,
        max_lat=50.3,
    )

    response = client.get(
        f"{settings.API_V1_STR}/export/regions",
        headers=normal_user_token_headers,
        params={"format": "geojson"},
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["type"] == "FeatureCollection"
    ids = {feature["properties"]["id"] for feature in payload["features"]}
    assert str(own_region.id) in ids
    assert len(ids) == 1


def test_export_gis_operation_summary_stats_csv(
    client: TestClient,
    db_session: Session,
    test_user: User,
    normal_user_token_headers: dict[str, str],
) -> None:
    from app import crud
    from tests.factories import ItemFactory

    item_in = ItemFactory.build()
    item = cast(Item, crud.create_item(session=db_session, item_in=item_in, owner_id=test_user.id))
    assert item.id is not None
    _create_site(
        db_session,
        item_id=item.id,
        lat=48.12,
        lon=11.54,
        name="Manual A",
        confidence=1.0,
        is_manual=True,
    )
    db_session.commit()

    response = client.post(
        f"{settings.API_V1_STR}/export/gis-operation",
        headers=normal_user_token_headers,
        params={"format": "csv"},
        json={
            "operation_id": "summary-stats",
            "payload": {
                "target": {"layer_id": "study-sites", "selection": {"type": "all"}},
                "group_by": ["is_manual"],
                "metrics": [{"type": "count", "field": "id", "alias": "site_count"}],
            },
        },
    )
    assert response.status_code == 200
    assert "site_count" in response.text


def test_export_gis_operation_buffer_geojson(
    client: TestClient,
    db_session: Session,
    test_user: User,
    normal_user_token_headers: dict[str, str],
) -> None:
    from app import crud
    from tests.factories import ItemFactory

    item_in = ItemFactory.build()
    item = cast(Item, crud.create_item(session=db_session, item_in=item_in, owner_id=test_user.id))
    assert item.id is not None
    _create_site(
        db_session,
        item_id=item.id,
        lat=48.12,
        lon=11.54,
        name="Buffer point",
        confidence=0.9,
        is_manual=True,
    )
    db_session.commit()

    response = client.post(
        f"{settings.API_V1_STR}/export/gis-operation",
        headers=normal_user_token_headers,
        params={"format": "geojson"},
        json={
            "operation_id": "buffer",
            "payload": {
                "target": {"layer_id": "study-sites", "selection": {"type": "all"}},
                "parameters": {"distance": 250, "unit": "meter", "dissolve": False},
            },
        },
    )
    assert response.status_code == 200
    payload = json.loads(response.text)
    assert payload["type"] == "FeatureCollection"
    assert len(payload["features"]) == 1
