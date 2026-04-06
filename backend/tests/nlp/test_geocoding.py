"""Tests for geocoding candidate filtering and batching behavior."""

from __future__ import annotations

from geopy.point import Point

from app.nlp.domain_models import GeoEntity
from app.nlp.geocoding import CachedGeocoder


def _entity(
    text: str,
    *,
    confidence: float = 0.9,
    entity_type: str = "GPE",
    section: str = "methods",
) -> GeoEntity:
    return GeoEntity(
        text=text,
        entity_type=entity_type,
        context=f"study site in {text}",
        section=section,
        confidence=confidence,
        start_char=0,
        end_char=max(1, len(text)),
    )


class DummyGeocoder(CachedGeocoder):
    """Deterministic geocoder for unit tests."""

    def __init__(self) -> None:
        super().__init__(user_agent="test", rate_limit=0.0)
        self.calls: list[str] = []

    def geocode(  # type: ignore[override]
        self,
        location_name: str,
        bias_point=None,
        bias_radius_km: float = 500.0,
        country_hints: set[str] | None = None,
        feature_hint: str | None = None,
    ) -> tuple[float, float] | None:
        self.calls.append(location_name)
        if "fail" in location_name.lower():
            self._last_error_was_rate_limit = False
            return None
        self._last_error_was_rate_limit = False
        return (10.0, 20.0)


def test_filters_low_signal_candidates() -> None:
    geocoder = DummyGeocoder()

    entities = [
        _entity("Quito", confidence=0.9),
        _entity("thebanks", confidence=0.95),
        _entity("Study area", confidence=0.99),
        _entity("A", confidence=0.99),
        _entity("Laguna Verde", confidence=0.8),
        _entity("13u13'09S", confidence=0.95),
    ]

    result = geocoder.geocode_entities(entities, max_candidates=20, min_confidence=0.55)

    # Only valid, high-signal names should be geocoded.
    assert sorted(geocoder.calls) == ["Laguna Verde", "Quito"]

    resolved = [e for e in result if e.coordinates is not None]
    assert len(resolved) == 2


def test_batches_by_unique_names_and_budget() -> None:
    geocoder = DummyGeocoder()

    entities = [
        _entity("Quito", confidence=0.95, section="methods"),
        _entity("Quito", confidence=0.92, section="results"),
        _entity("Cuenca", confidence=0.9, section="methods"),
        _entity("Loja", confidence=0.85, section="abstract"),
    ]

    result = geocoder.geocode_entities(entities, max_candidates=2, min_confidence=0.55)

    # Should geocode only top-2 unique names by confidence/section priority.
    assert len(geocoder.calls) == 2
    assert sorted(geocoder.calls) == ["Cuenca", "Quito"]

    # Both Quito mentions should share the same resolved coordinates.
    quito_entities = [e for e in result if e.text == "Quito"]
    assert len(quito_entities) == 2
    assert all(e.coordinates == (10.0, 20.0) for e in quito_entities)

    loja = next(e for e in result if e.text == "Loja")
    assert loja.coordinates is None


def test_offline_geocoding_uses_cache_only() -> None:
    geocoder = CachedGeocoder(user_agent="test", rate_limit=0.0, allow_live_requests=False)

    # Cache miss in offline mode should return None and store negative cache.
    assert geocoder.geocode("Quito") is None
    assert geocoder.cache.size() == 1

    # Repeated call should hit cache and keep cache size stable.
    assert geocoder.geocode("Quito") is None
    assert geocoder.cache.size() == 1


def test_export_and_import_cache_entries_round_trip() -> None:
    source = CachedGeocoder(user_agent="test", rate_limit=0.0)
    source.cache.set("Quito", (-0.2201641, -78.5123274))
    source.cache.set("Unknown Place", None)

    payload = source.export_cache_entries()

    target = CachedGeocoder(user_agent="test", rate_limit=0.0, allow_live_requests=False)
    loaded = target.import_cache_entries(payload)

    assert loaded == 2
    assert target.geocode("Quito") == (-0.2201641, -78.5123274)
    assert target.geocode("Unknown Place") is None


def test_import_cache_entries_skips_invalid_records() -> None:
    geocoder = CachedGeocoder(user_agent="test", rate_limit=0.0, allow_live_requests=False)

    loaded = geocoder.import_cache_entries(
        {
            "good": [1.0, 2.0],
            "none": None,
            "bad_type": "not-a-coordinate",
            "bad_len": [1.0],
            "bad_num": ["x", 2.0],
        }
    )

    assert loaded == 2
    assert geocoder.geocode("good") == (1.0, 2.0)
    assert geocoder.geocode("none") is None


def test_country_hints_are_inferred_from_entities() -> None:
    geocoder = CachedGeocoder(user_agent="test", rate_limit=0.0, allow_live_requests=False)

    entities = [
        _entity("Laguna Miscanti", section="methods"),
        _entity("Northern Chile", section="study_area"),
    ]

    hints = geocoder._infer_country_hints(entities, bias_point=None)
    assert "cl" in hints


def test_distance_guard_rejects_far_geocode() -> None:
    geocoder = CachedGeocoder(user_agent="test", rate_limit=0.0, allow_live_requests=False)

    assert geocoder._passes_distance_guard(
        (0.0, 0.0),
        document_bias=None,
        per_candidate_bias=None,
    )

    # Farther than per-candidate bias threshold -> reject
    assert not geocoder._passes_distance_guard(
        (0.0, 0.0),
        document_bias=None,
        per_candidate_bias=Point(latitude=40.0, longitude=-70.0),
    )


def test_filters_generic_determiner_phrases() -> None:
    geocoder = DummyGeocoder()

    entities = [
        _entity("the study site", confidence=0.95, section="methods"),
        _entity("this area", confidence=0.95, section="study_area"),
        _entity("Quito", confidence=0.9, section="methods"),
    ]

    _ = geocoder.geocode_entities(entities, max_candidates=20, min_confidence=0.55)

    assert geocoder.calls == ["Quito"]


def test_filters_non_location_content_fragments() -> None:
    geocoder = DummyGeocoder()

    entities = [
        _entity("regression indicates linear fit", confidence=0.98, section="results"),
        _entity("sampling equipment", confidence=0.98, section="methods"),
        _entity("Laguna Verde", confidence=0.9, section="study_area"),
    ]

    _ = geocoder.geocode_entities(entities, max_candidates=20, min_confidence=0.55)

    assert geocoder.calls == ["Laguna Verde"]


def test_uses_configurable_defaults_for_budget_and_confidence() -> None:
    geocoder = DummyGeocoder()
    geocoder.max_candidates_per_doc = 1
    geocoder.min_candidate_confidence = 0.9

    entities = [
        _entity("Quito", confidence=0.95, section="methods"),
        _entity("Cuenca", confidence=0.91, section="methods"),
        _entity("Loja", confidence=0.85, section="methods"),
    ]

    _ = geocoder.geocode_entities(entities)

    assert len(geocoder.calls) == 1
    assert geocoder.calls[0] in {"Quito", "Cuenca"}


def test_toggleable_phrase_filters_can_be_disabled() -> None:
    geocoder = DummyGeocoder()
    geocoder.reject_determiner_prefix = False
    geocoder.reject_non_location_content = False
    geocoder.require_capitalized_multi_token = False

    entities = [
        _entity("the study site", confidence=0.95, section="methods"),
        _entity("sampling equipment", confidence=0.95, section="methods"),
    ]

    _ = geocoder.geocode_entities(entities, max_candidates=20, min_confidence=0.55)

    assert sorted(geocoder.calls) == ["sampling equipment", "the study site"]
