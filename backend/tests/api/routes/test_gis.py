from __future__ import annotations

from typing import TYPE_CHECKING

from geoalchemy2.shape import from_shape
from pydantic_extra_types.coordinate import Latitude, Longitude
from shapely.geometry import MultiPolygon, Polygon

from app.core.config import settings
from app.crud import create_study_site
from app.models import Region, StudySiteCreate
from maress_types import CoordinateExtractionMethod, CoordinateSourceType, PaperSections
from tests.utils.item import create_random_item

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


def test_gis_capabilities_anonymous(client: TestClient) -> None:
    response = client.get(f"{settings.API_V1_STR}/gis/capabilities")
    assert response.status_code == 200
    content = response.json()

    assert content["version"] == "draft-v1"
    assert isinstance(content["operations"], list)
    assert any(op["id"] == "within-distance" for op in content["operations"])
    assert all(op["enabled"] is False for op in content["operations"])


def test_gis_capabilities_authenticated(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/gis/capabilities",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    assert all(op["enabled"] is True for op in content["operations"])


def test_within_distance_requires_authentication(client: TestClient) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/gis/operations/within-distance",
        json={
            "source": {"layer_id": "study-sites", "selection": {"type": "all"}},
            "against": {"layer_id": "regions", "selection": {"type": "all"}},
            "parameters": {"distance": 1, "unit": "kilometer", "return": "source"},
        },
    )
    assert response.status_code == 401


def test_summary_stats_requires_authentication(client: TestClient) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/gis/operations/summary-stats",
        json={
            "target": {"layer_id": "study-sites", "selection": {"type": "all"}},
            "group_by": ["is_manual"],
            "metrics": [{"type": "count", "field": "id", "alias": "site_count"}],
        },
    )
    assert response.status_code == 401


def test_summary_stats_groups_and_metrics(
    client: TestClient,
    db_session: Session,
    normal_user_token_headers: dict[str, str],
) -> None:
    item = create_random_item(db_session)
    _create_site(
        db_session,
        item_id=item.id,
        lat=48.12,
        lon=11.54,
        name="Manual A",
        confidence=1.0,
        is_manual=True,
    )
    _create_site(
        db_session,
        item_id=item.id,
        lat=48.14,
        lon=11.58,
        name="Auto B",
        confidence=0.6,
        is_manual=False,
    )
    db_session.commit()

    response = client.post(
        f"{settings.API_V1_STR}/gis/operations/summary-stats",
        headers=normal_user_token_headers,
        json={
            "target": {"layer_id": "study-sites", "selection": {"type": "all"}},
            "group_by": ["is_manual"],
            "metrics": [
                {"type": "count", "field": "id", "alias": "site_count"},
                {"type": "avg", "field": "confidence_score", "alias": "avg_conf"},
            ],
        },
    )
    assert response.status_code == 200
    content = response.json()

    assert content["count"] == 2
    rows = {row["is_manual"]: row for row in content["rows"]}
    assert rows[True]["site_count"] == 1
    assert rows[False]["site_count"] == 1
    assert rows[True]["avg_conf"] == 1.0
    assert rows[False]["avg_conf"] == 0.6


def test_within_distance_returns_study_sites(
    client: TestClient,
    db_session: Session,
    test_user: User,
    normal_user_token_headers: dict[str, str],
) -> None:
    item = create_random_item(db_session)
    _create_site(
        db_session,
        item_id=item.id,
        lat=48.1300,
        lon=11.5600,
        name="Inside Munich",
        confidence=0.9,
        is_manual=True,
    )
    _create_site(
        db_session,
        item_id=item.id,
        lat=50.1109,
        lon=8.6821,
        name="Frankfurt",
        confidence=0.8,
        is_manual=False,
    )
    db_session.commit()

    region = _create_region(
        db_session,
        owner_id=test_user.id,
        name="Munich Area",
        min_lon=11.40,
        min_lat=48.00,
        max_lon=11.80,
        max_lat=48.30,
    )

    response = client.post(
        f"{settings.API_V1_STR}/gis/operations/within-distance",
        headers=normal_user_token_headers,
        json={
            "source": {"layer_id": "study-sites", "selection": {"type": "all"}},
            "against": {
                "layer_id": "regions",
                "selection": {"type": "ids", "ids": [str(region.id)]},
            },
            "parameters": {"distance": 2000, "unit": "meter", "return": "source"},
        },
    )
    assert response.status_code == 200
    content = response.json()

    assert content["return_layer_id"] == "study-sites"
    assert content["count"] == 1
    assert content["study_sites"][0]["name"] == "Inside Munich"


