"""API routes for manual study site management.

Allows users to:
- View study sites for an item
- Manually create study sites
- Update existing study sites (manual or automatic)
- Delete study sites
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from urllib.parse import quote
from typing import Any, Literal

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import func, select

from app.api.deps import CurrentUser, OptionalCurrentUser, SessionDep
from app.core.config import settings
from app.crud import create_location_if_needed
from app.models import (
    Item,
    Location,
    StudySite,
    StudySiteManualCreate,
    StudySiteManualUpdate,
    StudySiteMapPoint,
    StudySiteMapPointsPublic,
    StudySitePublic,
    StudySitesPublic,
)
from maress_types import (
    CoordinateExtractionMethod,
    CoordinateSourceType,
    PaperSections,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/study-sites", tags=["study-sites"])

_search_cache: dict[str, tuple[float, list["GeocodeSearchResult"]]] = {}
_search_lock = threading.Lock()
_last_search_request_time = 0.0


class GeocodeSearchResult(BaseModel):
    id: str
    label: str
    latitude: float
    longitude: float


class GeocodeSearchPublic(BaseModel):
    data: list[GeocodeSearchResult]
    count: int


def _normalized_countrycodes(countrycodes: str | None) -> str | None:
    if not countrycodes:
        return None

    codes = [code.strip().lower() for code in countrycodes.split(",") if code.strip()]
    return ",".join(codes) if codes else None


def _search_cache_key(
    provider: str,
    query_text: str,
    limit: int,
    language: str | None,
    countrycodes: str | None,
) -> str:
    normalized_language = (language or "").strip().lower()
    normalized_countrycodes = _normalized_countrycodes(countrycodes) or ""
    normalized_query = " ".join(query_text.strip().lower().split())
    return f"{provider}|{limit}|{normalized_language}|{normalized_countrycodes}|{normalized_query}"


def _get_cached_search_results(cache_key: str) -> list[GeocodeSearchResult] | None:
    cached_entry = _search_cache.get(cache_key)
    if not cached_entry:
        return None

    cached_at, results = cached_entry
    if (time.time() - cached_at) > settings.GEOCODING_SEARCH_CACHE_TTL:
        _search_cache.pop(cache_key, None)
        return None

    return results


def _cache_search_results(cache_key: str, results: list[GeocodeSearchResult]) -> None:
    _search_cache[cache_key] = (time.time(), results)


def _respect_search_rate_limit() -> None:
    global _last_search_request_time

    delay = 0.0
    now = time.time()

    with _search_lock:
        elapsed = now - _last_search_request_time
        required = settings.GEOCODING_SEARCH_RATE_LIMIT
        if elapsed < required:
            delay = required - elapsed
        else:
            _last_search_request_time = now

    if delay > 0:
        time.sleep(delay)
        with _search_lock:
            _last_search_request_time = time.time()


def _search_with_nominatim(
    query_text: str,
    limit: int,
    language: str | None,
    countrycodes: str | None,
) -> list[GeocodeSearchResult]:
    params: dict[str, str | int] = {
        "q": query_text,
        "format": "jsonv2",
        "limit": limit,
        "addressdetails": 1,
    }

    normalized_countrycodes = _normalized_countrycodes(countrycodes)
    if normalized_countrycodes:
        params["countrycodes"] = normalized_countrycodes
    if language:
        params["accept-language"] = language

    headers = {
        "User-Agent": f"{settings.PROJECT_NAME}/1.0 geocode-search",
        "Accept": "application/json",
    }

    _respect_search_rate_limit()
    response = httpx.get(
        settings.GEOCODING_SEARCH_NOMINATIM_URL,
        params=params,
        headers=headers,
        timeout=15.0,
    )
    response.raise_for_status()

    payload = response.json()
    if not isinstance(payload, list):
        return []

    results: list[GeocodeSearchResult] = []
    for item in payload:
        if not isinstance(item, dict):
            continue

        lat_raw = item.get("lat")
        lon_raw = item.get("lon")
        label = item.get("display_name")
        place_id = item.get("place_id")

        if lat_raw is None or lon_raw is None or not isinstance(label, str):
            continue

        try:
            latitude = float(lat_raw)
            longitude = float(lon_raw)
        except (TypeError, ValueError):
            continue

        results.append(
            GeocodeSearchResult(
                id=str(place_id) if place_id is not None else f"{latitude},{longitude}",
                label=label,
                latitude=latitude,
                longitude=longitude,
            )
        )

    return results


def _search_with_mapbox(
    query_text: str,
    limit: int,
    language: str | None,
    countrycodes: str | None,
) -> list[GeocodeSearchResult]:
    if not settings.GEOCODING_SEARCH_MAPBOX_ACCESS_TOKEN:
        raise HTTPException(status_code=503, detail="Mapbox search provider is not configured")

    encoded_query = quote(query_text, safe="")
    endpoint = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{encoded_query}.json"
    params: dict[str, str | int] = {
        "access_token": settings.GEOCODING_SEARCH_MAPBOX_ACCESS_TOKEN,
        "limit": limit,
    }

    normalized_countrycodes = _normalized_countrycodes(countrycodes)
    if normalized_countrycodes:
        params["country"] = normalized_countrycodes
    if language:
        params["language"] = language

    response = httpx.get(endpoint, params=params, timeout=15.0)
    response.raise_for_status()

    payload = response.json()
    features = payload.get("features", []) if isinstance(payload, dict) else []
    if not isinstance(features, list):
        return []

    results: list[GeocodeSearchResult] = []
    for feature in features:
        if not isinstance(feature, dict):
            continue

        center = feature.get("center")
        if not isinstance(center, list) or len(center) != 2:
            continue

        try:
            longitude = float(center[0])
            latitude = float(center[1])
        except (TypeError, ValueError):
            continue

        label = feature.get("place_name")
        if not isinstance(label, str):
            continue

        results.append(
            GeocodeSearchResult(
                id=str(feature.get("id") or f"{latitude},{longitude}"),
                label=label,
                latitude=latitude,
                longitude=longitude,
            )
        )

    return results


def _parse_bbox(bbox: str) -> tuple[float, float, float, float]:
    parts = [part.strip() for part in bbox.split(",")]
    if len(parts) != 4:
        raise HTTPException(
            status_code=400,
            detail="Invalid bbox format. Expected 'minLon,minLat,maxLon,maxLat'",
        )

    try:
        min_lon, min_lat, max_lon, max_lat = [float(v) for v in parts]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid bbox coordinates") from exc

    if min_lon >= max_lon or min_lat >= max_lat:
        raise HTTPException(status_code=400, detail="Invalid bbox extents")

    min_lon = max(-180.0, min_lon)
    max_lon = min(180.0, max_lon)
    min_lat = max(-90.0, min_lat)
    max_lat = min(90.0, max_lat)

    return min_lon, min_lat, max_lon, max_lat


@router.get("/map-points", response_model=StudySiteMapPointsPublic)
def get_map_points(
    *,
    session: SessionDep,
    current_user: OptionalCurrentUser,
    bbox: str | None = Query(default=None, description="minLon,minLat,maxLon,maxLat"),
    limit: int = Query(default=25000, ge=1, le=200000),
    scope: Literal["all", "mine"] = Query(default="all"),
) -> StudySiteMapPointsPublic:
    """Return lightweight study-site data for the map.

    Joins StudySite → Location (lat/lon) and Item (title only).
    No pagination — returns a flat list limited by viewport and scope.
    """
    if scope == "mine" and current_user is None:
        raise HTTPException(status_code=401, detail="Authentication required for scope=mine")

    statement = (
        select(
            StudySite.id,
            StudySite.name,
            StudySite.item_id,
            Item.title.label("item_title"),  # type: ignore[union-attr]
            Location.latitude,
            Location.longitude,
            StudySite.is_manual,
            StudySite.confidence_score,
        )
        .select_from(Location)
        .join(StudySite, StudySite.location_id == Location.id)
        .join(Item, StudySite.item_id == Item.id)
    )

    if scope == "mine" and current_user is not None:
        statement = statement.where(Item.owner_id == current_user.id)

    if bbox:
        min_lon, min_lat, max_lon, max_lat = _parse_bbox(bbox)
        envelope = func.ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
        statement = statement.where(
            func.ST_Intersects(Location.geom, envelope),
        )

    statement = statement.limit(limit)
    rows = session.exec(statement).all()

    points = [
        StudySiteMapPoint(
            id=row.id,
            name=row.name,
            item_id=row.item_id,
            item_title=row.item_title,
            latitude=float(row.latitude),
            longitude=float(row.longitude),
            is_manual=row.is_manual,
            confidence_score=row.confidence_score,
        )
        for row in rows
    ]

    return StudySiteMapPointsPublic(data=points, count=len(points))


@router.get("/geocode-search", response_model=GeocodeSearchPublic)
def geocode_search(
    *,
    session: SessionDep,
    current_user: OptionalCurrentUser,
    q: str = Query(min_length=3, max_length=120, description="Location search query"),
    limit: int = Query(default=8, ge=1, le=20),
    provider: str | None = Query(default=None, pattern="^(nominatim|mapbox)$"),
    language: str | None = Query(default=None, max_length=20),
    countrycodes: str | None = Query(default=None, max_length=120),
) -> GeocodeSearchPublic:
    del session, current_user

    normalized_query = " ".join(q.split())
    if len(normalized_query) < 3:
        raise HTTPException(status_code=400, detail="Query must contain at least 3 characters")

    effective_provider = provider or settings.GEOCODING_SEARCH_PROVIDER
    effective_limit = min(limit, settings.GEOCODING_SEARCH_MAX_LIMIT)
    effective_countrycodes = countrycodes or settings.GEOCODING_SEARCH_COUNTRYCODES

    cache_key = _search_cache_key(
        effective_provider,
        normalized_query,
        effective_limit,
        language,
        effective_countrycodes,
    )
    cached_results = _get_cached_search_results(cache_key)
    if cached_results is not None:
        return GeocodeSearchPublic(data=cached_results, count=len(cached_results))

    try:
        if effective_provider == "mapbox":
            results = _search_with_mapbox(
                normalized_query,
                effective_limit,
                language,
                effective_countrycodes,
            )
        else:
            results = _search_with_nominatim(
                normalized_query,
                effective_limit,
                language,
                effective_countrycodes,
            )
    except HTTPException:
        raise
    except httpx.HTTPStatusError as exc:
        logger.warning("Geocoding search request failed: %s", exc)
        raise HTTPException(status_code=502, detail="Search provider returned an error") from exc
    except httpx.HTTPError as exc:
        logger.warning("Geocoding search transport error: %s", exc)
        raise HTTPException(status_code=502, detail="Unable to reach search provider") from exc

    _cache_search_results(cache_key, results)
    return GeocodeSearchPublic(data=results, count=len(results))


def study_site_to_public(study_site: StudySite) -> StudySitePublic:
    """Convert StudySite ORM model to StudySitePublic with location data.

    Args:
        study_site: StudySite ORM object with loaded location relationship

    Returns:
        StudySitePublic with location data (lat/lon automatically computed)
    """
    # Pydantic will automatically populate computed fields (latitude/longitude)
    # from the location relationship
    return StudySitePublic.model_validate(study_site)


@router.get("/items/{item_id}/study-sites", response_model=StudySitesPublic)
def get_item_study_sites(
    *,
    session: SessionDep,
    current_user: OptionalCurrentUser,
    item_id: uuid.UUID,
) -> StudySitesPublic:
    """Get all study sites for a specific item.

    Returns both automatic and manual study sites.
    """
    # Verify item exists and user has access
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # Get all study sites for this item with location relationship loaded
    from sqlalchemy.orm import joinedload
    from sqlmodel import select as sql_select

    statement = (
        sql_select(StudySite)
        .where(StudySite.item_id == item_id)
        .order_by(StudySite.confidence_score.desc(), StudySite.created_at.desc())
        .options(joinedload(StudySite.location))  # Eagerly load location
    )
    study_sites = session.exec(statement).unique().all()

    return StudySitesPublic(
        data=[study_site_to_public(site) for site in study_sites],
        count=len(study_sites),
    )


@router.get("/study-sites/{study_site_id}", response_model=StudySitePublic)
def get_study_site(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    study_site_id: uuid.UUID,
) -> Any:
    """Get a specific study site by ID."""
    from sqlalchemy.orm import joinedload
    from sqlmodel import select as sql_select

    # Load study site with location relationship
    statement = (
        sql_select(StudySite)
        .where(StudySite.id == study_site_id)
        .options(joinedload(StudySite.location))
    )
    result = session.exec(statement).first()
    if not result:
        raise HTTPException(status_code=404, detail="Study site not found")

    study_site = result

    # Check access
    item = session.get(Item, study_site.item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Associated item not found")

    if not current_user.is_superuser and item.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    return study_site_to_public(study_site)


@router.post("/items/{item_id}/study-sites", response_model=StudySitePublic)
def create_manual_study_site(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    item_id: uuid.UUID,
    study_site_in: StudySiteManualCreate,
) -> Any:
    """Manually create a new study site for an item.

    This allows users to add study sites that the algorithm missed or
    to add known study sites before running extraction.
    """
    # Verify item exists and user has access
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if not current_user.is_superuser and item.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    # Create or get location for the coordinates
    location = create_location_if_needed(
        session=session,
        latitude=study_site_in.latitude,
        longitude=study_site_in.longitude,
    )

    # Create the study site marked as manual
    study_site = StudySite(
        name=study_site_in.name,
        context=study_site_in.context,
        confidence_score=study_site_in.confidence_score,
        validation_score=study_site_in.validation_score,
        extraction_method=CoordinateExtractionMethod.MANUAL,
        source_type=CoordinateSourceType.MANUAL,
        section=PaperSections.OTHER,
        item_id=item_id,
        location_id=location.id,
        is_manual=True,  # Mark as manually created
    )

    session.add(study_site)
    session.commit()
    session.refresh(study_site)
    # Load the location relationship
    session.refresh(study_site, ["location"])
    logger.info("User %s manually created study site %s for item %s", current_user.id, study_site.id, item_id)

    return study_site_to_public(study_site)


@router.put("/study-sites/{study_site_id}", response_model=StudySitePublic)
def update_study_site(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    study_site_id: uuid.UUID,
    study_site_in: StudySiteManualUpdate,
) -> Any:
    """Update an existing study site (manual or automatic).

    When a user modifies a study site, it's marked as manual to indicate
    human oversight has been applied.
    """
    study_site = session.get(StudySite, study_site_id)
    if not study_site:
        raise HTTPException(status_code=404, detail="Study site not found")

    # Check access
    item = session.get(Item, study_site.item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Associated item not found")

    if not current_user.is_superuser and item.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    # Update fields
    update_data = study_site_in.model_dump(exclude_unset=True)

    # If coordinates are being updated, create or get new location
    if "latitude" in update_data or "longitude" in update_data:
        # Use new coordinates or keep existing ones
        new_lat = update_data.get("latitude", study_site.location.latitude)
        new_lon = update_data.get("longitude", study_site.location.longitude)

        location = create_location_if_needed(session=session, latitude=new_lat, longitude=new_lon)
        study_site.location_id = location.id

        # Remove lat/lon from update_data as we handled them
        update_data.pop("latitude", None)
        update_data.pop("longitude", None)

    # Apply remaining updates
    for key, value in update_data.items():
        setattr(study_site, key, value)

    # Mark as manual since human has modified it
    study_site.is_manual = True
    if study_site.extraction_method != CoordinateExtractionMethod.MANUAL:
        # Keep track that it was originally automatic but now human-verified
        study_site.extraction_method = CoordinateExtractionMethod.MANUAL

    session.add(study_site)
    session.commit()
    session.refresh(study_site)
    # Load the location relationship
    session.refresh(study_site, ["location"])
    logger.info("User %s updated study site %s", current_user.id, study_site_id)

    return study_site_to_public(study_site)


@router.patch("/study-sites/{study_site_id}", response_model=StudySitePublic)
def partial_update_study_site(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    study_site_id: uuid.UUID,
    study_site_in: StudySiteManualUpdate,
) -> Any:
    """Partially update a study site (alias for PUT for convenience)."""
    return update_study_site(
        session=session,
        current_user=current_user,
        study_site_id=study_site_id,
        study_site_in=study_site_in,
    )


@router.delete("/study-sites/{study_site_id}")
def delete_study_site(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    study_site_id: uuid.UUID,
) -> dict[str, str]:
    """Delete a study site.

    This allows users to remove false positives identified by the algorithm.
    """
    study_site = session.get(StudySite, study_site_id)
    if not study_site:
        raise HTTPException(status_code=404, detail="Study site not found")

    # Check access
    item = session.get(Item, study_site.item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Associated item not found")

    if not current_user.is_superuser and item.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    session.delete(study_site)
    session.commit()
    logger.info("User %s deleted study site %s", current_user.id, study_site_id)

    return {"message": "Study site deleted successfully"}


@router.get("/items/{item_id}/study-sites/stats")
def get_study_site_stats(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    item_id: uuid.UUID,
) -> dict[str, Any]:
    """Get statistics about study sites for an item.

    Returns counts of automatic vs manual study sites, confidence distribution, etc.
    """
    # Verify item exists and user has access
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if not current_user.is_superuser and item.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    # Get counts
    total_count = session.exec(
        select(func.count()).where(StudySite.item_id == item_id),
    ).one()

    manual_count = session.exec(
        select(func.count()).where(StudySite.item_id == item_id, StudySite.is_manual == True),  # noqa: E712
    ).one()

    automatic_count = total_count - manual_count

    # Get average confidence
    avg_confidence_stmt = select(func.avg(StudySite.confidence_score)).where(
        StudySite.item_id == item_id,
    )
    avg_confidence = session.exec(avg_confidence_stmt).one()

    # Get extraction methods breakdown
    methods_stmt = (
        select(StudySite.extraction_method, func.count())
        .where(StudySite.item_id == item_id)
        .group_by(StudySite.extraction_method)
    )
    methods_result = session.exec(methods_stmt).all()
    methods_breakdown = {str(method): count for method, count in methods_result}

    return {
        "total": total_count,
        "manual": manual_count,
        "automatic": automatic_count,
        "average_confidence": float(avg_confidence) if avg_confidence else 0.0,
        "extraction_methods": methods_breakdown,
    }
