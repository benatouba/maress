"""API routes for manual study site management.

Allows users to:
- View study sites for an item
- Manually create study sites
- Update existing study sites (manual or automatic)
- Delete study sites
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep
from app.crud import create_location_if_needed
from app.models import (
    Item,
    StudySite,
    StudySiteManualCreate,
    StudySiteManualUpdate,
    StudySitePublic,
    StudySitesPublic,
)
from maress_types import (
    CoordinateExtractionMethod,
    CoordinateSourceType,
    PaperSections,
)

router = APIRouter(prefix="/study-sites", tags=["study-sites"])


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
    current_user: CurrentUser,
    item_id: uuid.UUID,
) -> StudySitesPublic:
    """Get all study sites for a specific item.

    Returns both automatic and manual study sites.
    """
    # Verify item exists and user has access
    item = session.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if not current_user.is_superuser and item.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    # Get all study sites for this item with location relationship loaded
    from sqlmodel import select as sql_select
    from sqlalchemy.orm import joinedload

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
    from sqlmodel import select as sql_select
    from sqlalchemy.orm import joinedload

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
