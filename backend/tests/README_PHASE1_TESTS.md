# Phase 1 Test Suite Documentation

This document describes the comprehensive test suite created for Phase 1 critical fixes.

## Overview

Phase 1 implemented critical bug fixes and improvements to the study site extraction system. The test suite ensures these fixes work correctly and prevents regressions.

## Test Files

### 1. `tests/tasks/test_extract.py`
**Tests for multi-site storage fix**

Tests the critical bug fix that ensures ALL study sites are saved, not just the primary one.

**Test Cases:**
- ✅ `test_extract_single_study_site` - Verifies single site extraction and storage
- ✅ `test_extract_multiple_study_sites` - **Critical test** for multi-site storage across different clusters
- ✅ `test_skip_existing_sites_without_force` - Verifies skip logic when sites exist
- ✅ `test_force_reextraction` - Verifies force flag triggers re-extraction
- ✅ `test_no_pdf_attachment` - Handles missing PDF gracefully
- ✅ `test_pdf_not_found` - Handles file not found errors
- ✅ `test_no_study_sites_found` - Handles empty extraction results
- ✅ `test_permission_denied` - Verifies authorization
- ✅ `test_location_deduplication` - Verifies identical coordinates share Location records

**Key Assertions:**
```python
# Verify all 4 sites saved, not just primary
assert result["count"] == 4
assert "1 primary + 3 additional" in result["message"]
assert len(item.study_sites) == 4
```

### 2. `tests/nlp/test_study_site_extraction.py`
**Tests for NLP extraction improvements**

Tests geocoding cache, clustering improvements, and table extraction.

#### Test Class: `TestLocationExtractorCache`
**Tests for geocoding cache and rate limiting**

- ✅ `test_geocoding_cache_hit` - Verifies cache prevents duplicate API calls
- ✅ `test_geocoding_cache_negative_result` - Verifies failed lookups are cached
- ✅ `test_geocoding_rate_limiting` - Verifies 1 req/sec rate limit enforcement

**Key Assertions:**
```python
# Second call should use cache, not hit geocoder again
assert mock_geocode.call_count == 1  # Still 1, not 2

# Rate limiting: 3 requests should take ~2 seconds
assert elapsed >= 2.0
```

#### Test Class: `TestCoordinateClusterer`
**Tests for clustering that preserves all regions**

- ✅ `test_single_cluster_preservation` - Single geographic region clustering
- ✅ `test_multiple_clusters_preservation` - **Critical test** for multi-cluster preservation
- ✅ `test_cluster_sorting_by_size` - Verifies largest cluster comes first
- ✅ `test_noise_points_handling` - Handles DBSCAN noise points

**Key Assertions:**
```python
# All 4 candidates returned, not just largest cluster
assert len(result) == 4

# 3 distinct clusters preserved
assert len(cluster_info) == 3
assert cluster_info["cluster_0"] == 2  # Ecuador
assert cluster_info["cluster_1"] == 1  # Peru
assert cluster_info["cluster_2"] == 1  # Chile
```

#### Test Class: `TestTableExtraction`
**Tests for table coordinate extraction**

- ✅ `test_extract_coordinates_from_table` - Basic table extraction
- ✅ `test_table_with_alternative_column_names` - Handles lat/lon/x/y variations
- ✅ `test_table_with_site_names` - Extracts site names from tables
- ✅ `test_table_with_invalid_coordinates` - Skips invalid data
- ✅ `test_table_without_coordinate_columns` - Skips non-coordinate tables
- ✅ `test_multiple_tables` - Processes multiple tables

**Key Assertions:**
```python
# Verify table extraction works
assert len(result) == 3
assert all(c.extraction_method == CoordinateExtractionMethod.TABLE_PARSING for c in result)
assert all(c.confidence_score == 0.9 for c in result)  # High confidence
```

#### Test Class: `TestStudySiteExtractorIntegration`
**Integration tests**

- ✅ `test_table_extraction_integrated` - Verifies table extraction called in main pipeline

### 3. `tests/api/routes/test_task_status.py`
**Tests for new task status endpoints**

Tests the three new API endpoints for monitoring extraction progress.

#### Test Class: `TestTaskStatusEndpoint`
**Tests for GET /api/v1/items/tasks/{task_id}**

- ✅ `test_get_pending_task_status` - Retrieves pending task info
- ✅ `test_get_successful_task_status` - Retrieves completed task results
- ✅ `test_get_failed_task_status` - Retrieves error information
- ✅ `test_get_task_status_requires_auth` - Verifies authentication required

