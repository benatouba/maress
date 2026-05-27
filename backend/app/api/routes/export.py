"""Data export endpoints for study sites and items.

Supports exporting study sites as GeoJSON or CSV, and items as BibTeX.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import uuid
from enum import StrEnum
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.api.routes.gis import execute_gis_operation
from app.models import Creator, GISAsyncOperationRequest, Item, Location, Region, StudySite

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export", tags=["export"])


class StudySiteExportFormat(StrEnum):
    geojson = "geojson"
    csv = "csv"


class ItemExportFormat(StrEnum):
    bibtex = "bibtex"


class RegionExportFormat(StrEnum):
    geojson = "geojson"
    csv = "csv"


class GISOperationExportFormat(StrEnum):
    geojson = "geojson"
    csv = "csv"


@router.get("/study-sites")
def export_study_sites(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    export_format: Annotated[StudySiteExportFormat, Query(alias="format")] = StudySiteExportFormat.geojson,
    item_id: Annotated[uuid.UUID | None, Query(description="Filter by item ID")] = None,
) -> StreamingResponse:
    """Export study sites as GeoJSON or CSV."""
    statement = (  # pyright: ignore[reportCallIssue]
        select(  # pyright: ignore[reportCallIssue]
            col(StudySite.id),
            col(StudySite.name),
            col(StudySite.item_id),
            col(Item.title).label("item_title"),
            col(Item.doi),
            col(Location.latitude),
            col(Location.longitude),
            col(StudySite.confidence_score),
            col(StudySite.is_manual),
            col(StudySite.extraction_method),
            col(StudySite.source_type),
            col(StudySite.section),
            col(StudySite.context),
        )
        .select_from(StudySite)
        .join(Location, StudySite.location_id == Location.id)
        .join(Item, StudySite.item_id == Item.id)
        .where(Item.owner_id == current_user.id)
    )

    if item_id is not None:
        statement = statement.where(StudySite.item_id == item_id)

    rows = session.exec(statement).all()

    if export_format == StudySiteExportFormat.geojson:
        return _export_study_sites_geojson(rows)
    return _export_study_sites_csv(rows)


def _coerce(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, StrEnum):
        return value.value
    return value


def _export_study_sites_geojson(rows: list[Any]) -> StreamingResponse:
    features = []
    for row in rows:
        lat, lon = float(row[5]), float(row[6])
        feature = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "id": str(row[0]),
                "name": row[1],
                "item_id": str(row[2]),
                "item_title": row[3],
                "doi": row[4],
                "confidence_score": row[7],
                "is_manual": row[8],
                "extraction_method": _coerce(row[9]),
                "source_type": _coerce(row[10]),
                "section": _coerce(row[11]),
                "context": row[12],
            },
        }
        features.append(feature)

    collection = {"type": "FeatureCollection", "features": features}
    content = json.dumps(collection, ensure_ascii=False, indent=2)

    return StreamingResponse(
        iter([content]),
        media_type="application/geo+json",
        headers={"Content-Disposition": "attachment; filename=study_sites.geojson"},
    )


def _export_study_sites_csv(rows: list[Any]) -> StreamingResponse:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "name", "latitude", "longitude", "item_id", "item_title",
        "doi", "confidence_score", "is_manual", "extraction_method",
        "source_type", "section", "context",
    ])

    for row in rows:
        writer.writerow([
            str(row[0]),   # id
            row[1],        # name
            float(row[5]), # latitude
            float(row[6]), # longitude
            str(row[2]),   # item_id
            row[3],        # item_title
            row[4],        # doi
            row[7],        # confidence_score
            row[8],        # is_manual
            _coerce(row[9]),  # extraction_method
            _coerce(row[10]), # source_type
            _coerce(row[11]), # section
            row[12],       # context
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=study_sites.csv"},
    )


@router.get("/regions")
def export_regions(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    export_format: Annotated[RegionExportFormat, Query(alias="format")] = RegionExportFormat.geojson,
) -> StreamingResponse:
    """Export user's regions as GeoJSON or CSV."""
    statement = (  # pyright: ignore[reportCallIssue]
        select(  # pyright: ignore[reportCallIssue]
            col(Region.id),
            col(Region.name),
            col(Region.description),
            col(Region.source_filename),
            col(Region.properties_json),
            func.ST_AsGeoJSON(Region.geom).label("geometry_json"),
        )
        .select_from(Region)
        .where(Region.owner_id == current_user.id)
    )
    rows = list(session.exec(statement).all())

    if export_format == RegionExportFormat.geojson:
        features = []
        for row in rows:
            geometry = json.loads(row[5]) if row[5] else None
            if geometry is None:
                continue
            features.append(
                {
                    "type": "Feature",
                    "geometry": geometry,
                    "properties": {
                        "id": str(row[0]),
                        "name": row[1],
                        "description": row[2],
                        "source_filename": row[3],
                        "properties_json": row[4],
                    },
                },
            )

        content = json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, indent=2)
        return StreamingResponse(
            iter([content]),
            media_type="application/geo+json",
            headers={"Content-Disposition": "attachment; filename=regions.geojson"},
        )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "name", "description", "source_filename", "properties_json", "geometry"])
    for row in rows:
        writer.writerow([
            str(row[0]),
            row[1],
            row[2],
            row[3],
            row[4],
            row[5],
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=regions.csv"},
    )


@router.post("/gis-operation")
def export_gis_operation(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    request: GISAsyncOperationRequest,
    export_format: Annotated[GISOperationExportFormat, Query(alias="format")] = GISOperationExportFormat.geojson,
) -> StreamingResponse:
    """Run one GIS operation and export result as GeoJSON/CSV."""
    result = execute_gis_operation(
        session=session,
        current_user=current_user,
        operation_id=request.operation_id,
        payload=request.payload,
    )

    if export_format == GISOperationExportFormat.geojson:
        return _export_gis_operation_geojson(session, current_user.id, request.operation_id, result)
    return _export_gis_operation_csv(request.operation_id, result)


def _export_gis_operation_geojson(
    session: SessionDep,
    owner_id: uuid.UUID,
    operation_id: str,
    result: dict[str, Any],
) -> StreamingResponse:
    features: list[dict[str, Any]] = []

    if operation_id == "buffer":
        for feature in result.get("features", []):
            geometry = feature.get("geometry")
            if not geometry:
                continue
            features.append(
                {
                    "type": "Feature",
                    "geometry": geometry,
                    "properties": {"source_id": feature.get("source_id")},
                },
            )
    elif operation_id in {"clip", "within-distance"} and result.get("study_sites"):
        for site in result.get("study_sites", []):
            lat = site.get("latitude")
            lon = site.get("longitude")
            if lat is None or lon is None:
                continue
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    "properties": site,
                },
            )
    elif operation_id == "within-distance" and result.get("regions"):
        region_ids = [entry.get("id") for entry in result.get("regions", []) if entry.get("id")]
        if region_ids:
            statement = (
                select(Region.id, Region.name, func.ST_AsGeoJSON(Region.geom).label("geometry_json"))
                .select_from(Region)
                .where(Region.owner_id == owner_id)
                .where(col(Region.id).in_(region_ids))
            )
            for row in session.exec(statement).all():
                geometry = json.loads(row[2]) if row[2] else None
                if geometry is None:
                    continue
                features.append(
                    {
                        "type": "Feature",
                        "geometry": geometry,
                        "properties": {"id": str(row[0]), "name": row[1]},
                    },
                )
    else:
        raise HTTPException(
            status_code=400,
            detail="GeoJSON export is not supported for this operation result",
        )

    collection = {"type": "FeatureCollection", "features": features}
    content = json.dumps(collection, ensure_ascii=False, indent=2)
    return StreamingResponse(
        iter([content]),
        media_type="application/geo+json",
        headers={"Content-Disposition": f"attachment; filename=gis_{operation_id}.geojson"},
    )