def test_summary_stats_with_spatial_filter(
    client: TestClient,
    db_session: Session,
    test_user: User,
    normal_user_token_headers: dict[str, str],
) -> None:
    item = create_random_item(db_session)
    _create_site(
        db_session,
        item_id=item.id,
        lat=48.1300,
        lon=11.5600,
        name="Inside Munich",
        confidence=0.9,
        is_manual=True,
    )
    _create_site(
        db_session,
        item_id=item.id,
        lat=50.1109,
        lon=8.6821,
        name="Frankfurt",
        confidence=0.8,
        is_manual=False,
    )
    db_session.commit()

    region = _create_region(
        db_session,
        owner_id=test_user.id,
        name="Munich Area",
        min_lon=11.40,
        min_lat=48.00,
        max_lon=11.80,
        max_lat=48.30,
    )

    response = client.post(
        f"{settings.API_V1_STR}/gis/operations/summary-stats",
        headers=normal_user_token_headers,
        json={
            "target": {"layer_id": "study-sites", "selection": {"type": "all"}},
            "group_by": ["is_manual"],
            "metrics": [{"type": "count", "field": "id", "alias": "site_count"}],
            "spatial_filter": {
                "layer_id": "regions",
                "selection": {"type": "ids", "ids": [str(region.id)]},
                "predicate": "within",
            },
        },
    )
    assert response.status_code == 200
    content = response.json()

    assert content["count"] == 1
    assert content["rows"][0]["is_manual"] is True
    assert content["rows"][0]["site_count"] == 1


def test_summary_stats_rejects_invalid_metric_field(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/gis/operations/summary-stats",
        headers=normal_user_token_headers,
        json={
            "target": {"layer_id": "study-sites", "selection": {"type": "all"}},
            "group_by": ["is_manual"],
            "metrics": [{"type": "avg", "field": "id"}],
        },
    )
    assert response.status_code == 400
    assert "Unsupported avg field" in response.json()["detail"]


def test_buffer_study_sites_returns_geojson_buffers(
    client: TestClient,
    db_session: Session,
    normal_user_token_headers: dict[str, str],
) -> None:
    item = create_random_item(db_session)
    _create_site(
        db_session,
        item_id=item.id,
        lat=48.12,
        lon=11.54,
        name="Buffer Point",
        confidence=0.9,
        is_manual=True,
    )
    db_session.commit()

    response = client.post(
        f"{settings.API_V1_STR}/gis/operations/buffer",
        headers=normal_user_token_headers,
        json={
            "target": {"layer_id": "study-sites", "selection": {"type": "all"}},
            "parameters": {"distance": 500, "unit": "meter", "dissolve": False},
        },
    )
    assert response.status_code == 200
    content = response.json()

    assert content["target_layer_id"] == "study-sites"
    assert content["count"] == 1
    assert content["features"][0]["source_id"] is not None
    assert content["features"][0]["geometry"]["type"] in {"Polygon", "MultiPolygon"}


def test_buffer_regions_dissolve_returns_single_geometry(
    client: TestClient,
    db_session: Session,
    test_user: User,
    normal_user_token_headers: dict[str, str],
) -> None:
    _create_region(
        db_session,
        owner_id=test_user.id,
        name="Region A",
        min_lon=11.0,
        min_lat=48.0,
        max_lon=11.2,
        max_lat=48.2,
    )
    _create_region(
        db_session,
        owner_id=test_user.id,
        name="Region B",
        min_lon=11.15,
        min_lat=48.1,
        max_lon=11.4,
        max_lat=48.35,
    )

    response = client.post(
        f"{settings.API_V1_STR}/gis/operations/buffer",
        headers=normal_user_token_headers,
        json={
            "target": {"layer_id": "regions", "selection": {"type": "all"}},
            "parameters": {"distance": 250, "unit": "meter", "dissolve": True},
        },
    )
    assert response.status_code == 200
    content = response.json()

    assert content["target_layer_id"] == "regions"
    assert content["dissolved"] is True
    assert content["count"] == 1
    assert content["features"][0]["geometry"]["type"] in {"Polygon", "MultiPolygon"}


def test_clip_study_sites_by_region(
    client: TestClient,
    db_session: Session,
    test_user: User,
    normal_user_token_headers: dict[str, str],
) -> None:
    item = create_random_item(db_session)
    _create_site(
        db_session,
        item_id=item.id,
        lat=48.1300,
        lon=11.5600,
        name="Inside Munich",
        confidence=0.9,
        is_manual=True,
    )
    _create_site(
        db_session,
        item_id=item.id,
        lat=50.1109,
        lon=8.6821,
        name="Frankfurt",
        confidence=0.8,
        is_manual=False,
    )
    db_session.commit()

    region = _create_region(
        db_session,
        owner_id=test_user.id,
        name="Munich Area",
        min_lon=11.40,
        min_lat=48.00,
        max_lon=11.80,
        max_lat=48.30,
    )

    response = client.post(
        f"{settings.API_V1_STR}/gis/operations/clip",
        headers=normal_user_token_headers,
        json={
            "target": {"layer_id": "study-sites", "selection": {"type": "all"}},
            "clip_with": {
                "layer_id": "regions",
                "selection": {"type": "ids", "ids": [str(region.id)]},
            },
        },
    )
    assert response.status_code == 200
    content = response.json()

    assert content["target_layer_id"] == "study-sites"
    assert content["clip_layer_id"] == "regions"
    assert content["count"] == 1
    assert content["study_sites"][0]["name"] == "Inside Munich"


def test_clip_rejects_unsupported_layers(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/gis/operations/clip",
        headers=normal_user_token_headers,
        json={
            "target": {"layer_id": "regions", "selection": {"type": "all"}},
            "clip_with": {"layer_id": "study-sites", "selection": {"type": "all"}},
        },
    )
    assert response.status_code == 400
    assert "clip currently supports" in response.json()["detail"]
