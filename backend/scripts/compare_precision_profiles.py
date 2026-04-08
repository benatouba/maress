"""Compare baseline vs strict precision geocoding profiles on local PDFs.

This script runs the NLP extraction pipeline in-memory (no DB writes) and
prints a compact markdown table for quick before/after comparison.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from time import perf_counter

from app.core.config import settings
from app.nlp.domain_models import GeoEntity
from app.nlp.factories import PipelineFactory
from app.nlp.geocoding import CachedGeocoder
from app.nlp.model_config import ModelConfig

LOW_SIGNAL_SECTIONS = {
    "other",
    "introduction",
    "background",
    "discussion",
    "conclusion",
    "conclusions",
    "abstract",
    "results",
    "caption",
}

NON_TEXTUAL_SECTIONS = {
    "caption",
    "author_information",
    "references",
    "appendix",
}

TEXTUAL_STUDY_SITE_CUE_PATTERNS = [
    re.compile(
        r"(?:study|sampling|field|research)\s+(?:site|sites|area|location|station|plot)",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:located|situated|established|collected|sampled)\s+(?:at|in|near)\b", re.IGNORECASE),
    re.compile(r"\b(?:coordinates?|latitude|longitude|lat\.?|lon\.?)\b", re.IGNORECASE),
    re.compile(r"\b\d{1,2}(?:\.\d+)?\s*[°º]?\s*[NS]\b", re.IGNORECASE),
]

BASELINE_PROFILE = {
    "strict_low_signal_section_min_confidence": 0.90,
    "min_top_candidate_score": 0.85,
    "ambiguity_score_margin": 0.35,
    "ambiguity_distance_km": 250.0,
}

STRICT_PROFILE = {
    "strict_low_signal_section_min_confidence": 0.93,
    "min_top_candidate_score": 0.95,
    "ambiguity_score_margin": 0.45,
    "ambiguity_distance_km": 200.0,
}


@dataclass
class PdfMetrics:
    pdf_name: str
    seconds: float
    entities_total: int
    entities_with_coordinates: int
    loc_gpe_with_coordinates: int
    low_signal_loc_gpe_with_coordinates: int
    avg_conf_loc_gpe: float
    geocode_unique_candidates_total: int
    geocode_unique_candidates_geocoded: int
    geocode_rejections: int
    rejected_by_candidate_filters: int
    textual_coordinates: int
    map_image_coordinates: int
    has_textual_study_site_signal: bool


@dataclass
class PdfFailure:
    pdf_name: str
    error: str


def _is_map_image_entity(entity: GeoEntity) -> bool:
    return "[MAP_IMAGE" in entity.context


def _is_textual_coordinate_entity(entity: GeoEntity) -> bool:
    if entity.coordinates is None:
        return False
    if _is_map_image_entity(entity):
        return False
    section = entity.section.lower().strip()
    return section not in NON_TEXTUAL_SECTIONS


def _has_textual_study_site_signal(entities: list[GeoEntity]) -> bool:
    for entity in entities:
        section = entity.section.lower().strip()
        if section in NON_TEXTUAL_SECTIONS:
            continue
        if _is_map_image_entity(entity):
            continue
        if entity.coordinates is not None and entity.entity_type in {
            "COORDINATE",
            "LOC",
            "GPE",
            "SPATIAL_RELATION",
            "BOUNDING_BOX",
        }:
            return True
        if entity.entity_type in {"LOC", "GPE", "STUDY_SITE", "MULTIWORD_LOCATION", "CONTEXTUAL_LOCATION"}:
            if section in LOW_SIGNAL_SECTIONS:
                continue
            if any(pattern.search(entity.context) for pattern in TEXTUAL_STUDY_SITE_CUE_PATTERNS):
                return True
    return False


def _build_geocoder(profile: dict[str, float]) -> CachedGeocoder:
    return CachedGeocoder(
        rate_limit=settings.GEOCODING_RATE_LIMIT,
        allow_live_requests=settings.GEOCODING_ALLOW_LIVE_REQUESTS,
        max_candidates_per_doc=settings.GEOCODING_MAX_CANDIDATES_PER_DOC,
        min_candidate_confidence=settings.GEOCODING_MIN_CANDIDATE_CONFIDENCE,
        strict_other_section_min_confidence=settings.GEOCODING_STRICT_OTHER_SECTION_MIN_CONFIDENCE,
        reject_determiner_prefix=settings.GEOCODING_REJECT_DETERMINER_PREFIX,
        reject_non_location_content=settings.GEOCODING_REJECT_NON_LOCATION_CONTENT,
        require_capitalized_multi_token=settings.GEOCODING_REQUIRE_CAPITALIZED_MULTI_TOKEN,
        max_distance_without_bias_km=settings.GEOCODING_MAX_DISTANCE_WITHOUT_BIAS_KM,
        max_distance_with_bias_km=settings.GEOCODING_MAX_DISTANCE_WITH_BIAS_KM,
        max_distance_per_candidate_km=settings.GEOCODING_MAX_DISTANCE_PER_CANDIDATE_KM,
        require_context_cue_for_low_signal_section=settings.GEOCODING_REQUIRE_CONTEXT_CUE_FOR_LOW_SIGNAL_SECTION,
        strict_low_signal_section_min_confidence=profile["strict_low_signal_section_min_confidence"],
        min_top_candidate_score=profile["min_top_candidate_score"],
        ambiguity_score_margin=profile["ambiguity_score_margin"],
        ambiguity_distance_km=profile["ambiguity_distance_km"],
    )


def _select_pdfs(pdf_dir: Path, limit: int, extra_pdfs: list[Path]) -> list[Path]:
    candidates = [
        p for p in pdf_dir.glob("*.pdf") if p.is_file() and p.stat().st_size > 0
    ]
    candidates.sort(key=lambda p: (p.stat().st_size, p.name))

    selected = candidates[:limit]
    for extra in extra_pdfs:
        if extra.exists() and extra not in selected:
            selected.append(extra)

    return selected


def _run_profile(
    profile_name: str,
    profile: dict[str, float],
    pdfs: list[Path],
) -> tuple[list[PdfMetrics], list[PdfFailure]]:
    print(f"\n## Running profile: {profile_name}")
    config = ModelConfig()
    pipeline = PipelineFactory.create_pipeline_for_api(config=config)
    pipeline.geocoder = _build_geocoder(profile)

    rows: list[PdfMetrics] = []
    failures: list[PdfFailure] = []

    for index, pdf_path in enumerate(pdfs, start=1):
        try:
            started = perf_counter()
            result = pipeline.extract_from_pdf(pdf_path)
            elapsed = perf_counter() - started
        except Exception as exc:
            failures.append(PdfFailure(pdf_name=pdf_path.name, error=str(exc)))
            print(f"[{index:02d}/{len(pdfs):02d}] {pdf_path.name}: FAILED ({exc})")
            continue

        entities = result.entities
        entities_with_coords = [e for e in entities if e.coordinates is not None]
        loc_gpe_with_coords = [
            e for e in entities_with_coords if e.entity_type in {"LOC", "GPE"}
        ]
        low_signal_loc_gpe = [
            e
            for e in loc_gpe_with_coords
            if e.section.lower().strip() in LOW_SIGNAL_SECTIONS
        ]
        textual_coordinates = [
            e
            for e in entities_with_coords
            if _is_textual_coordinate_entity(e)
        ]
        map_image_coordinates = [
            e
            for e in entities_with_coords
            if _is_map_image_entity(e)
        ]

        telemetry = pipeline.geocoder.get_last_document_stats()
        geocode_rejections = sum(
            value
            for key, value in telemetry.items()
            if key.startswith("geocode_fail_") or key.startswith("geocode_reject_")
        )
        candidate_filter_rejections = sum(
            value
            for key, value in telemetry.items()
            if key.startswith("candidate_reject_")
        )

        row = PdfMetrics(
            pdf_name=pdf_path.name,
            seconds=elapsed,
            entities_total=len(entities),
            entities_with_coordinates=len(entities_with_coords),
            loc_gpe_with_coordinates=len(loc_gpe_with_coords),
            low_signal_loc_gpe_with_coordinates=len(low_signal_loc_gpe),
            avg_conf_loc_gpe=(
                round(mean([e.confidence for e in loc_gpe_with_coords]), 3)
                if loc_gpe_with_coords
                else 0.0
            ),
            geocode_unique_candidates_total=telemetry.get("unique_candidates_total", 0),
            geocode_unique_candidates_geocoded=telemetry.get("unique_candidates_geocoded", 0),
            geocode_rejections=geocode_rejections,
            rejected_by_candidate_filters=candidate_filter_rejections,
            textual_coordinates=len(textual_coordinates),
            map_image_coordinates=len(map_image_coordinates),
            has_textual_study_site_signal=_has_textual_study_site_signal(entities),
        )
        rows.append(row)

        print(
            f"[{index:02d}/{len(pdfs):02d}] {pdf_path.name}: "
            f"{elapsed:.1f}s, loc/gpe coords={row.loc_gpe_with_coordinates}, "
            f"geocoded unique={row.geocode_unique_candidates_geocoded}/{row.geocode_unique_candidates_total}, "
            f"text-signal={'yes' if row.has_textual_study_site_signal else 'no'}"
        )

    return rows, failures


def _print_comparison_table(baseline: list[PdfMetrics], strict: list[PdfMetrics]) -> None:
    comparison_rows = _build_comparison_rows(baseline, strict)

    by_name = {row.pdf_name: row for row in baseline}
    strict_by_name = {row.pdf_name: row for row in strict}

    print("\n## Baseline vs Strict (Per PDF)")
    print(
        "| PDF | Base LOC/GPE coords | Strict LOC/GPE coords | Delta | "
        "Base geocoded unique | Strict geocoded unique | Delta |"
    )
    print("|---|---:|---:|---:|---:|---:|---:|")

    for row in comparison_rows:
        name = row["pdf_name"]
        if not isinstance(name, str):
            continue
        delta_loc = row["delta_loc_gpe_with_coordinates"]
        delta_geo = row["delta_geocoded_unique"]
        if not isinstance(delta_loc, int) or not isinstance(delta_geo, int):
            continue
        b = by_name.get(name)
        s = strict_by_name.get(name)
        if b is None or s is None:
            continue
        print(
            f"| {name} | {b.loc_gpe_with_coordinates} | {s.loc_gpe_with_coordinates} | {delta_loc:+d} | "
            f"{b.geocode_unique_candidates_geocoded}/{b.geocode_unique_candidates_total} | "
            f"{s.geocode_unique_candidates_geocoded}/{s.geocode_unique_candidates_total} | {delta_geo:+d} |"
        )


def _build_summary(rows: list[PdfMetrics]) -> dict[str, float | int]:
    total_docs = len(rows)
    total_entities = sum(r.entities_total for r in rows)
    total_with_coords = sum(r.entities_with_coordinates for r in rows)
    total_loc_gpe_coords = sum(r.loc_gpe_with_coordinates for r in rows)
    total_low_signal_loc = sum(r.low_signal_loc_gpe_with_coordinates for r in rows)
    total_unique = sum(r.geocode_unique_candidates_total for r in rows)
    total_geocoded = sum(r.geocode_unique_candidates_geocoded for r in rows)
    total_rejections = sum(r.geocode_rejections for r in rows)
    total_candidate_filter_rejections = sum(r.rejected_by_candidate_filters for r in rows)
    docs_with_text_signal = sum(1 for r in rows if r.has_textual_study_site_signal)
    total_textual_coordinates = sum(r.textual_coordinates for r in rows)
    total_map_image_coordinates = sum(r.map_image_coordinates for r in rows)
    avg_seconds = mean([r.seconds for r in rows]) if rows else 0.0

    return {
        "docs": total_docs,
        "avg_runtime_seconds": round(avg_seconds, 3),
        "entities_total": total_entities,
        "entities_with_coordinates": total_with_coords,
        "loc_gpe_with_coordinates": total_loc_gpe_coords,
        "low_signal_loc_gpe_with_coordinates": total_low_signal_loc,
        "geocoded_unique_candidates": total_geocoded,
        "geocoded_unique_candidates_total": total_unique,
        "candidate_filter_rejections": total_candidate_filter_rejections,
        "geocode_rejections": total_rejections,
        "docs_with_textual_study_site_signal": docs_with_text_signal,
        "textual_coordinates": total_textual_coordinates,
        "map_image_coordinates": total_map_image_coordinates,
    }


def _build_comparison_rows(
    baseline: list[PdfMetrics],
    strict: list[PdfMetrics],
) -> list[dict[str, str | int | float | bool | None]]:
    by_name = {row.pdf_name: row for row in baseline}
    strict_by_name = {row.pdf_name: row for row in strict}
    names = sorted(set(by_name.keys()).union(strict_by_name.keys()))

    rows: list[dict[str, str | int | float | bool | None]] = []
    for name in names:
        b = by_name.get(name)
        s = strict_by_name.get(name)

        base_loc = b.loc_gpe_with_coordinates if b else None
        strict_loc = s.loc_gpe_with_coordinates if s else None
        base_geo = b.geocode_unique_candidates_geocoded if b else None
        strict_geo = s.geocode_unique_candidates_geocoded if s else None

        rows.append(
            {
                "pdf_name": name,
                "baseline_seconds": b.seconds if b else None,
                "strict_seconds": s.seconds if s else None,
                "baseline_loc_gpe_with_coordinates": base_loc,
                "strict_loc_gpe_with_coordinates": strict_loc,
                "delta_loc_gpe_with_coordinates": (
                    strict_loc - base_loc
                    if base_loc is not None and strict_loc is not None
                    else None
                ),
                "baseline_geocoded_unique": base_geo,
                "baseline_geocoded_unique_total": (
                    b.geocode_unique_candidates_total if b else None
                ),
                "strict_geocoded_unique": strict_geo,
                "strict_geocoded_unique_total": (
                    s.geocode_unique_candidates_total if s else None
                ),
                "delta_geocoded_unique": (
                    strict_geo - base_geo
                    if base_geo is not None and strict_geo is not None
                    else None
                ),
                "baseline_has_textual_study_site_signal": (
                    b.has_textual_study_site_signal if b else None
                ),
                "strict_has_textual_study_site_signal": (
                    s.has_textual_study_site_signal if s else None
                ),
                "baseline_textual_coordinates": b.textual_coordinates if b else None,
                "strict_textual_coordinates": s.textual_coordinates if s else None,
                "baseline_map_image_coordinates": (
                    b.map_image_coordinates if b else None
                ),
                "strict_map_image_coordinates": (
                    s.map_image_coordinates if s else None
                ),
            }
        )

    return rows


def _print_summary(label: str, rows: list[PdfMetrics]) -> None:
    summary = _build_summary(rows)

    print(f"\n## Summary: {label}")
    print(f"- docs: {summary['docs']}")
    print(f"- avg runtime seconds: {summary['avg_runtime_seconds']:.1f}")
    print(f"- entities total: {summary['entities_total']}")
    print(f"- entities with coordinates: {summary['entities_with_coordinates']}")
    print(f"- LOC/GPE with coordinates: {summary['loc_gpe_with_coordinates']}")
    print(f"- low-signal LOC/GPE with coordinates: {summary['low_signal_loc_gpe_with_coordinates']}")
    print(
        "- geocoded unique candidates: "
        f"{summary['geocoded_unique_candidates']}/{summary['geocoded_unique_candidates_total']}"
    )
    print(f"- candidate filter rejections: {summary['candidate_filter_rejections']}")
    print(f"- geocode rejections (failures + guards): {summary['geocode_rejections']}")
    print(
        "- docs with textual study-site signal: "
        f"{summary['docs_with_textual_study_site_signal']}/{summary['docs']}"
    )
    print(f"- textual coordinates: {summary['textual_coordinates']}")
    print(f"- map-image coordinates: {summary['map_image_coordinates']}")


def _print_text_signal_table(rows: list[PdfMetrics]) -> None:
    if not rows:
        return
    print("\n## Baseline textual signal classification")
    print("| PDF | Textual signal | Textual coords | Map-image coords |")
    print("|---|---|---:|---:|")
    for row in sorted(rows, key=lambda r: r.pdf_name):
        signal = "yes" if row.has_textual_study_site_signal else "no"
        print(
            f"| {row.pdf_name} | {signal} | {row.textual_coordinates} | {row.map_image_coordinates} |"
        )


def _print_failures(label: str, failures: list[PdfFailure]) -> None:
    if not failures:
        return
    print(f"\n## Skipped due to parse/extraction errors: {label}")
    for failure in failures:
        print(f"- {failure.pdf_name}: {failure.error}")


def _write_json_output(
    output_path: Path,
    *,
    input_pdfs: list[Path],
    benchmark_pdfs: list[Path],
    baseline_rows_all: list[PdfMetrics],
    baseline_rows_compared: list[PdfMetrics],
    strict_rows: list[PdfMetrics],
    baseline_failures: list[PdfFailure],
    strict_failures: list[PdfFailure],
    text_only: bool,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "selection": {
            "input_pdfs": [str(pdf) for pdf in input_pdfs],
            "benchmark_pdfs": [str(pdf) for pdf in benchmark_pdfs],
            "text_only": text_only,
        },
        "baseline": {
            "summary": _build_summary(baseline_rows_compared),
            "rows": [asdict(row) for row in baseline_rows_compared],
        },
        "strict": {
            "summary": _build_summary(strict_rows),
            "rows": [asdict(row) for row in strict_rows],
        },
        "baseline_text_signal_classification": [
            {
                "pdf_name": row.pdf_name,
                "has_textual_study_site_signal": row.has_textual_study_site_signal,
                "textual_coordinates": row.textual_coordinates,
                "map_image_coordinates": row.map_image_coordinates,
            }
            for row in baseline_rows_all
        ],
        "comparison_rows": _build_comparison_rows(baseline_rows_compared, strict_rows),
        "failures": {
            "baseline": [asdict(failure) for failure in baseline_failures],
            "strict": [asdict(failure) for failure in strict_failures],
        },
    }

    output_path.write_text(f"{json.dumps(payload, indent=2, sort_keys=True)}\n", encoding="utf-8")
    print(f"\nWrote JSON output: {output_path}")


def _write_csv_output(
    output_path: Path,
    *,
    baseline_rows_compared: list[PdfMetrics],
    strict_rows: list[PdfMetrics],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    comparison_rows = _build_comparison_rows(baseline_rows_compared, strict_rows)
    fieldnames = [
        "pdf_name",
        "baseline_seconds",
        "strict_seconds",
        "baseline_loc_gpe_with_coordinates",
        "strict_loc_gpe_with_coordinates",
        "delta_loc_gpe_with_coordinates",
        "baseline_geocoded_unique",
        "baseline_geocoded_unique_total",
        "strict_geocoded_unique",
        "strict_geocoded_unique_total",
        "delta_geocoded_unique",
        "baseline_has_textual_study_site_signal",
        "strict_has_textual_study_site_signal",
        "baseline_textual_coordinates",
        "strict_textual_coordinates",
        "baseline_map_image_coordinates",
        "strict_map_image_coordinates",
    ]

    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for row in comparison_rows:
            writer.writerow(row)

    print(f"Wrote CSV output: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare baseline vs strict precision geocoding profiles.",
    )
    parser.add_argument(
        "--pdf-dir",
        default="zotero_files",
        help="Directory containing PDF files (default: zotero_files)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of PDFs to sample from --pdf-dir (default: 10)",
    )
    parser.add_argument(
        "--include",
        nargs="*",
        default=["tests/data/35J9RCQ8.pdf"],
        help="Extra PDF paths to include in comparison",
    )
    parser.add_argument(
        "--text-only",
        action="store_true",
        help=(
            "Only benchmark PDFs that show textual study-site signal "
            "(classified from baseline extraction output)."
        ),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="Optional path for machine-readable JSON output.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=None,
        help="Optional path for machine-readable CSV comparison output.",
    )
    args = parser.parse_args()

    pdf_dir = Path(args.pdf_dir)
    if not pdf_dir.exists():
        raise SystemExit(f"PDF directory not found: {pdf_dir}")

    extra_pdfs = [Path(path) for path in args.include]
    pdfs = _select_pdfs(pdf_dir, args.limit, extra_pdfs)

    if not pdfs:
        raise SystemExit("No PDFs selected")

    print(f"Selected {len(pdfs)} PDFs")
    for pdf in pdfs:
        print(f"- {pdf}")

    baseline_rows, baseline_failures = _run_profile("baseline", BASELINE_PROFILE, pdfs)
    baseline_rows_all = list(baseline_rows)
    _print_text_signal_table(baseline_rows_all)

    benchmark_pdfs = pdfs
    if args.text_only:
        baseline_by_name = {row.pdf_name: row for row in baseline_rows}
        benchmark_pdfs = [
            pdf
            for pdf in pdfs
            if baseline_by_name.get(pdf.name) and baseline_by_name[pdf.name].has_textual_study_site_signal
        ]
        selected_names = {pdf.name for pdf in benchmark_pdfs}
        baseline_rows = [row for row in baseline_rows if row.pdf_name in selected_names]

        print("\n## Text-only benchmark selection")
        print(f"- selected {len(benchmark_pdfs)} of {len(pdfs)} PDFs for strict-vs-baseline comparison")
        for pdf in benchmark_pdfs:
            print(f"- {pdf}")

        if not benchmark_pdfs:
            raise SystemExit("No PDFs with textual study-site signal in selected sample")

    strict_rows, strict_failures = _run_profile("strict", STRICT_PROFILE, benchmark_pdfs)

    _print_summary("baseline", baseline_rows)
    _print_summary("strict", strict_rows)
    _print_failures("baseline", baseline_failures)
    _print_failures("strict", strict_failures)
    _print_comparison_table(baseline_rows, strict_rows)

    if args.output_json:
        _write_json_output(
            args.output_json,
            input_pdfs=pdfs,
            benchmark_pdfs=benchmark_pdfs,
            baseline_rows_all=baseline_rows_all,
            baseline_rows_compared=baseline_rows,
            strict_rows=strict_rows,
            baseline_failures=baseline_failures,
            strict_failures=strict_failures,
            text_only=args.text_only,
        )

    if args.output_csv:
        _write_csv_output(
            args.output_csv,
            baseline_rows_compared=baseline_rows,
            strict_rows=strict_rows,
        )


if __name__ == "__main__":
    main()
