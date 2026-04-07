"""Precision-first tests for section-level gating in the orchestrator."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.nlp.model_config import ModelConfig
from app.nlp.orchestrator import StudySiteExtractionPipeline
from app.nlp.pdf_parser import PDFParser


class _DummyParser(PDFParser):
    def parse(self, pdf_path: Path) -> Any:  # pragma: no cover - not exercised
        raise NotImplementedError


def _pipeline(config: ModelConfig) -> StudySiteExtractionPipeline:
    return StudySiteExtractionPipeline(
        config=config,
        pdf_parser=_DummyParser(),
        extractors=[],
        enable_geocoding=False,
        enable_clustering=False,
        enable_table_extraction=False,
        enable_quality_assessment=False,
        enable_enriched_context=False,
        enable_context_filtering=False,
        enable_bounding_box_extraction=False,
        enable_ml_section_classifier=False,
        enable_spatial_resolution=False,
        enable_temporal_filtering=False,
        enable_location_name_merging=False,
        enable_coreference_resolution=False,
        enable_abbreviation_expansion=False,
        enable_uncertainty_detection=False,
        enable_validation=False,
    )


def test_low_signal_section_requires_explicit_study_cue() -> None:
    pipeline = _pipeline(ModelConfig())

    assert not pipeline._is_study_site_relevant_section(
        "introduction",
        "Paris was discussed in previous literature.",
    )
    assert pipeline._is_study_site_relevant_section(
        "introduction",
        "Study sites were located in Paris and sampled monthly.",
    )


def test_methods_section_remains_allowed() -> None:
    pipeline = _pipeline(ModelConfig())

    assert pipeline._is_study_site_relevant_section(
        "methods",
        "Samples were collected at two stations.",
    )


def test_irrelevant_sections_are_blocked() -> None:
    pipeline = _pipeline(ModelConfig())

    assert not pipeline._is_study_site_relevant_section(
        "references",
        "Smith et al. 2020.",
    )
    assert not pipeline._is_study_site_relevant_section(
        "author_information",
        "Department of Biology, University of X.",
    )


def test_non_strict_mode_allows_unknown_sections() -> None:
    config = ModelConfig(STRICT_SECTION_FILTERING=False)
    pipeline = _pipeline(config)

    assert pipeline._is_study_site_relevant_section(
        "other",
        "No clear cue text.",
    )
