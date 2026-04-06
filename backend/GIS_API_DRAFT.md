# GIS Frontend and PostGIS API Draft

Status: draft-v1
Owner: backend + frontend
Scope: operations contract for a GIS-like workflow in MaRESS

## Goals

- Provide a stable contract so frontend can expose GIS tools dynamically.
- Keep heavy spatial operations in PostGIS and run them as jobs.
- Support both app UI and external GIS clients with predictable endpoints.
- Enforce permissions server-side for every operation.

## Design Principles

- Layer-first: operations run against layer references, not ad-hoc blobs only.
- Capability-driven UI: frontend renders tools from server capabilities.
- Async by default: heavy geoprocessing should return jobs (`202 Accepted`).
- Deterministic outputs: each job can produce a named result layer.
- Auditability: every operation stores parameters, owner, and timestamps.

## API Namespace

All endpoints below assume `"/api/v1"` prefix.

- `GET /gis/capabilities`
- `GET /gis/layers`
- `GET /gis/layers/{layer_id}`
- `GET /gis/layers/{layer_id}/features`
- `GET /gis/layers/{layer_id}/tiles/{z}/{x}/{y}.pbf`
- `POST /gis/operations/buffer`
- `POST /gis/operations/clip`
- `POST /gis/operations/intersect`
- `POST /gis/operations/within-distance`
- `POST /gis/operations/summary-stats`
- `GET /gis/jobs/{job_id}`
- `GET /gis/jobs/{job_id}/result`
- `DELETE /gis/jobs/{job_id}`

## Authentication and Authorization

- Read-only map browsing can stay public where needed.
- All operations endpoints require authenticated users.
- Capabilities endpoint returns user-scoped operation visibility.
- Each operation includes a permission string, for example:
  - `analysis.buffer`
  - `analysis.clip`
  - `analysis.intersect`
  - `analysis.within_distance`
  - `analysis.summary_stats`

## Core Schemas

### FeatureSetRef

```json
{
  "layer_id": "study-sites",
  "selection": {
    "type": "all"
  }
}
```

Supported `selection.type`:

- `all`
- `ids` (feature ids)
- `bbox` (`[minLon, minLat, maxLon, maxLat]`)
- `geojson` (Polygon/MultiPolygon)

### OperationAccepted (async)

```json
{
  "job_id": "3b9aa3d8-b2f9-4d09-a92b-1ca6bf11bfc7",
  "status": "queued",
  "operation": "buffer",
  "submitted_at": "2026-04-01T10:10:10Z"
}
```

### JobStatus

```json
{
  "job_id": "3b9aa3d8-b2f9-4d09-a92b-1ca6bf11bfc7",
  "operation": "buffer",
  "status": "running",
  "progress": 42,
  "message": "Applying ST_Buffer",
  "result_layer_id": null,
  "error": null,
  "started_at": "2026-04-01T10:10:20Z",
  "finished_at": null
}
```

### OperationResult

```json
{
  "operation": "buffer",
  "result_layer_id": "layer_7f7c8d",
  "feature_count": 1268,
  "duration_ms": 3210,
  "warnings": []
}
```

## Capabilities Contract

`GET /gis/capabilities`

```json
{
  "version": "draft-v1",
  "operations": [
    {
      "id": "buffer",
      "label": "Buffer",
      "description": "Create distance buffers around features",
      "permission": "analysis.buffer",
      "geometry_inputs": ["Point", "LineString", "Polygon"],
      "execution": "async",
      "parameter_schema": {
        "distance": { "type": "number", "minimum": 0 },
        "unit": { "type": "string", "enum": ["meter", "kilometer"] },
        "dissolve": { "type": "boolean" }
      }
    }
  ],
  "limits": {
    "max_features_sync": 5000,
    "max_job_runtime_seconds": 900
  }
}
```

Frontend should render tools from this response.

## Operations Draft

### 1) Buffer

`POST /gis/operations/buffer`

```json
{
  "target": {
    "layer_id": "study-sites",
    "selection": { "type": "bbox", "bbox": [-10, 40, 10, 60] }
  },
  "parameters": {
    "distance": 1000,
    "unit": "meter",
    "dissolve": false,
    "join_style": "round",
    "end_cap": "round"
  },
  "output": {
    "name": "sites_buffer_1km",
    "persist": true
  }
}
```

