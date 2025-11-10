# Manual Study Site Management API

## Overview

The Manual Study Site Management API allows users to perform CRUD (Create, Read, Update, Delete) operations on study sites extracted from scientific papers. This enables human oversight and correction of algorithm results.

### Key Features

- **View study sites**: List all study sites (automatic and manual) for a specific item
- **Create manual sites**: Add study sites that the algorithm missed
- **Update existing sites**: Correct coordinates, names, or other attributes
- **Delete false positives**: Remove incorrectly identified study sites
- **Track provenance**: `is_manual` flag indicates human vs. algorithm origin
- **Get statistics**: View breakdown of manual vs. automatic study sites

### Human-in-the-Loop Workflow

1. **Algorithm extracts** study sites from PDF → `is_manual=False`
2. **User reviews** extracted sites via API
3. **User corrects** mistakes by updating sites → `is_manual=True`
4. **User adds** missing sites → `is_manual=True`
5. **User removes** false positives via DELETE

---

## Authentication

All endpoints require authentication via JWT bearer token:

```bash
Authorization: Bearer <your_jwt_token>
```

Users can only access study sites for items they own, unless they are superusers.

---

## Endpoints

### 1. List Study Sites for an Item

**GET** `/api/items/{item_id}/study-sites`

Returns all study sites (automatic and manual) for a specific item, ordered by confidence score.

#### Request

```bash
curl -X GET "http://localhost:8000/api/items/123e4567-e89b-12d3-a456-426614174000/study-sites" \
  -H "Authorization: Bearer <token>"
```

#### Response (200 OK)

```json
{
  "data": [
    {
      "id": "987fbc97-4bed-5078-9f07-9141ba07c9f3",
      "name": "Study Site A",
      "latitude": 45.5231,
      "longitude": -122.6765,
      "context": "Our main study site was located at...",
      "confidence_score": 0.95,
      "validation_score": 0.90,
      "extraction_method": "COORDINATE",
      "source_type": "TEXT",
      "section": "methods",
      "is_manual": false,
      "item_id": "123e4567-e89b-12d3-a456-426614174000",
      "location_id": "456e7890-e12b-34c5-d678-901234567890",
      "created_at": "2025-11-10T10:30:00Z",
      "updated_at": "2025-11-10T10:30:00Z"
    },
    {
      "id": "abc12345-6789-0def-1234-567890abcdef",
      "name": "Additional Site (Manual)",
      "latitude": 45.6789,
      "longitude": -122.8901,
      "context": "Manually added by user - site mentioned in supplementary materials",
      "confidence_score": 1.0,
      "validation_score": 1.0,
      "extraction_method": "MANUAL",
      "source_type": "MANUAL",
      "section": "OTHER",
      "is_manual": true,
      "item_id": "123e4567-e89b-12d3-a456-426614174000",
      "location_id": "789abc12-3456-78de-f012-345678901234",
      "created_at": "2025-11-10T14:15:00Z",
      "updated_at": "2025-11-10T14:15:00Z"
    }
  ],
  "count": 2
}
```

#### Errors

- **404 Not Found**: Item does not exist
- **403 Forbidden**: User does not have permission to access this item

---

### 2. Get Single Study Site

**GET** `/api/study-sites/{study_site_id}`

Retrieves a specific study site by ID.

#### Request

```bash
curl -X GET "http://localhost:8000/api/study-sites/987fbc97-4bed-5078-9f07-9141ba07c9f3" \
  -H "Authorization: Bearer <token>"
```

#### Response (200 OK)

```json
{
  "id": "987fbc97-4bed-5078-9f07-9141ba07c9f3",
  "name": "Study Site A",
  "latitude": 45.5231,
  "longitude": -122.6765,
  "context": "Our main study site was located at...",
  "confidence_score": 0.95,
  "validation_score": 0.90,
  "extraction_method": "COORDINATE",
  "source_type": "TEXT",
  "section": "methods",
  "is_manual": false,
  "item_id": "123e4567-e89b-12d3-a456-426614174000",
  "location_id": "456e7890-e12b-34c5-d678-901234567890",
  "created_at": "2025-11-10T10:30:00Z",
  "updated_at": "2025-11-10T10:30:00Z"
}
```

#### Errors

- **404 Not Found**: Study site does not exist
- **403 Forbidden**: User does not have permission to access this study site

---

### 3. Create Manual Study Site

**POST** `/api/items/{item_id}/study-sites`

Manually create a new study site for an item. This is useful for adding sites that the algorithm missed.

#### Request

```bash
curl -X POST "http://localhost:8000/api/items/123e4567-e89b-12d3-a456-426614174000/study-sites" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Northern Research Station",
    "latitude": 47.6062,
    "longitude": -122.3321,
    "context": "Supplementary site mentioned in appendix but not detected by algorithm",
    "confidence_score": 1.0,
    "validation_score": 1.0
  }'
```

