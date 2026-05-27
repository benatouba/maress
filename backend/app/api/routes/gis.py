"""GIS capabilities and spatial operations API.

This module exposes:
- A capability endpoint for dynamic frontend tool availability.
- Synchronous MVP GIS operations backed by PostGIS.
"""

from __future__ import annotations

import json
import logging
import uuid
from decimal import Decimal
from enum import Enum
from typing import Any

from celery.result import AsyncResult
from fastapi import APIRouter, HTTPException, Query
from geoalchemy2 import Geography, Geometry
from sqlalchemy import cast
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, OptionalCurrentUser, SessionDep
from app.celery_app import celery
from app.models import (
    GISAsyncOperationRequest,
    GISAsyncTaskAccepted,
    GISAsyncTaskRef,
    GISBufferRequest,
    GISBufferResult,
    GISBufferedFeature,
    GISCapabilitiesPublic,
    GISClipRequest,
    GISClipResult,
    GISFeatureSetRef,
    GISOperationCapability,
    GISPreset,
    GISPresetCreate,
    GISPresetPublic,
    GISPresetsPublic,
    GISPresetUpdate,
    GISRegionFeature,
    GISSummaryStatsPublic,
    GISSummaryStatsRequest,
    GISWithinDistanceRequest,
    GISWithinDistanceResult,
    Item,
    Location,
    Region,
    StudySite,
    StudySiteMapPoint,
    User,
)
from app.tasks.gis import run_gis_operation_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gis", tags=["gis"])