PostGIS core: `ST_Buffer` (prefer geography for meter-based buffers on EPSG:4326).

### 2) Clip

`POST /gis/operations/clip`

```json
{
  "target": {
    "layer_id": "study-sites",
    "selection": { "type": "all" }
  },
  "clip_with": {
    "layer_id": "regions",
    "selection": { "type": "ids", "ids": ["region_123"] }
  },
  "parameters": {
    "keep_attributes": true
  },
  "output": {
    "name": "sites_clipped_region_123",
    "persist": true
  }
}
```

PostGIS core: `ST_Intersection` with prefilter `ST_Intersects`.

### 3) Intersect

`POST /gis/operations/intersect`

```json
{
  "left": {
    "layer_id": "regions",
    "selection": { "type": "ids", "ids": ["region_123"] }
  },
  "right": {
    "layer_id": "study-sites",
    "selection": { "type": "all" }
  },
  "parameters": {
    "predicate": "intersects",
    "return_geometry": true,
    "attribute_merge": "both"
  },
  "output": {
    "name": "region_sites_intersection",
    "persist": true
  }
}
```

PostGIS core: `ST_Intersects`, optional geometry output via `ST_Intersection`.

### 4) Within Distance

`POST /gis/operations/within-distance`

```json
{
  "source": {
    "layer_id": "study-sites",
    "selection": { "type": "all" }
  },
  "against": {
    "layer_id": "regions",
    "selection": { "type": "ids", "ids": ["region_123"] }
  },
  "parameters": {
    "distance": 5000,
    "unit": "meter",
    "return": "source"
  }
}
```

PostGIS core: `ST_DWithin` (geography for meters).

### 5) Summary Stats

`POST /gis/operations/summary-stats`

```json
{
  "target": {
    "layer_id": "study-sites",
    "selection": { "type": "all" }
  },
  "group_by": ["item_id", "is_manual"],
  "metrics": [
    { "type": "count", "field": "id", "alias": "site_count" },
    { "type": "avg", "field": "confidence_score", "alias": "avg_confidence" }
  ],
  "spatial_filter": {
    "layer_id": "regions",
    "selection": { "type": "ids", "ids": ["region_123"] },
    "predicate": "within"
  }
}
```

Response can be tabular JSON (no output layer required):

```json
{
  "rows": [
    {
      "item_id": "71bbf73d-4811-40bd-ac3a-b4b3ebd69a77",
      "is_manual": true,
      "site_count": 12,
      "avg_confidence": 0.91
    }
  ],
  "count": 1
}
```

## Error Model

All endpoints return:

```json
{
  "detail": "Human-readable message",
  "code": "invalid_selection",
  "hint": "Use selection.type=bbox with four coordinates"
}
```

Suggested error codes:

- `invalid_selection`
- `invalid_parameters`
- `permission_denied`
- `layer_not_found`
- `unsupported_geometry_type`
- `job_failed`

## Frontend Contract (recommended)

- On map/toolbox load: call `GET /gis/capabilities`.
- Build the tools menu from `operations[]`.
- Build tool forms from `parameter_schema`.
- Submit operation requests and track via `GET /gis/jobs/{job_id}`.
- Add `result_layer_id` to layer panel when complete.
- Store recent operations in user session for reproducibility.

## Suggested Execution Model

- FastAPI receives operation request and validates payload.
- Celery task executes SQL in PostGIS.
- Result saved as materialized layer table/view with metadata row.
- Frontend renders result via vector tiles (`.pbf`) and feature endpoint.

## Rollout Plan

1. Implement `GET /gis/capabilities` with static operation metadata.
2. Implement jobs API (`/gis/jobs/*`) and Celery plumbing.
3. Implement `within-distance` and `summary-stats` first (lowest UI complexity).
4. Implement `buffer`, `clip`, and `intersect` with persisted result layers.
5. Add vector tile endpoint for result layers and layer manager integration.

## Interoperability Notes

For compatibility with external GIS tools later:

- Expose OGC API Features style feature endpoints for layers.
- Keep CRS handling explicit (`EPSG:4326` input, `EPSG:3857` rendering path).
- Consider `pg_tileserv` or `martin` for tile serving at scale.