def _export_gis_operation_csv(operation_id: str, result: dict[str, Any]) -> StreamingResponse:
    output = io.StringIO()
    writer = csv.writer(output)

    if operation_id == "summary-stats":
        rows = result.get("rows", [])
        if rows:
            header = list(rows[0].keys())
            writer.writerow(header)
            for row in rows:
                writer.writerow([row.get(key) for key in header])
        else:
            writer.writerow(["message"])
            writer.writerow(["No rows"])
    elif operation_id == "buffer":
        writer.writerow(["source_id", "geometry"])
        for feature in result.get("features", []):
            writer.writerow([
                feature.get("source_id"),
                json.dumps(feature.get("geometry")),
            ])
    elif operation_id in {"clip", "within-distance"} and result.get("study_sites"):
        writer.writerow(["id", "name", "item_id", "item_title", "latitude", "longitude", "is_manual", "confidence_score"])
        for site in result.get("study_sites", []):
            writer.writerow([
                site.get("id"),
                site.get("name"),
                site.get("item_id"),
                site.get("item_title"),
                site.get("latitude"),
                site.get("longitude"),
                site.get("is_manual"),
                site.get("confidence_score"),
            ])
    elif operation_id == "within-distance" and result.get("regions"):
        writer.writerow(["id", "name"])
        for region in result.get("regions", []):
            writer.writerow([region.get("id"), region.get("name")])
    else:
        raise HTTPException(status_code=400, detail="CSV export is not supported for this operation result")

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=gis_{operation_id}.csv"},
    )