def _geojson_or_none(value: str | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return json.loads(value)


def _to_meters(distance: float, unit: str) -> float:
    if unit == "meter":
        return distance
    if unit == "kilometer":
        return distance * 1000.0
    raise HTTPException(status_code=400, detail=f"Unsupported distance unit '{unit}'")


def _normalized_bbox(bbox: list[float]) -> tuple[float, float, float, float]:
    min_lon, min_lat, max_lon, max_lat = bbox
    return (
        max(-180.0, min_lon),
        max(-90.0, min_lat),
        min(180.0, max_lon),
        min(90.0, max_lat),
    )


def _study_site_selection_predicates(ref: GISFeatureSetRef) -> list[Any]:
    selection = ref.selection
    predicates: list[Any] = []
    if selection.type == "ids":
        if not selection.ids:
            raise HTTPException(status_code=400, detail="selection.ids is required")
        predicates.append(col(StudySite.id).in_(selection.ids))
    elif selection.type == "bbox":
        if not selection.bbox:
            raise HTTPException(status_code=400, detail="selection.bbox is required")
        min_lon, min_lat, max_lon, max_lat = _normalized_bbox(selection.bbox)
        envelope = func.ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
        predicates.append(func.ST_Intersects(Location.geom, envelope))
    elif selection.type == "geometry":
        if not selection.geometry:
            raise HTTPException(status_code=400, detail="selection.geometry is required")
        geometry_text = json.dumps(selection.geometry)
        geometry = func.ST_SetSRID(func.ST_GeomFromGeoJSON(geometry_text), 4326)
        predicates.append(func.ST_Intersects(Location.geom, geometry))
    return predicates


def _region_selection_predicates(ref: GISFeatureSetRef, owner_id: uuid.UUID) -> list[Any]:
    selection = ref.selection
    predicates: list[Any] = [Region.owner_id == owner_id]
    if selection.type == "ids":
        if not selection.ids:
            raise HTTPException(status_code=400, detail="selection.ids is required")
        predicates.append(col(Region.id).in_(selection.ids))
    elif selection.type == "bbox":
        if not selection.bbox:
            raise HTTPException(status_code=400, detail="selection.bbox is required")
        min_lon, min_lat, max_lon, max_lat = _normalized_bbox(selection.bbox)
        envelope = func.ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
        predicates.append(func.ST_Intersects(Region.geom, envelope))
    elif selection.type == "geometry":
        if not selection.geometry:
            raise HTTPException(status_code=400, detail="selection.geometry is required")
        geometry_text = json.dumps(selection.geometry)
        geometry = func.ST_SetSRID(func.ST_GeomFromGeoJSON(geometry_text), 4326)
        predicates.append(func.ST_Intersects(Region.geom, geometry))
    return predicates


def _coerce_json_value(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Enum):
        return value.value
    return value


def _study_site_base_query(ref: GISFeatureSetRef):
    columns: list[Any] = [
        col(StudySite.id),
        col(StudySite.name),
        col(StudySite.item_id),
        col(Location.latitude),
        col(Location.longitude),
    ]
    statement = (
        select(*columns)
        .select_from(StudySite)
        .join(Location, StudySite.location_id == Location.id)
    )
    predicates = _study_site_selection_predicates(ref)
    if predicates:
        statement = statement.where(*predicates)
    return statement


@router.get("/capabilities", response_model=GISCapabilitiesPublic)
def get_capabilities(current_user: OptionalCurrentUser) -> GISCapabilitiesPublic:
    """Return GIS tool capabilities for the current user context."""
    can_run_ops = current_user is not None and current_user.is_active

    operations = [
        GISOperationCapability(
            id="buffer",
            label="Buffer",
            description="Create geometry buffers around selected features",
            permission="analysis.buffer",
            execution="sync",
            requires_authentication=True,
            enabled=can_run_ops,
            geometry_inputs=["Point", "Polygon"],
            parameter_schema={
                "distance": {"type": "number", "minimum": 0},
                "unit": {"type": "string", "enum": ["meter", "kilometer"]},
                "dissolve": {"type": "boolean"},
            },
        ),
        GISOperationCapability(
            id="clip",
            label="Clip",
            description="Clip selected features against a region selection",
            permission="analysis.clip",
            execution="sync",
            requires_authentication=True,
            enabled=can_run_ops,
            geometry_inputs=["Point", "Polygon"],
            parameter_schema={
                "target": {"type": "object"},
                "clip_with": {"type": "object"},
            },
        ),
        GISOperationCapability(
            id="within-distance",
            label="Within Distance",
            description="Find features within a given distance",
            permission="analysis.within_distance",
            execution="sync",
            requires_authentication=True,
            enabled=can_run_ops,
            geometry_inputs=["Point", "Polygon"],
            parameter_schema={
                "distance": {"type": "number", "minimum": 0},
                "unit": {"type": "string", "enum": ["meter", "kilometer"]},
                "return": {"type": "string", "enum": ["source", "against"]},
            },
        ),
        GISOperationCapability(
            id="summary-stats",
            label="Summary Stats",
            description="Aggregate grouped statistics over selected features",
            permission="analysis.summary_stats",
            execution="sync",
            requires_authentication=True,
            enabled=can_run_ops,
            geometry_inputs=["Point", "Polygon"],
            parameter_schema={
                "group_by": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": [
                            "item_id",
                            "is_manual",
                            "extraction_method",
                            "source_type",
                            "section",
                            "item_title",
                        ],
                    },
                },
                "metrics": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["count", "avg", "min", "max", "sum"],
                            },
                            "field": {
                                "type": "string",
                                "enum": ["id", "item_id", "confidence_score", "validation_score"],
                            },
                            "alias": {"type": "string"},
                        },
                        "required": ["type", "field"],
                    },
                },
            },
        ),
    ]

    return GISCapabilitiesPublic(
        version="draft-v1",
        operations=operations,
        limits={
            "max_features_sync": 25000,
            "max_group_fields": 5,
        },
    )


