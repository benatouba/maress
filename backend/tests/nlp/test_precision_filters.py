"""Precision-first tests for section/context filtering and geocoding gating."""

from __future__ import annotations

from app.nlp.context_filter import ContextFilter
from app.nlp.domain_models import GeoEntity
from app.nlp.geocoding import CachedGeocoder


def _entity(
    text: str,
    *,
    entity_type: str = "GPE",
    section: str = "methods",
    context: str | None = None,
    confidence: float = 0.9,
) -> GeoEntity:
    return GeoEntity(
        text=text,
        entity_type=entity_type,
        context=context or f"Study site located in {text}",
        section=section,
        confidence=confidence,
        start_char=0,
        end_char=max(1, len(text)),
    )


def test_context_filter_blocks_reference_sections() -> None:
    filt = ContextFilter()
    candidate = _entity(
        "Paris",
        section="references",
        context="References: Smith et al. (2021) Paris dataset.",
    )

    assert filt.should_filter(candidate)
    assert filt.get_filter_reason(candidate) == "blocked_section"


def test_context_filter_blocks_generic_location_terms() -> None:
    filt = ContextFilter()
    generic = _entity(
        "study area",
        entity_type="LOC",
        section="methods",
        context="Our study area was monitored weekly.",
    )

    assert filt.should_filter(generic)
    assert filt.get_filter_reason(generic) == "generic_location_term"


def test_context_filter_requires_cues_in_low_signal_section() -> None:
    filt = ContextFilter()
    low_signal = _entity(
        "London",
        section="introduction",
        context="London has been widely discussed in prior literature.",
    )
    cue_present = _entity(
        "London",
        section="introduction",
        context="The study site was located in London for this campaign.",
    )

    assert filt.should_filter(low_signal)
    assert not filt.should_filter(cue_present)


def test_geocoder_low_signal_requires_high_confidence_and_context_cue() -> None:
    geocoder = CachedGeocoder(user_agent="test", rate_limit=0.0, allow_live_requests=False)
    geocoder.strict_low_signal_section_min_confidence = 0.9
    geocoder.require_context_cue_for_low_signal_section = True

    low_conf = _entity(
        "Quito",
        section="results",
        context="Quito appeared in comparative analysis.",
        confidence=0.82,
    )
    no_cue = _entity(
        "Quito",
        section="results",
        context="Quito appeared in comparative analysis.",
        confidence=0.95,
    )
    with_cue = _entity(
        "Quito",
        section="results",
        context="Study sites were located in Quito and sampled monthly.",
        confidence=0.95,
    )

    assert not geocoder._is_geocoding_candidate(low_conf)
    assert not geocoder._is_geocoding_candidate(no_cue)
    assert geocoder._is_geocoding_candidate(with_cue)