**Key Assertions:**
```python
assert data["status"] == "SUCCESS"
assert data["ready"] is True
assert data["result"]["count"] == 1
```

#### Test Class: `TestBatchTaskStatusEndpoint`
**Tests for GET /api/v1/items/tasks/batch/?task_ids=...**

- ✅ `test_get_batch_task_status_multiple_tasks` - Handles multiple task IDs
- ✅ `test_batch_task_status_empty_ids` - Rejects empty input
- ✅ `test_batch_task_status_too_many_ids` - Enforces 100 task limit
- ✅ `test_batch_task_status_comma_separated` - Handles spaces in input

**Key Assertions:**
```python
assert summary["total"] == 3
assert summary["success"] == 1
assert summary["pending"] == 1
assert summary["failure"] == 1
```

#### Test Class: `TestExtractionSummaryEndpoint`
**Tests for GET /api/v1/items/tasks/summary/**

- ✅ `test_get_extraction_summary` - Returns summary statistics
- ✅ `test_extraction_summary_empty_database` - Handles empty database
- ✅ `test_extraction_summary_requires_auth` - Verifies authentication
- ✅ `test_extraction_summary_by_method_breakdown` - Verifies method breakdown

**Key Assertions:**
```python
assert "total_study_sites" in data
assert "coverage_percentage" in data
assert "average_confidence" in data
assert "by_extraction_method" in data
```

#### Test Class: `TestTaskStatusIntegration`
**Integration tests**

- ✅ `test_task_status_after_extraction` - End-to-end workflow test

## Running the Tests

### Run all Phase 1 tests:
```bash
cd backend
uv run pytest tests/tasks/test_extract.py tests/nlp/test_study_site_extraction.py tests/api/routes/test_task_status.py -v
```

### Run specific test files:
```bash
# Task extraction tests
uv run pytest tests/tasks/test_extract.py -v

# NLP extraction tests
uv run pytest tests/nlp/test_study_site_extraction.py -v

# API endpoint tests
uv run pytest tests/api/routes/test_task_status.py -v
```

### Run with coverage:
```bash
uv run pytest tests/tasks/ tests/nlp/test_study_site_extraction.py tests/api/routes/test_task_status.py --cov=app.tasks --cov=app.nlp --cov=app.api.routes.items --cov-report=html
```

### Run specific test:
```bash
uv run pytest tests/tasks/test_extract.py::TestExtractStudySiteTask::test_extract_multiple_study_sites -v
```

## Test Coverage

### Components Tested:
- ✅ **Multi-site storage** (`app/tasks/extract.py`)
- ✅ **Geocoding cache** (`app/nlp/find_my_home.py::LocationExtractor`)
- ✅ **Rate limiting** (`app/nlp/find_my_home.py::LocationExtractor`)
- ✅ **Multi-cluster preservation** (`app/nlp/find_my_home.py::CoordinateClusterer`)
- ✅ **Table extraction** (`app/nlp/find_my_home.py::CoordinateExtractor`)
- ✅ **Task status endpoints** (`app/api/routes/items.py`)

### Critical Paths Tested:
1. **Multi-site workflow**: Item → Extract → Multiple Sites → Database
2. **Caching workflow**: Location → Geocode → Cache → Reuse
3. **Clustering workflow**: Candidates → DBSCAN → All Clusters → Ranked
4. **Table workflow**: PDF → Tables → Parse → Extract → Candidates
5. **Task status workflow**: Trigger → Query Status → Get Results

## Fixtures Used

### From `tests/conftest.py`:
- `db_session` - Database session for tests
- `client` - FastAPI test client
- `superuser_token_headers` - Superuser authentication
- `normal_user_token_headers` - Regular user authentication
- `model_manager` - spaCy model manager

### Custom Fixtures:
- `mock_pdf_path` - Temporary PDF file
- `item_with_pdf` - Item with PDF attachment
- `mock_single_site_result` - Single study site extraction result
- `mock_multi_site_result` - Multiple study sites extraction result

## Mocking Strategy

### External Services Mocked:
- ✅ Celery AsyncResult (task status)
- ✅ Nominatim geocoder (external API)
- ✅ StudySiteExtractor (NLP pipeline)
- ✅ PDF processing (file I/O)

### Database Operations:
- ✅ Real database operations (using test database)
- ✅ Transactions rolled back after each test

## Expected Test Results

All tests should pass:
```
tests/tasks/test_extract.py::TestExtractStudySiteTask::test_extract_single_study_site PASSED
tests/tasks/test_extract.py::TestExtractStudySiteTask::test_extract_multiple_study_sites PASSED
tests/tasks/test_extract.py::TestExtractStudySiteTask::test_skip_existing_sites_without_force PASSED
tests/tasks/test_extract.py::TestExtractStudySiteTask::test_force_reextraction PASSED
tests/tasks/test_extract.py::TestExtractStudySiteTask::test_no_pdf_attachment PASSED
tests/tasks/test_extract.py::TestExtractStudySiteTask::test_pdf_not_found PASSED
tests/tasks/test_extract.py::TestExtractStudySiteTask::test_no_study_sites_found PASSED
tests/tasks/test_extract.py::TestExtractStudySiteTask::test_permission_denied PASSED
tests/tasks/test_extract.py::TestExtractStudySiteTask::test_location_deduplication PASSED

tests/nlp/test_study_site_extraction.py::TestLocationExtractorCache::test_geocoding_cache_hit PASSED
tests/nlp/test_study_site_extraction.py::TestLocationExtractorCache::test_geocoding_cache_negative_result PASSED
tests/nlp/test_study_site_extraction.py::TestLocationExtractorCache::test_geocoding_rate_limiting PASSED
tests/nlp/test_study_site_extraction.py::TestCoordinateClusterer::test_single_cluster_preservation PASSED
tests/nlp/test_study_site_extraction.py::TestCoordinateClusterer::test_multiple_clusters_preservation PASSED
tests/nlp/test_study_site_extraction.py::TestCoordinateClusterer::test_cluster_sorting_by_size PASSED
tests/nlp/test_study_site_extraction.py::TestCoordinateClusterer::test_noise_points_handling PASSED
tests/nlp/test_study_site_extraction.py::TestTableExtraction::test_extract_coordinates_from_table PASSED
tests/nlp/test_study_site_extraction.py::TestTableExtraction::test_table_with_alternative_column_names PASSED
tests/nlp/test_study_site_extraction.py::TestTableExtraction::test_table_with_site_names PASSED
tests/nlp/test_study_site_extraction.py::TestTableExtraction::test_table_with_invalid_coordinates PASSED
tests/nlp/test_study_site_extraction.py::TestTableExtraction::test_table_without_coordinate_columns PASSED
tests/nlp/test_study_site_extraction.py::TestTableExtraction::test_multiple_tables PASSED
tests/nlp/test_study_site_extraction.py::TestStudySiteExtractorIntegration::test_table_extraction_integrated PASSED

tests/api/routes/test_task_status.py::TestTaskStatusEndpoint::test_get_pending_task_status PASSED
tests/api/routes/test_task_status.py::TestTaskStatusEndpoint::test_get_successful_task_status PASSED
tests/api/routes/test_task_status.py::TestTaskStatusEndpoint::test_get_failed_task_status PASSED
tests/api/routes/test_task_status.py::TestTaskStatusEndpoint::test_get_task_status_requires_auth PASSED
tests/api/routes/test_task_status.py::TestBatchTaskStatusEndpoint::test_get_batch_task_status_multiple_tasks PASSED
tests/api/routes/test_task_status.py::TestBatchTaskStatusEndpoint::test_batch_task_status_empty_ids PASSED
tests/api/routes/test_task_status.py::TestBatchTaskStatusEndpoint::test_batch_task_status_too_many_ids PASSED
tests/api/routes/test_task_status.py::TestBatchTaskStatusEndpoint::test_batch_task_status_comma_separated PASSED
tests/api/routes/test_task_status.py::TestExtractionSummaryEndpoint::test_get_extraction_summary PASSED
tests/api/routes/test_task_status.py::TestExtractionSummaryEndpoint::test_extraction_summary_empty_database PASSED
tests/api/routes/test_task_status.py::TestExtractionSummaryEndpoint::test_extraction_summary_requires_auth PASSED
tests/api/routes/test_task_status.py::TestExtractionSummaryEndpoint::test_extraction_summary_by_method_breakdown PASSED
tests/api/routes/test_task_status.py::TestTaskStatusIntegration::test_task_status_after_extraction PASSED

================================= 35 passed in X.XXs =================================
```

## Troubleshooting

### Import Errors
If you see import errors, ensure you're running from the backend directory:
```bash
cd backend
uv run pytest tests/...
```

### Database Connection Errors
Ensure PostgreSQL is running and test database can be created:
```bash
psql -U postgres -c "CREATE DATABASE maress_test;"
```

### SpaCy Model Missing
Download required spaCy model:
```bash
uv run python -m spacy download en_core_web_lg
```

## Next Steps

After Phase 1 tests pass, proceed to Phase 2:
- Accuracy improvements (regex patterns, false positive filtering)
- Additional validation tests
- Performance benchmarking tests