@router.post("/operations/buffer", response_model=GISBufferResult)
def buffer_operation(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    request: GISBufferRequest,
) -> GISBufferResult:
    """Create simple buffers around selected study-site points or regions."""
    logger.info("Buffer operation: layer=%s, distance=%s%s", request.target.layer_id, request.parameters.distance, request.parameters.unit)
    distance_meters = _to_meters(request.parameters.distance, request.parameters.unit)

    if request.target.layer_id == "study-sites":
        statement = (
            _study_site_base_query(request.target)
            .add_columns(
                func.ST_AsGeoJSON(
                    func.ST_Buffer(cast(Location.geom, Geography), distance_meters),
                ).label("geometry_json"),
            )
        )
        rows = session.exec(statement).all()

        features: list[GISBufferedFeature] = []
        for row in rows:
            geom = _geojson_or_none(row[5])
            if geom is None:
                continue
            features.append(
                GISBufferedFeature(
                    source_id=row[0],
                    geometry=geom,
                ),
            )

        return GISBufferResult(
            target_layer_id="study-sites",
            distance_meters=distance_meters,
            dissolved=False,
            count=len(features),
            features=features,
        )

    if request.target.layer_id == "regions":
        region_preds = _region_selection_predicates(request.target, current_user.id)
        buffer_geom = func.ST_Buffer(cast(Region.geom, Geography), distance_meters)
        buffer_geom_as_geometry = cast(buffer_geom, Geometry)

        if request.parameters.dissolve:
            statement = (
                select(
                    func.ST_AsGeoJSON(func.ST_UnaryUnion(func.ST_Collect(buffer_geom_as_geometry))).label(
                        "geometry_json",
                    ),
                )
                .select_from(Region)
                .where(*region_preds)
            )
            row = session.exec(statement).first()
            features: list[GISBufferedFeature] = []
            if row:
                geometry_json = row if isinstance(row, str) else row[0]
                geom = _geojson_or_none(geometry_json)
                if geom is not None:
                    features.append(GISBufferedFeature(source_id=None, geometry=geom))
            return GISBufferResult(
                target_layer_id="regions",
                distance_meters=distance_meters,
                dissolved=True,
                count=len(features),
                features=features,
            )

        statement = (
            select(
                Region.id,
                func.ST_AsGeoJSON(buffer_geom_as_geometry).label("geometry_json"),
            )
            .select_from(Region)
            .where(*region_preds)
        )
        rows = session.exec(statement).all()

        features: list[GISBufferedFeature] = []
        for row in rows:
            geom = _geojson_or_none(row[1])
            if geom is None:
                continue
            features.append(GISBufferedFeature(source_id=row[0], geometry=geom))

        return GISBufferResult(
            target_layer_id="regions",
            distance_meters=distance_meters,
            dissolved=False,
            count=len(features),
            features=features,
        )

    raise HTTPException(status_code=400, detail="Unsupported target layer for buffer")


@router.post("/operations/clip", response_model=GISClipResult)
def clip_operation(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    request: GISClipRequest,
) -> GISClipResult:
    """Clip study sites to selected region geometries (spatial within filter)."""
    logger.info("Clip operation: target=%s, clip_with=%s", request.target.layer_id, request.clip_with.layer_id)
    if request.target.layer_id != "study-sites" or request.clip_with.layer_id != "regions":
        raise HTTPException(
            status_code=400,
            detail="clip currently supports target=study-sites and clip_with=regions",
        )

    study_preds = _study_site_selection_predicates(request.target)
    region_preds = _region_selection_predicates(request.clip_with, current_user.id)

    region_contains_site_exists = (
        select(col(Region.id))
        .where(*region_preds)
        .where(func.ST_Within(Location.geom, Region.geom))
        .exists()
    )

    clip_columns: list[Any] = [
        col(StudySite.id),
        col(StudySite.name),
        col(StudySite.item_id),
        col(Item.title).label("item_title"),
        col(Location.latitude),
        col(Location.longitude),
        col(StudySite.is_manual),
        col(StudySite.confidence_score),
    ]

    statement = (
        select(*clip_columns)
        .select_from(StudySite)
        .join(Location, StudySite.location_id == Location.id)
        .join(Item, StudySite.item_id == Item.id)
        .where(*study_preds)
        .where(region_contains_site_exists)
        .distinct()
    )
    rows = session.exec(statement).all()

    points = [
        StudySiteMapPoint(
            id=row[0],
            name=row[1],
            item_id=row[2],
            item_title=row[3],
            latitude=float(row[4]),
            longitude=float(row[5]),
            is_manual=row[6],
            confidence_score=row[7],
        )
        for row in rows
    ]

    return GISClipResult(
        target_layer_id="study-sites",
        clip_layer_id="regions",
        count=len(points),
        study_sites=points,
    )