#### Request Body

```json
{
  "name": "Northern Research Station",
  "latitude": 47.6062,
  "longitude": -122.3321,
  "context": "Supplementary site mentioned in appendix",
  "confidence_score": 1.0,
  "validation_score": 1.0
}
```

**Required Fields:**
- `name` (string, max 255 chars): Name of the study site
- `latitude` (float, -90 to 90): Latitude coordinate
- `longitude` (float, -180 to 180): Longitude coordinate

**Optional Fields:**
- `context` (string): Description or context about the site (default: "Manually added by user")
- `confidence_score` (float, 0-1): Confidence in the coordinates (default: 1.0)
- `validation_score` (float, 0-1): Validation score (default: 1.0)

#### Response (200 OK)

```json
{
  "id": "new-uuid-here",
  "name": "Northern Research Station",
  "latitude": 47.6062,
  "longitude": -122.3321,
  "context": "Supplementary site mentioned in appendix",
  "confidence_score": 1.0,
  "validation_score": 1.0,
  "extraction_method": "MANUAL",
  "source_type": "MANUAL",
  "section": "OTHER",
  "is_manual": true,
  "item_id": "123e4567-e89b-12d3-a456-426614174000",
  "location_id": "generated-location-id",
  "created_at": "2025-11-10T15:00:00Z",
  "updated_at": "2025-11-10T15:00:00Z"
}
```

#### Errors

- **404 Not Found**: Item does not exist
- **403 Forbidden**: User does not have permission to create study sites for this item
- **422 Unprocessable Entity**: Invalid coordinates or validation errors

---

### 4. Update Study Site

**PUT** `/api/study-sites/{study_site_id}`

**PATCH** `/api/study-sites/{study_site_id}` (alias)

Update an existing study site (automatic or manual). When a user modifies any study site, it is automatically marked as `is_manual=True` to indicate human oversight.

#### Request

```bash
curl -X PUT "http://localhost:8000/api/study-sites/987fbc97-4bed-5078-9f07-9141ba07c9f3" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Study Site A (Corrected)",
    "latitude": 45.5250,
    "longitude": -122.6800,
    "context": "Corrected coordinates based on field verification"
  }'
```

#### Request Body

All fields are optional. Only include fields you want to update:

```json
{
  "name": "Study Site A (Corrected)",
  "latitude": 45.5250,
  "longitude": -122.6800,
  "context": "Corrected coordinates based on field verification",
  "confidence_score": 0.98,
  "validation_score": 0.95
}
```

**Optional Fields:**
- `name` (string, max 255 chars): Updated name
- `latitude` (float, -90 to 90): Updated latitude
- `longitude` (float, -180 to 180): Updated longitude
- `context` (string): Updated context/description
- `confidence_score` (float, 0-1): Updated confidence score
- `validation_score` (float, 0-1): Updated validation score

#### Response (200 OK)

```json
{
  "id": "987fbc97-4bed-5078-9f07-9141ba07c9f3",
  "name": "Study Site A (Corrected)",
  "latitude": 45.5250,
  "longitude": -122.6800,
  "context": "Corrected coordinates based on field verification",
  "confidence_score": 0.98,
  "validation_score": 0.95,
  "extraction_method": "MANUAL",
  "source_type": "TEXT",
  "section": "methods",
  "is_manual": true,
  "item_id": "123e4567-e89b-12d3-a456-426614174000",
  "location_id": "updated-location-id",
  "created_at": "2025-11-10T10:30:00Z",
  "updated_at": "2025-11-10T15:30:00Z"
}
```

**Note:** The `is_manual` flag is automatically set to `true` and `extraction_method` is changed to `MANUAL` when any update is made.

#### Errors

- **404 Not Found**: Study site does not exist
- **403 Forbidden**: User does not have permission to update this study site
- **422 Unprocessable Entity**: Invalid coordinates or validation errors

---

### 5. Delete Study Site

**DELETE** `/api/study-sites/{study_site_id}`

Delete a study site. This is useful for removing false positives identified by the algorithm.

#### Request

```bash
curl -X DELETE "http://localhost:8000/api/study-sites/987fbc97-4bed-5078-9f07-9141ba07c9f3" \
  -H "Authorization: Bearer <token>"
```

#### Response (200 OK)

```json
{
  "message": "Study site deleted successfully"
}
```

#### Errors

- **404 Not Found**: Study site does not exist
- **403 Forbidden**: User does not have permission to delete this study site

---

### 6. Get Study Site Statistics

**GET** `/api/items/{item_id}/study-sites/stats`

Get statistics about study sites for an item, including counts of automatic vs manual sites and confidence distribution.

#### Request

