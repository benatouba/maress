"""API routes for geographic region management.

Allows users to:
- Upload shapefiles (.zip) to create geographic regions
- List and view uploaded regions with GeoJSON geometry
- Query spatial statistics (study sites within a region)
- Retrieve study sites that fall within a region
- Delete regions
"""

from __future__ import annotations

import json
import tempfile
import uuid
import zipfile
from typing import Any

import geopandas as gpd
from fastapi import APIRouter, HTTPException, UploadFile
from geoalchemy2.functions import ST_AsGeoJSON, ST_Within
from geoalchemy2.shape import from_shape
from shapely.geometry import MultiPolygon, mapping
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Item,
    ItemSummary,
    Location,
    Region,
    RegionPublic,
    RegionStats,
    RegionsPublic,
    StudySite,
    StudySiteMapPoint,
    StudySiteMapPointsPublic,
)

router = APIRouter(prefix="/regions", tags=["regions"])

MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB


def _to_multipolygon(geom: Any) -> MultiPolygon:
    """Normalize a geometry to MultiPolygon."""
    if geom.geom_type == "Polygon":
        return MultiPolygon([geom])
    if geom.geom_type == "MultiPolygon":
        return geom
    msg = f"Unsupported geometry type: {geom.geom_type}. Only Polygon and MultiPolygon are supported."
    raise ValueError(msg)


@router.post("/upload", response_model=RegionsPublic)
def upload_shapefile(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    file: UploadFile,
) -> RegionsPublic:
    """Upload a .zip file containing shapefile components.

    Parses the shapefile with geopandas, reprojects to EPSG:4326 if needed,
    and creates one Region record per feature.
    """
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="File must be a .zip archive")

    # Read file content and check size
    content = file.file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 50 MB size limit")

    # Validate it's a valid ZIP
    try:
        with zipfile.ZipFile(file.file) as zf:
            zf.testzip()
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail="Invalid ZIP file") from exc

    # Write to temp file and parse with geopandas
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=True) as tmp:
        tmp.write(content)
        tmp.flush()

        try:
            gdf = gpd.read_file(tmp.name)
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Could not parse shapefile: {exc}",
            ) from exc

    if gdf.empty:
        raise HTTPException(status_code=400, detail="Shapefile contains no features")

    # Reproject to EPSG:4326 if needed
    if gdf.crs and not gdf.crs.equals("EPSG:4326"):
        gdf = gdf.to_crs(epsg=4326)
    elif gdf.crs is None:
        # Assume WGS84 if no CRS is specified
        gdf = gdf.set_crs(epsg=4326)

    # Validate and make geometries valid
    gdf["geometry"] = gdf["geometry"].make_valid()

    created_regions: list[RegionPublic] = []
    source_filename = file.filename

    for idx, row in gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue

        try:
            multi_geom = _to_multipolygon(geom)
        except ValueError:
            continue  # skip non-polygon features

        # Extract a name from common shapefile attribute columns
        name = None
        for col in ("NAME", "Name", "name", "LABEL", "Label", "label", "ID", "FID"):
            if col in row.index and row[col] is not None:
                name = str(row[col])
                break
        if not name:
            name = f"Region {idx}"

        # Store non-geometry attributes as JSON
        props = {}
        for col in gdf.columns:
            if col == "geometry":
                continue
            val = row[col]
            if val is not None:
                try:
                    json.dumps(val)  # test if serializable
                    props[col] = val
                except (TypeError, ValueError):
                    props[col] = str(val)

        region = Region(
            name=name,
            source_filename=source_filename,
            properties_json=json.dumps(props) if props else None,
            owner_id=current_user.id,
            geom=from_shape(multi_geom, srid=4326),
        )
        session.add(region)
        session.flush()

        geojson_dict = mapping(multi_geom)

        created_regions.append(
            RegionPublic(
                id=region.id,
                name=region.name,
                description=region.description,
                source_filename=region.source_filename,
                properties_json=region.properties_json,
                owner_id=region.owner_id,
                created_at=region.created_at,
                updated_at=region.updated_at,
                geojson=geojson_dict,
            )
        )

    session.commit()

    return RegionsPublic(data=created_regions, count=len(created_regions))