@router.get("/items")
def export_items(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    export_format: Annotated[ItemExportFormat, Query(alias="format")] = ItemExportFormat.bibtex,  # noqa: ARG001
    tag: Annotated[str | None, Query(description="Filter by tag name")] = None,
) -> StreamingResponse:
    """Export items as BibTeX."""
    statement = select(Item).where(Item.owner_id == current_user.id)
    results = list(session.exec(statement).all())

    if tag is not None:
        results = [item for item in results if any(t.name == tag for t in (item.tags or []))]

    # Eagerly load creators
    for item in results:
        _ = item.creators

    return _export_items_bibtex(results)


def _export_items_bibtex(items: list[Item]) -> StreamingResponse:
    entries = []
    for item in items:
        cite_key = _make_cite_key(item)
        entry_type = _zotero_to_bibtex_type(item.itemType)

        fields: list[str] = []
        if item.title:
            fields.append(f"  title = {{{item.title}}}")
        if item.publicationTitle:
            fields.append(f"  journal = {{{item.publicationTitle}}}")
        if item.volume:
            fields.append(f"  volume = {{{item.volume}}}")
        if item.issue:
            fields.append(f"  number = {{{item.issue}}}")
        if item.pages:
            fields.append(f"  pages = {{{item.pages}}}")
        if item.date:
            fields.append(f"  year = {{{item.date[:4]}}}")
        if item.doi:
            fields.append(f"  doi = {{{item.doi}}}")
        if item.url:
            fields.append(f"  url = {{{item.url}}}")
        if item.abstractNote:
            abstract = item.abstractNote.replace("{", "\\{").replace("}", "\\}")
            fields.append(f"  abstract = {{{abstract}}}")

        authors = _format_bibtex_authors(item.creators)
        if authors:
            fields.append(f"  author = {{{authors}}}")

        entry = f"@{entry_type}{{{cite_key},\n" + ",\n".join(fields) + "\n}"
        entries.append(entry)

    content = "\n\n".join(entries) + "\n"
    return StreamingResponse(
        iter([content]),
        media_type="application/x-bibtex",
        headers={"Content-Disposition": "attachment; filename=references.bib"},
    )


def _make_cite_key(item: Item) -> str:
    first_creator = ""
    if item.creators:
        first_creator = item.creators[0].lastName or item.creators[0].firstName or ""
        first_creator = "".join(c for c in first_creator if c.isalnum())

    year = item.date[:4] if item.date else ""
    return f"{first_creator}{year}" or str(item.id)[:8]


def _zotero_to_bibtex_type(item_type: str) -> str:
    mapping = {
        "journalArticle": "article",
        "book": "book",
        "bookSection": "incollection",
        "conferencePaper": "inproceedings",
        "thesis": "phdthesis",
        "report": "techreport",
        "manuscript": "unpublished",
        "preprint": "article",
    }
    return mapping.get(item_type, "misc")


def _format_bibtex_authors(creators: list[Creator] | None) -> str:
    if not creators:
        return ""
    author_names = []
    for c in creators:
        if c.creatorType != "author":
            continue
        if c.lastName and c.firstName:
            author_names.append(f"{c.lastName}, {c.firstName}")
        elif c.lastName:
            author_names.append(c.lastName)
        elif c.firstName:
            author_names.append(c.firstName)
    return " and ".join(author_names)