```bash
curl -X GET "http://localhost:8000/api/items/123e4567-e89b-12d3-a456-426614174000/study-sites/stats" \
  -H "Authorization: Bearer <token>"
```

#### Response (200 OK)

```json
{
  "total": 15,
  "manual": 3,
  "automatic": 12,
  "average_confidence": 0.87,
  "extraction_methods": {
    "COORDINATE": 8,
    "GPE": 4,
    "MANUAL": 3
  }
}
```

**Response Fields:**
- `total`: Total number of study sites for this item
- `manual`: Number of sites created or modified by humans
- `automatic`: Number of sites created automatically by the algorithm
- `average_confidence`: Mean confidence score across all sites
- `extraction_methods`: Breakdown of extraction methods used

#### Errors

- **404 Not Found**: Item does not exist
- **403 Forbidden**: User does not have permission to access this item

---

## Usage Scenarios

### Scenario 1: User Reviews Algorithm Results

1. User uploads PDF → algorithm extracts study sites
2. User calls **GET /items/{item_id}/study-sites** to review results
3. User calls **GET /items/{item_id}/study-sites/stats** to see overview
4. User identifies issues with specific sites

### Scenario 2: User Corrects Coordinates

1. Algorithm extracted site with coordinates (45.123, -122.456) but they're slightly wrong
2. User calls **PUT /study-sites/{study_site_id}** with corrected coordinates:
   ```json
   {
     "latitude": 45.125,
     "longitude": -122.458,
     "context": "Corrected based on Google Maps verification"
   }
   ```
3. Study site is now marked as `is_manual=true`

### Scenario 3: User Adds Missing Site

1. Algorithm missed a study site mentioned only in supplementary materials
2. User calls **POST /items/{item_id}/study-sites** with manual coordinates:
   ```json
   {
     "name": "Supplementary Site B",
     "latitude": 46.234,
     "longitude": -123.567,
     "context": "Mentioned in Table S2 of supplementary materials"
   }
   ```
3. New study site created with `is_manual=true`

### Scenario 4: User Removes False Positive

1. Algorithm incorrectly identified author affiliation as study site
2. User calls **DELETE /study-sites/{study_site_id}**
3. False positive removed from database

### Scenario 5: Batch Quality Control

1. User processes 100 papers
2. User calls **GET /items/{item_id}/study-sites/stats** for each paper
3. User identifies papers with low `average_confidence` or high `automatic` counts
4. User manually reviews and corrects those papers first

---

## Python Client Example

```python
import httpx
from typing import List, Dict, Any

class StudySiteClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {token}"}

    def get_study_sites(self, item_id: str) -> Dict[str, Any]:
        """Get all study sites for an item."""
        response = httpx.get(
            f"{self.base_url}/api/items/{item_id}/study-sites",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

    def create_manual_site(
        self,
        item_id: str,
        name: str,
        latitude: float,
        longitude: float,
        context: str = "",
    ) -> Dict[str, Any]:
        """Create a manual study site."""
        response = httpx.post(
            f"{self.base_url}/api/items/{item_id}/study-sites",
            headers=self.headers,
            json={
                "name": name,
                "latitude": latitude,
                "longitude": longitude,
                "context": context,
            }
        )
        response.raise_for_status()
        return response.json()

    def update_site(
        self,
        study_site_id: str,
        **updates
    ) -> Dict[str, Any]:
        """Update a study site."""
        response = httpx.put(
            f"{self.base_url}/api/study-sites/{study_site_id}",
            headers=self.headers,
            json=updates
        )
        response.raise_for_status()
        return response.json()

    def delete_site(self, study_site_id: str) -> Dict[str, str]:
        """Delete a study site."""
        response = httpx.delete(
            f"{self.base_url}/api/study-sites/{study_site_id}",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

    def get_stats(self, item_id: str) -> Dict[str, Any]:
        """Get study site statistics for an item."""
        response = httpx.get(
            f"{self.base_url}/api/items/{item_id}/study-sites/stats",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

# Usage
client = StudySiteClient("http://localhost:8000", "your-jwt-token")

# Get all study sites
sites = client.get_study_sites("123e4567-e89b-12d3-a456-426614174000")
print(f"Found {sites['count']} study sites")

# Create manual site
new_site = client.create_manual_site(
    item_id="123e4567-e89b-12d3-a456-426614174000",
    name="Manual Site",
    latitude=45.5231,
    longitude=-122.6765,
    context="Added from supplementary materials"
)
print(f"Created site: {new_site['id']}")

# Update coordinates
updated = client.update_site(
    study_site_id=new_site['id'],
    latitude=45.5250,
    context="Corrected coordinates"
)
print(f"Updated site, is_manual={updated['is_manual']}")

# Get statistics
stats = client.get_stats("123e4567-e89b-12d3-a456-426614174000")
print(f"Manual: {stats['manual']}, Automatic: {stats['automatic']}")

# Delete false positive
client.delete_site(study_site_id="some-id")
print("Deleted false positive")
```