@router.post("/operations/within-distance", response_model=GISWithinDistanceResult)
def within_distance(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    request: GISWithinDistanceRequest,
) -> GISWithinDistanceResult:
    """Return features that satisfy ST_DWithin between study sites and regions."""
    logger.info("Within-distance operation: source=%s, against=%s, distance=%s%s", request.source.layer_id, request.against.layer_id, request.parameters.distance, request.parameters.unit)
    layer_pair = {request.source.layer_id, request.against.layer_id}
    if layer_pair != {"study-sites", "regions"}:
        raise HTTPException(
            status_code=400,
            detail="within-distance currently supports only study-sites <-> regions",
        )

    distance_meters = _to_meters(request.parameters.distance, request.parameters.unit)
    if request.source.layer_id == "study-sites":
        study_ref = request.source
        region_ref = request.against
    else:
        study_ref = request.against
        region_ref = request.source

    study_preds = _study_site_selection_predicates(study_ref)
    region_preds = _region_selection_predicates(region_ref, current_user.id)
    return_source = (
        request.parameters.return_target == "source" and request.source.layer_id == "study-sites"
    ) or (
        request.parameters.return_target == "against" and request.against.layer_id == "study-sites"
    )

    if return_source:
        source_columns: list[Any] = [
            col(StudySite.id),
            col(StudySite.name),
            col(StudySite.item_id),
            col(Item.title).label("item_title"),
            col(Location.latitude),
            col(Location.longitude),
            col(StudySite.is_manual),
            col(StudySite.confidence_score),
        ]

        matching_region_exists = (
            select(col(Region.id))
            .where(*region_preds)
            .where(
                func.ST_DWithin(
                    cast(Location.geom, Geography),
                    cast(Region.geom, Geography),
                    distance_meters,
                ),
            )
            .exists()
        )

        statement = (
            select(*source_columns)
            .select_from(StudySite)
            .join(Location, StudySite.location_id == Location.id)
            .join(Item, StudySite.item_id == Item.id)
            .where(*study_preds)
            .where(matching_region_exists)
            .distinct()
        )

        rows = session.exec(statement).all()
        points = [
            StudySiteMapPoint(
                id=row[0],
                name=row[1],
                item_id=row[2],
                item_title=row[3],
                latitude=float(row[4]),
                longitude=float(row[5]),
                is_manual=row[6],
                confidence_score=row[7],
            )
            for row in rows
        ]

        return GISWithinDistanceResult(
            source_layer_id=request.source.layer_id,
            against_layer_id=request.against.layer_id,
            return_layer_id="study-sites",
            distance_meters=distance_meters,
            count=len(points),
            study_sites=points,
        )

    matching_study_exists = (
        select(col(StudySite.id))
        .select_from(StudySite)
        .join(Location, col(StudySite.location_id) == col(Location.id))
        .where(*study_preds)
        .where(
            func.ST_DWithin(
                cast(Location.geom, Geography),
                cast(Region.geom, Geography),
                distance_meters,
            ),
        )
        .exists()
    )

    statement = select(Region.id, Region.name).where(*region_preds).where(matching_study_exists).distinct()
    rows = session.exec(statement).all()
    regions = [GISRegionFeature(id=row[0], name=row[1]) for row in rows]

    return GISWithinDistanceResult(
        source_layer_id=request.source.layer_id,
        against_layer_id=request.against.layer_id,
        return_layer_id="regions",
        distance_meters=distance_meters,
        count=len(regions),
        regions=regions,
    )