@router.get("/", response_model=RegionsPublic)
def list_regions(
    *,
    session: SessionDep,
    current_user: CurrentUser,
) -> RegionsPublic:
    """List all regions for the current user with GeoJSON geometry."""
    statement = select(
        Region.id,
        Region.name,
        Region.description,
        Region.source_filename,
        Region.properties_json,
        Region.owner_id,
        Region.created_at,
        Region.updated_at,
        ST_AsGeoJSON(Region.geom).label("geojson_str"),
    ).where(Region.owner_id == current_user.id)

    rows = session.exec(statement).all()

    regions = [
        RegionPublic(
            id=row.id,
            name=row.name,
            description=row.description,
            source_filename=row.source_filename,
            properties_json=row.properties_json,
            owner_id=row.owner_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
            geojson=json.loads(row.geojson_str),
        )
        for row in rows
    ]

    return RegionsPublic(data=regions, count=len(regions))


@router.get("/{region_id}", response_model=RegionPublic)
def get_region(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    region_id: uuid.UUID,
) -> RegionPublic:
    """Get a single region with its GeoJSON geometry."""
    statement = select(
        Region.id,
        Region.name,
        Region.description,
        Region.source_filename,
        Region.properties_json,
        Region.owner_id,
        Region.created_at,
        Region.updated_at,
        ST_AsGeoJSON(Region.geom).label("geojson_str"),
    ).where(Region.id == region_id, Region.owner_id == current_user.id)

    row = session.exec(statement).first()
    if not row:
        raise HTTPException(status_code=404, detail="Region not found")

    return RegionPublic(
        id=row.id,
        name=row.name,
        description=row.description,
        source_filename=row.source_filename,
        properties_json=row.properties_json,
        owner_id=row.owner_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        geojson=json.loads(row.geojson_str),
    )


@router.get("/{region_id}/stats", response_model=RegionStats)
def get_region_stats(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    region_id: uuid.UUID,
) -> RegionStats:
    """Get spatial statistics: study sites and papers within a region."""
    region = session.get(Region, region_id)
    if not region or region.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Region not found")

    # Count study sites within the region using a subquery for the region geometry
    region_geom_subq = select(Region.geom).where(Region.id == region_id).scalar_subquery()

    base_filter = (
        select(StudySite.id, StudySite.item_id, StudySite.is_manual, StudySite.extraction_method)
        .join(Location, StudySite.location_id == Location.id)
        .where(ST_Within(Location.geom, region_geom_subq))
    )

    rows = session.exec(base_filter).all()

    study_site_count = len(rows)
    manual_count = sum(1 for r in rows if r.is_manual)
    automatic_count = study_site_count - manual_count

    # Extraction method breakdown
    methods: dict[str, int] = {}
    for r in rows:
        method_name = str(r.extraction_method)
        methods[method_name] = methods.get(method_name, 0) + 1

    # Distinct papers
    paper_ids = list({r.item_id for r in rows})
    papers: list[ItemSummary] = []
    if paper_ids:
        paper_stmt = select(Item.id, Item.title).where(Item.id.in_(paper_ids))  # type: ignore[union-attr]
        paper_rows = session.exec(paper_stmt).all()
        papers = [ItemSummary(id=p.id, title=p.title) for p in paper_rows]

    return RegionStats(
        region_id=region.id,
        region_name=region.name,
        study_site_count=study_site_count,
        paper_count=len(paper_ids),
        manual_count=manual_count,
        automatic_count=automatic_count,
        extraction_methods=methods,
        papers=papers,
    )


@router.get("/{region_id}/study-sites", response_model=StudySiteMapPointsPublic)
def get_region_study_sites(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    region_id: uuid.UUID,
) -> StudySiteMapPointsPublic:
    """Get study sites that fall within a region."""
    region = session.get(Region, region_id)
    if not region or region.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Region not found")

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
        .where(ST_Within(Location.geom, select(Region.geom).where(Region.id == region_id).scalar_subquery()))
    )

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


@router.delete("/{region_id}")
def delete_region(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    region_id: uuid.UUID,
) -> dict[str, str]:
    """Delete a region."""
    region = session.get(Region, region_id)
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")
    if region.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    session.delete(region)
    session.commit()

    return {"message": "Region deleted successfully"}