---

## Data Model

### StudySite Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Unique identifier |
| `name` | string | Name of the study site |
| `latitude` | float | Latitude (-90 to 90) |
| `longitude` | float | Longitude (-180 to 180) |
| `context` | string | Surrounding text or description |
| `confidence_score` | float | Algorithm confidence (0-1) |
| `validation_score` | float | Validation score (0-1) |
| `extraction_method` | enum | COORDINATE, GPE, LOC, SPATIAL_RELATION, MANUAL |
| `source_type` | enum | TEXT, TABLE, FIGURE, MANUAL |
| `section` | enum | methods, results, introduction, etc. |
| `is_manual` | boolean | **True if created/modified by human** |
| `item_id` | UUID | Associated item (PDF paper) |
| `location_id` | UUID | Associated location (geocoded) |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last update timestamp |

### Coordinate Validation

- **Latitude**: Must be between -90 and 90
- **Longitude**: Must be between -180 and 180
- Coordinates are automatically validated on create/update
- Invalid coordinates will result in 422 Unprocessable Entity error

---

## Best Practices

1. **Review before deleting**: Always check the `context` field before deleting to ensure it's actually a false positive

2. **Add context when creating**: Always provide meaningful context when creating manual sites:
   ```json
   {
     "context": "Mentioned in supplementary Table S2, verified with Google Maps"
   }
   ```

3. **Use appropriate confidence scores**:
   - Manual sites with verified coordinates: `1.0`
   - Manual sites with approximate coordinates: `0.8-0.9`
   - Corrected automatic sites: Keep or adjust based on correction

4. **Check statistics first**: Before manual review, check `/stats` endpoint to understand the automatic/manual ratio

5. **Preserve extraction metadata**: When updating automatic sites, consider whether to preserve the original `extraction_method` for tracking

6. **Batch processing**: For multiple corrections, consider batching API calls to reduce overhead

---

## Testing

### Manual Testing with curl

```bash
# Set variables
export API_URL="http://localhost:8000"
export TOKEN="your-jwt-token-here"
export ITEM_ID="123e4567-e89b-12d3-a456-426614174000"

# List study sites
curl -X GET "$API_URL/api/items/$ITEM_ID/study-sites" \
  -H "Authorization: Bearer $TOKEN"

# Create manual site
curl -X POST "$API_URL/api/items/$ITEM_ID/study-sites" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Site",
    "latitude": 45.5,
    "longitude": -122.6,
    "context": "Test manual creation"
  }'

# Get statistics
curl -X GET "$API_URL/api/items/$ITEM_ID/study-sites/stats" \
  -H "Authorization: Bearer $TOKEN"
```

### Integration Testing

Create tests in `tests/api/test_study_sites.py`:

```python
def test_create_manual_study_site(client, normal_user_token_headers, test_item):
    """Test creating a manual study site."""
    data = {
        "name": "Test Manual Site",
        "latitude": 45.5231,
        "longitude": -122.6765,
        "context": "Test context"
    }
    response = client.post(
        f"/api/items/{test_item.id}/study-sites",
        headers=normal_user_token_headers,
        json=data
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == "Test Manual Site"
    assert content["is_manual"] is True
    assert content["extraction_method"] == "MANUAL"
```

---

## Troubleshooting

### Issue: 403 Forbidden

**Cause**: User doesn't own the item or isn't a superuser

**Solution**: Verify the user owns the item or has superuser privileges

### Issue: 422 Unprocessable Entity on coordinates

**Cause**: Coordinates outside valid range

**Solution**: Ensure latitude is -90 to 90, longitude is -180 to 180

### Issue: Study site not showing as manual after update

**Cause**: This should not happen - `is_manual` is automatically set to `True` on update

**Solution**: Check the API response - if `is_manual` is still `False`, this is a bug

### Issue: Location not updating when coordinates change

**Cause**: Location is managed automatically via `create_location_if_needed`

**Solution**: This is expected behavior - locations are deduplicated by coordinates

---

## Migration Information

The `is_manual` field was added via Alembic migration `9a2729365f82`:

- **Added column**: `is_manual` (boolean, NOT NULL, default False)
- **Added index**: `ix_studysite_is_manual` for efficient filtering
- **Backward compatible**: Existing study sites are automatically marked as `is_manual=False`

To apply the migration:

```bash
uv run alembic upgrade head
```

To rollback:

```bash
uv run alembic downgrade -1
```

---

## API Documentation

The API is automatically documented via FastAPI's built-in Swagger UI and ReDoc:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

All endpoints include request/response schemas and examples in the interactive documentation.