@router.post("/operations/summary-stats", response_model=GISSummaryStatsPublic)
def summary_stats(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    request: GISSummaryStatsRequest,
) -> GISSummaryStatsPublic:
    """Aggregate grouped metrics for selected study sites."""
    logger.info("Summary-stats operation: group_by=%s, metrics=%d", request.group_by, len(request.metrics))
    if request.target.layer_id != "study-sites":
        raise HTTPException(
            status_code=400,
            detail="summary-stats currently supports only target.layer_id='study-sites'",
        )

    group_fields: dict[str, Any] = {
        "item_id": col(StudySite.item_id),
        "is_manual": col(StudySite.is_manual),
        "extraction_method": col(StudySite.extraction_method),
        "source_type": col(StudySite.source_type),
        "section": col(StudySite.section),
        "item_title": col(Item.title),
    }
    count_fields: dict[str, Any] = {
        "id": col(StudySite.id),
        "item_id": col(StudySite.item_id),
    }
    avg_fields: dict[str, Any] = {
        "confidence_score": col(StudySite.confidence_score),
        "validation_score": col(StudySite.validation_score),
    }
    min_max_sum_fields: dict[str, Any] = {
        "confidence_score": col(StudySite.confidence_score),
        "validation_score": col(StudySite.validation_score),
    }

    selected_group_fields: list[str] = []
    select_expressions: list[Any] = []
    group_expressions: list[Any] = []

    for field_name in request.group_by:
        column = group_fields.get(field_name)
        if column is None:
            raise HTTPException(status_code=400, detail=f"Unsupported group_by field '{field_name}'")
        select_expressions.append(column.label(field_name))
        group_expressions.append(column)
        selected_group_fields.append(field_name)

    metric_names: list[str] = []
    for metric in request.metrics:
        if metric.type == "count":
            col_expr = count_fields.get(metric.field)
            if col_expr is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported count field '{metric.field}'",
                )
            alias = metric.alias or f"count_{metric.field}"
            select_expressions.append(func.count(col_expr).label(alias))
            metric_names.append(alias)
            continue

        if metric.type == "avg":
            col_expr = avg_fields.get(metric.field)
            if col_expr is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported avg field '{metric.field}'",
                )
            alias = metric.alias or f"avg_{metric.field}"
            select_expressions.append(func.avg(col_expr).label(alias))
            metric_names.append(alias)
            continue

        if metric.type == "min":
            col_expr = min_max_sum_fields.get(metric.field)
            if col_expr is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported min field '{metric.field}'",
                )
            alias = metric.alias or f"min_{metric.field}"
            select_expressions.append(func.min(col_expr).label(alias))
            metric_names.append(alias)
            continue

        if metric.type == "max":
            col_expr = min_max_sum_fields.get(metric.field)
            if col_expr is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported max field '{metric.field}'",
                )
            alias = metric.alias or f"max_{metric.field}"
            select_expressions.append(func.max(col_expr).label(alias))
            metric_names.append(alias)
            continue

        if metric.type == "sum":
            col_expr = min_max_sum_fields.get(metric.field)
            if col_expr is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported sum field '{metric.field}'",
                )
            alias = metric.alias or f"sum_{metric.field}"
            select_expressions.append(func.sum(col_expr).label(alias))
            metric_names.append(alias)
            continue

        raise HTTPException(status_code=400, detail=f"Unsupported metric type '{metric.type}'")

    statement = (
        select(*select_expressions)
        .select_from(StudySite)
        .join(Location, StudySite.location_id == Location.id)
    )

    if "item_title" in selected_group_fields:
        statement = statement.join(Item, StudySite.item_id == Item.id)

    target_preds = _study_site_selection_predicates(request.target)
    if target_preds:
        statement = statement.where(*target_preds)

    if request.spatial_filter is not None:
        if request.spatial_filter.layer_id != "regions":
            raise HTTPException(status_code=400, detail="Unsupported spatial_filter layer")

        filter_ref = GISFeatureSetRef(
            layer_id="regions",
            selection=request.spatial_filter.selection,
        )
        region_preds = _region_selection_predicates(filter_ref, current_user.id)

        predicate = request.spatial_filter.predicate
        if predicate == "within":
            spatial_exists = (
                select(Region.id)
                .where(*region_preds)
                .where(func.ST_Within(Location.geom, Region.geom))
                .exists()
            )
        elif predicate == "intersects":
            spatial_exists = (
                select(Region.id)
                .where(*region_preds)
                .where(func.ST_Intersects(Location.geom, Region.geom))
                .exists()
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported spatial_filter predicate '{predicate}'",
            )

        statement = statement.where(spatial_exists)

    if group_expressions:
        statement = statement.group_by(*group_expressions)

    rows = session.exec(statement).all()
    column_names = selected_group_fields + metric_names
    payload_rows: list[dict[str, Any]] = []

    for row in rows:
        if hasattr(row, "_mapping"):
            raw = dict(row._mapping)
        elif isinstance(row, tuple):
            raw = {column_names[idx]: row[idx] for idx in range(len(column_names))}
        else:
            raw = {column_names[0]: row}

        payload_rows.append({k: _coerce_json_value(v) for k, v in raw.items()})

    return GISSummaryStatsPublic(rows=payload_rows, count=len(payload_rows))


def execute_gis_operation(
    *,
    session: SessionDep,
    current_user: User,
    operation_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Execute one GIS operation and return JSON-serializable payload."""
    if operation_id == "buffer":
        request = GISBufferRequest.model_validate(payload)
        result = buffer_operation(session=session, current_user=current_user, request=request)
        return result.model_dump(mode="json")

    if operation_id == "clip":
        request = GISClipRequest.model_validate(payload)
        result = clip_operation(session=session, current_user=current_user, request=request)
        return result.model_dump(mode="json")

    if operation_id == "within-distance":
        request = GISWithinDistanceRequest.model_validate(payload)
        result = within_distance(session=session, current_user=current_user, request=request)
        return result.model_dump(mode="json")

    if operation_id == "summary-stats":
        request = GISSummaryStatsRequest.model_validate(payload)
        result = summary_stats(session=session, current_user=current_user, request=request)
        return result.model_dump(mode="json")

    raise HTTPException(status_code=400, detail=f"Unsupported GIS operation '{operation_id}'")


@router.post("/operations/async", response_model=GISAsyncTaskAccepted, status_code=202)
def start_async_operation(
    *,
    current_user: CurrentUser,
    request: GISAsyncOperationRequest,
) -> GISAsyncTaskAccepted:
    """Queue a GIS operation in Celery and return task reference."""
    # Validate request payload upfront for fast feedback.
    if request.operation_id == "buffer":
        GISBufferRequest.model_validate(request.payload)
    elif request.operation_id == "clip":
        GISClipRequest.model_validate(request.payload)
    elif request.operation_id == "within-distance":
        GISWithinDistanceRequest.model_validate(request.payload)
    elif request.operation_id == "summary-stats":
        GISSummaryStatsRequest.model_validate(request.payload)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported GIS operation '{request.operation_id}'",
        )

    async_result = run_gis_operation_task.delay(
        operation_id=request.operation_id,
        payload=request.payload,
        user_id=str(current_user.id),
        is_superuser=bool(current_user.is_superuser),
    )
    return GISAsyncTaskAccepted(
        data=GISAsyncTaskRef(
            task_id=async_result.id,
            operation_id=request.operation_id,
            status="queued",
            message="Task queued",
        ),
    )


@router.get("/tasks/{task_id}")
def get_gis_task_status(
    *,
    task_id: str,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Get status for one queued GIS task."""
    del current_user
    result = AsyncResult(task_id, app=celery)

    response: dict[str, Any] = {
        "task_id": task_id,
        "state": result.state,
        "status": result.status,
        "ready": result.ready(),
        "successful": result.successful() if result.ready() else None,
        "failed": result.failed() if result.ready() else None,
    }

    if result.ready():
        if result.successful():
            response["result"] = result.result
        else:
            error_info = result.info
            if isinstance(error_info, dict):
                response["error"] = error_info
            else:
                response["error"] = {
                    "message": str(error_info),
                    "type": type(error_info).__name__,
                }
    elif isinstance(result.info, dict):
        response["result"] = result.info

    if isinstance(result.info, dict):
        response["metadata"] = result.info

    return response


@router.get("/tasks/batch/")
def get_gis_batch_task_status(
    *,
    task_ids: str = Query(description="Comma-separated task IDs"),
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Get status of multiple GIS tasks at once."""
    del current_user
    ids = [tid.strip() for tid in task_ids.split(",") if tid.strip()]

    if not ids:
        raise HTTPException(status_code=400, detail="No task IDs provided")

    if len(ids) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 tasks can be queried at once")

    tasks: dict[str, Any] = {}
    for task_id in ids:
        result = AsyncResult(task_id, app=celery)
        tasks[task_id] = {
            "status": result.status,
            "ready": result.ready(),
            "successful": result.successful() if result.ready() else None,
            "failed": result.failed() if result.ready() else None,
        }

    statuses = [entry["status"] for entry in tasks.values()]
    ready_tasks = [entry for entry in tasks.values() if entry["ready"]]

    return {
        "tasks": tasks,
        "summary": {
            "total": len(tasks),
            "pending": statuses.count("PENDING"),
            "started": statuses.count("STARTED"),
            "success": statuses.count("SUCCESS"),
            "failure": statuses.count("FAILURE"),
            "retry": statuses.count("RETRY"),
            "ready": len(ready_tasks),
            "successful": sum(1 for entry in ready_tasks if entry.get("successful")),
            "failed": sum(1 for entry in ready_tasks if entry.get("failed")),
        },
    }


@router.delete("/tasks/{task_id}")
def cancel_gis_task(
    *,
    task_id: str,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Cancel a queued/running GIS task."""
    del current_user
    celery.control.revoke(task_id, terminate=True, signal="SIGTERM")
    result = AsyncResult(task_id, app=celery)
    return {
        "task_id": task_id,
        "message": "Task cancellation requested",
        "previous_status": result.status,
        "cancelled": True,
    }


def _preset_public(preset: GISPreset) -> GISPresetPublic:
    try:
        config = json.loads(preset.config_json)
    except (TypeError, json.JSONDecodeError):
        config = {}

    return GISPresetPublic(
        id=preset.id,
        owner_id=preset.owner_id,
        name=preset.name,
        operation_id=preset.operation_id,
        config=config,
        created_at=preset.created_at,
        updated_at=preset.updated_at,
    )


@router.get("/presets", response_model=GISPresetsPublic)
def list_gis_presets(
    *,
    session: SessionDep,
    current_user: CurrentUser,
) -> GISPresetsPublic:
    """List current user's saved GIS presets."""
    statement = (
        select(GISPreset)
        .where(GISPreset.owner_id == current_user.id)
        .order_by(col(GISPreset.created_at).desc())
    )
    presets = list(session.exec(statement).all())
    data = [_preset_public(preset) for preset in presets]
    return GISPresetsPublic(data=data, count=len(data))


@router.post("/presets", response_model=GISPresetPublic, status_code=201)
def create_gis_preset(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    preset_in: GISPresetCreate,
) -> GISPresetPublic:
    """Create a GIS analysis preset."""
    preset = GISPreset(
        owner_id=current_user.id,
        name=preset_in.name,
        operation_id=preset_in.operation_id,
        config_json=json.dumps(preset_in.config),
    )
    session.add(preset)
    session.commit()
    session.refresh(preset)
    return _preset_public(preset)


@router.put("/presets/{preset_id}", response_model=GISPresetPublic)
def update_gis_preset(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    preset_id: uuid.UUID,
    preset_in: GISPresetUpdate,
) -> GISPresetPublic:
    """Update an existing GIS preset."""
    preset = session.get(GISPreset, preset_id)
    if preset is None or preset.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Preset not found")

    if preset_in.name is not None:
        preset.name = preset_in.name
    if preset_in.operation_id is not None:
        preset.operation_id = preset_in.operation_id
    if preset_in.config is not None:
        preset.config_json = json.dumps(preset_in.config)

    session.add(preset)
    session.commit()
    session.refresh(preset)
    return _preset_public(preset)


@router.delete("/presets/{preset_id}")
def delete_gis_preset(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    preset_id: uuid.UUID,
) -> dict[str, str]:
    """Delete one GIS preset."""
    preset = session.get(GISPreset, preset_id)
    if preset is None or preset.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Preset not found")

    session.delete(preset)
    session.commit()
    return {"message": "Preset deleted"}
