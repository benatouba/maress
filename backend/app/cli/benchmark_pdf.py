"""Benchmark NLP study site extraction from PDF files against user-curated DB results.

Workflow
--------
1. Collect PDF files from ``--path`` (single file or directory).
2. For each PDF, extract title and DOI from its metadata / first-page text.
3. Match the PDF to a DB item that has *manual* study sites:
   - First try an exact DOI match.
   - Fall back to fuzzy title similarity (``--threshold``, default 0.75).
4. Run NLP extraction on the PDF (no DB writes).
5. Compare extracted sites against the matched item's manual sites.
6. Print a report and optionally write markdown / CSV output.

Usage
-----
    benchmark-pdf --path /path/to/papers/
    benchmark-pdf --path /path/to/paper.pdf
    benchmark-pdf --path /path/to/papers/ --threshold 0.8 --output report.md
    benchmark-pdf --path /path/to/papers/ --no-extract   # evaluate existing DB auto-sites
"""

from __future__ import annotations

import json
import logging
import re
import sys
import uuid
from dataclasses import dataclass
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING

import pymupdf
import spacy
from sqlalchemy.orm import selectinload
from sqlmodel import select

from app.core.db import SessionLocal
from app.models import Item, StudySite
from app.nlp.adapters import StudySiteResultAdapter
from app.nlp.factories import PipelineFactory
from app.nlp.model_config import ModelConfig
from app.nlp.pdf_parser import DoclingPDFParser

# Reuse shared result types and reporting from the DOI-based benchmark script
from app.cli.benchmark_extraction import (
    SiteCoord,
    PaperResult,
    compute_distances,
    print_report,
    write_markdown_report,
    write_csv,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.nlp.orchestrator import StudySiteExtractionPipeline

_DOI_RE = re.compile(r'10\.\d{4,9}/\S+')


def _load_geocode_cache(cache_path: Path) -> int:
    """Load serialized geocoding cache entries from *cache_path*.

    Returns the number of entries imported.
    """
    from app.nlp.geocoding import get_geocoder

    if not cache_path.exists():
        return 0

    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to read geocode cache %s: %s", cache_path, exc)
        return 0

    if not isinstance(payload, dict):
        logger.warning("Ignoring geocode cache %s: expected top-level object", cache_path)
        return 0

    entries: dict[str, list[float] | tuple[float, float] | None] = {}
    for key, value in payload.items():
        if not isinstance(key, str):
            continue
        if value is None:
            entries[key] = None
            continue
        if isinstance(value, list | tuple) and len(value) == 2:
            entries[key] = value

    return get_geocoder().import_cache_entries(entries)


def _save_geocode_cache(cache_path: Path) -> int:
    """Save geocoding cache entries to *cache_path* and return entry count."""
    from app.nlp.geocoding import get_geocoder

    entries = get_geocoder().export_cache_entries()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(entries, indent=2, sort_keys=True), encoding="utf-8")
    return len(entries)


# ---------------------------------------------------------------------------
# PDF metadata extraction
# ---------------------------------------------------------------------------

def _doi_from_pymupdf(path: Path) -> str | None:
    """Extract DOI quickly via PyMuPDF metadata fields and first-page text."""
    try:
        doc = pymupdf.open(str(path))
        meta = doc.metadata or {}

        for field in ("subject", "keywords", "title"):
            field_text = str(meta.get(field) or "")
            m = _DOI_RE.search(field_text)
            if m:
                doc.close()
                return m.group(0).rstrip(".")

        if doc.page_count > 0:
            page_text = str(doc[0].get_text("text"))
            m = _DOI_RE.search(page_text)
            if m:
                doc.close()
                return m.group(0).rstrip(".")

        doc.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("PyMuPDF DOI extraction failed for %s: %s", path.name, exc)
    return None


def _title_from_pymupdf(path: Path) -> str | None:
    """Extract title as fallback using PyMuPDF metadata and first-page text."""
    try:
        doc = pymupdf.open(str(path))
        meta = doc.metadata or {}

        raw = str(meta.get("title") or "").strip()
        if 5 < len(raw) < 350:
            doc.close()
            return raw

        if doc.page_count > 0:
            page_text = str(doc[0].get_text("text"))
            for line in page_text.splitlines():
                line = line.strip()
                if 15 < len(line) < 280:
                    doc.close()
                    return line

        doc.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("PyMuPDF title extraction failed for %s: %s", path.name, exc)
    return None


def _extract_pdf_metadata(path: Path) -> tuple[str | None, str | None]:
    """Return ``(title, doi)`` by parsing the PDF with the app's standard pipeline.

    For performance, metadata extraction is two-stage:

    1. Fast pass via PyMuPDF (title + DOI from metadata and first page text)
    2. Docling fallback only when PyMuPDF cannot provide a usable title

    This avoids expensive OCR/layout parsing during the matching phase for most
    PDFs while still keeping robust fallback behavior.

    The Docling fallback parser produces a spaCy Doc whose
    ``doc.spans["layout"]`` contains typed layout spans; the first span with
    ``label_ == "title"`` is used as paper title.

    Falls back to the normalised filename stem if no title is found at all.
    """
    # --- Fast pass: PyMuPDF (no OCR/layout parse needed) ---
    doi = _doi_from_pymupdf(path)
    title: str | None = _title_from_pymupdf(path)

    # --- Fallback: Docling title extraction (only when needed) ---
    if not title:
        try:
            nlp = spacy.blank("en")
            parser = DoclingPDFParser(nlp, enable_ocr_fallback=True, enable_pymupdf_fallback=True)
            doc = parser.parse(path)

            # First "title" layout span
            for span in doc.spans.get("layout", []):
                if span.label_ == "title":
                    candidate = span.text.strip()
                    if 5 < len(candidate) < 350:
                        title = candidate
                        break

            # Also scan for DOI in parsed text if not yet found
            if not doi:
                m = _DOI_RE.search(doc.text)
                if m:
                    doi = m.group(0).rstrip(".")

        except Exception as exc:  # noqa: BLE001
            logger.warning("Docling title extraction failed for %s: %s", path.name, exc)

    # --- Absolute fallback: filename ---
    if not title:
        title = path.stem.replace("_", " ").replace("-", " ")

    return title, doi


# ---------------------------------------------------------------------------
# Title fuzzy-matching
# ---------------------------------------------------------------------------

def _normalise(text: str) -> str:
    """Lowercase, remove punctuation, collapse whitespace."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _title_similarity(a: str, b: str) -> float:
    """SequenceMatcher ratio between two normalised titles."""
    return SequenceMatcher(None, _normalise(a), _normalise(b)).ratio()


@dataclass
class MatchResult:
    """Outcome of matching a PDF to a DB item."""

    pdf_path: Path
    pdf_title: str | None
    pdf_doi: str | None
    matched_item: Item | None
    match_method: str  # "doi", "title", or "none"
    similarity: float  # 1.0 for doi match, ratio for title match


def _find_match(
    pdf_path: Path,
    candidate_items: list[Item],
    *,
    threshold: float,
) -> MatchResult:
    """Match a single PDF to the best candidate DB item.

    Tries DOI first, then fuzzy title.
    """
    pdf_title, pdf_doi = _extract_pdf_metadata(pdf_path)

    # --- exact DOI match ---
    if pdf_doi:
        doi_norm = pdf_doi.strip().lower()
        for item in candidate_items:
            if item.doi and item.doi.strip().lower() == doi_norm:
                return MatchResult(
                    pdf_path=pdf_path,
                    pdf_title=pdf_title,
                    pdf_doi=pdf_doi,
                    matched_item=item,
                    match_method="doi",
                    similarity=1.0,
                )

    # --- fuzzy title match ---
    if pdf_title:
        best_item: Item | None = None
        best_score = 0.0

        for item in candidate_items:
            if not item.title:
                continue
            score = _title_similarity(pdf_title, item.title)
            if score > best_score:
                best_score = score
                best_item = item

        if best_score >= threshold and best_item is not None:
            return MatchResult(
                pdf_path=pdf_path,
                pdf_title=pdf_title,
                pdf_doi=pdf_doi,
                matched_item=best_item,
                match_method="title",
                similarity=best_score,
            )

    return MatchResult(
        pdf_path=pdf_path,
        pdf_title=pdf_title,
        pdf_doi=pdf_doi,
        matched_item=None,
        match_method="none",
        similarity=0.0,
    )


# ---------------------------------------------------------------------------
# NLP extraction (no DB writes)
# ---------------------------------------------------------------------------

def _run_extraction(
    path: Path,
    title: str | None,
    *,
    pipeline: StudySiteExtractionPipeline,
    config: ModelConfig,
) -> tuple[list[SiteCoord], float]:
    """Run the full NLP pipeline on *path* and return extracted site coords."""
    started_at = perf_counter()

    print(f"  Extracting from: {path.name}")
    result = pipeline.extract_from_pdf(path, title=title or None)

    study_sites = StudySiteResultAdapter.to_study_sites(
        result=result,
        item_id=uuid.uuid4(),  # ephemeral id – not persisted
        min_confidence=config.MIN_CONFIDENCE,
    )

    top_sites = study_sites[: config.MAX_STUDY_SITES]
    runtime_seconds = perf_counter() - started_at
    print(f"  Found {len(top_sites)} study sites ({len(study_sites)} total candidates)")
    print(f"  Extraction runtime: {runtime_seconds:.2f}s")

    return (
        [
            SiteCoord(name=s.name, lat=float(s.latitude), lon=float(s.longitude))
            for s in top_sites
            if s.latitude is not None and s.longitude is not None
        ],
        runtime_seconds,
    )


def _get_manual_site_coords(session, item: Item) -> list[SiteCoord]:  # noqa: ANN001
    """Fetch manual study site coordinates for *item* from the DB."""
    query = (
        select(StudySite)
        .options(selectinload(StudySite.location))  # pyright: ignore[reportArgumentType]
        .where(StudySite.item_id == item.id)
        .where(StudySite.is_manual.is_(True))  # noqa: FBT003  # pyright: ignore[reportAttributeAccessIssue]
    )
    sites = session.exec(query).all()
    return [
        SiteCoord(name=s.name, lat=float(s.location.latitude), lon=float(s.location.longitude))
        for s in sites
        if s.location
    ]


def _get_auto_site_coords(session, item: Item) -> list[SiteCoord]:  # noqa: ANN001
    """Fetch auto-extracted study site coordinates for *item* from the DB."""
    query = (
        select(StudySite)
        .options(selectinload(StudySite.location))  # pyright: ignore[reportArgumentType]
        .where(StudySite.item_id == item.id)
        .where(StudySite.is_manual.is_(False))  # noqa: FBT003  # pyright: ignore[reportAttributeAccessIssue]
    )
    sites = session.exec(query).all()
    return [
        SiteCoord(name=s.name, lat=float(s.location.latitude), lon=float(s.location.longitude))
        for s in sites
        if s.location
    ]


# ---------------------------------------------------------------------------
# Collect PDFs
# ---------------------------------------------------------------------------

def _collect_pdfs(path: Path) -> list[Path]:
    """Return PDF paths from *path* (file) or all PDFs under *path* (dir)."""
    if path.is_file():
        if path.suffix.lower() != ".pdf":
            print(f"WARNING: {path.name} is not a PDF, skipping")
            return []
        return [path]

    if path.is_dir():
        pdfs = sorted(path.rglob("*.pdf"))
        if not pdfs:
            print(f"No PDF files found under {path}")
        return pdfs

    print(f"ERROR: path does not exist: {path}")
    return []


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:  # noqa: C901
    """Entry point for the ``benchmark-pdf`` CLI command."""
    import argparse

    from app.core.logging import setup_logging
    setup_logging()

    parser = argparse.ArgumentParser(
        description=(
            "Benchmark NLP extraction from PDF files against "
            "user-curated study sites in the database."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--path",
        required=True,
        type=Path,
        metavar="PATH",
        help="Path to a single PDF file or a directory of PDF files.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.75,
        metavar="FLOAT",
        help="Minimum title-similarity score for a fuzzy match (default: 0.75).",
    )
    parser.add_argument(
        "--no-extract",
        action="store_true",
        help=(
            "Skip running extraction; evaluate auto-extracted sites already "
            "present in the DB for the matched item."
        ),
    )
    parser.add_argument(
        "--output",
        default=None,
        metavar="FILE",
        help=(
            "Write output to this file.  Use .csv for CSV; anything else "
            "is treated as markdown.  Default: benchmark_pdf_YYYY-MM-DD.md"
        ),
    )
    parser.add_argument(
        "--show-unmatched",
        action="store_true",
        help="Print a list of PDFs that could not be matched to any DB item.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Process at most N PDFs after collection. Useful for fast "
            "model-comparison smoke tests."
        ),
    )
    parser.add_argument(
        "--spacy-model",
        default=None,
        metavar="MODEL",
        help=(
            "Override NLP spaCy model for extraction, e.g. "
            "en_core_web_sm, en_core_web_lg, en_core_web_trf."
        ),
    )
    parser.add_argument(
        "--geocode-cache-file",
        default=None,
        type=Path,
        metavar="FILE",
        help=(
            "Path to geocoding cache JSON. When provided, cache entries are "
            "loaded before extraction and saved after extraction."
        ),
    )
    parser.add_argument(
        "--offline-geocoding",
        action="store_true",
        help=(
            "Disable live geocoding requests and use only cached geocoding "
            "entries (deterministic benchmark mode)."
        ),
    )
    parser.add_argument(
        "--read-only-geocode-cache",
        action="store_true",
        help=(
            "Do not write back geocoding cache when --geocode-cache-file is set. "
            "Useful for deterministic benchmark comparisons."
        ),
    )
    parser.add_argument(
        "--vision-extraction",
        action="store_true",
        help=(
            "Enable local OCR-based map/image coordinate extraction "
            "(uses Tesseract HOCR, CPU-only)."
        ),
    )

    args = parser.parse_args()

    # --- resolve output paths ---
    default_md = f"benchmark_pdf_{date.today().isoformat()}.md"
    md_output = args.output if args.output and not args.output.endswith(".csv") else default_md
    csv_output: str | None = args.output if args.output and args.output.endswith(".csv") else None

    # --- collect PDFs ---
    pdfs = _collect_pdfs(args.path)
    if not pdfs:
        sys.exit(1)

    if args.limit is not None:
        if args.limit <= 0:
            print(f"ERROR: --limit must be positive (got {args.limit})")
            sys.exit(2)
        pdfs = pdfs[: args.limit]

    print(f"Found {len(pdfs)} PDF file(s) under {args.path}")

    from app.nlp.geocoding import get_geocoder

    geocoder = get_geocoder()

    if args.geocode_cache_file is not None:
        imported_cache_entries = _load_geocode_cache(args.geocode_cache_file)
        print(
            f"Loaded {imported_cache_entries} geocoding cache entr"
            f"{'y' if imported_cache_entries == 1 else 'ies'} from {args.geocode_cache_file}"
        )

    if args.offline_geocoding:
        geocoder.set_live_requests_enabled(False)
        print("Geocoding mode: offline (cache-only)")
    else:
        geocoder.set_live_requests_enabled(True)
        print("Geocoding mode: live")

    config = ModelConfig()
    if args.spacy_model:
        config = config.model_copy(update={"SPACY_MODEL": args.spacy_model})

    pipeline: StudySiteExtractionPipeline | None = None
    if not args.no_extract:
        pipeline = PipelineFactory.create_pipeline_for_api(
            config=config,
            enable_vision_extraction=args.vision_extraction,
        )

    with SessionLocal() as session:
        # Load all DB items that have at least one manual study site
        print("\nLoading items with manual study sites from database…")
        candidate_items: list[Item] = list(session.exec(
            select(Item)
            .join(StudySite, StudySite.item_id == Item.id)  # pyright: ignore[reportArgumentType]
            .where(StudySite.is_manual.is_(True))  # noqa: FBT003  # pyright: ignore[reportAttributeAccessIssue]
            .distinct()
        ).all())

        if not candidate_items:
            print("No items with manual study sites found in the database.")
            print("Import manually curated data first (e.g. import-marcos-data).")
            sys.exit(0)

        print(f"Found {len(candidate_items)} candidate DB item(s) with manual sites.")

        # --- match PDFs to DB items ---
        print("\nMatching PDFs to database items…")
        matches: list[MatchResult] = []
        for pdf in pdfs:
            mr = _find_match(pdf, candidate_items, threshold=args.threshold)
            matches.append(mr)
            if mr.matched_item:
                print(
                    f"  ✓ {pdf.name!r:50s} → {(mr.matched_item.title or '')[:50]!r}"
                    f"  [{mr.match_method}, score={mr.similarity:.2f}]"
                )
            else:
                print(
                    f"  ✗ {pdf.name!r:50s}  no match  "
                    f"(best title: {mr.pdf_title!r:.50})"
                )

        matched = [m for m in matches if m.matched_item is not None]
        unmatched = [m for m in matches if m.matched_item is None]

        print(f"\n{len(matched)} matched, {len(unmatched)} unmatched")

        if unmatched and args.show_unmatched:
            print("\nUnmatched PDFs:")
            for m in unmatched:
                print(f"  {m.pdf_path.name}  (title: {m.pdf_title!r})")

        if not matched:
            print(
                "\nNo PDFs could be matched.  Try lowering --threshold "
                f"(current: {args.threshold}) or check that the PDF titles "
                "align with titles in the database."
            )
            sys.exit(0)

        # --- run extraction / fetch sites, compute metrics ---
        results: list[PaperResult] = []

        for i, mr in enumerate(matched, start=1):
            item = mr.matched_item
            assert item is not None  # narrowing

            print(f"\n[{i}/{len(matched)}] {mr.pdf_path.name}")
            print(f"  DB item:  {item.title}")
            print(f"  Match:    {mr.match_method}  (score={mr.similarity:.2f})")

            # --- get auto-extracted sites ---
            runtime_seconds: float | None = None
            if args.no_extract:
                auto_sites = _get_auto_site_coords(session, item)
                if not auto_sites:
                    print("  No auto-extracted sites in DB; skipping (run without --no-extract).")
                    continue
                print(f"  Using {len(auto_sites)} existing auto-extracted site(s) from DB")
            else:
                try:
                    if pipeline is None:
                        msg = "Extraction pipeline is not initialised"
                        raise RuntimeError(msg)
                    auto_sites, runtime_seconds = _run_extraction(
                        mr.pdf_path,
                        title=mr.pdf_title,
                        pipeline=pipeline,
                        config=config,
                    )
                except Exception as exc:
                    print(f"  ERROR during extraction: {exc}")
                    logger.exception("Extraction failed for %s", mr.pdf_path)
                    continue

            # --- get manual (ground-truth) sites ---
            manual_sites = _get_manual_site_coords(session, item)
            if not manual_sites:
                print("  WARNING: no manual sites with coordinates found for matched item")
                continue

            print(f"  Manual sites: {len(manual_sites)},  auto sites: {len(auto_sites)}")

            # --- compute distance metrics ---
            paper_result = compute_distances(manual_sites, auto_sites)
            paper_result.doi = item.doi or ""
            paper_result.title = item.title
            paper_result.manual_item_id = str(item.id)
            paper_result.zotero_item_id = str(item.id)
            paper_result.runtime_seconds = runtime_seconds
            results.append(paper_result)

            print(
                f"  Exact: {paper_result.exact_matches}  "
                f"<1km: {paper_result.close_1km}  "
                f"<5km: {paper_result.close_5km}  "
                f"mean dist: "
                + (f"{paper_result.mean_min_distance:.1f} km" if paper_result.mean_min_distance != float("inf") else "N/A")
            )

    # --- output ---
    print_report(results)
    write_markdown_report(results, md_output)
    if csv_output:
        write_csv(results, csv_output)

    if args.geocode_cache_file is not None and not args.read_only_geocode_cache:
        exported = _save_geocode_cache(args.geocode_cache_file)
        print(
            f"Saved {exported} geocoding cache entr"
            f"{'y' if exported == 1 else 'ies'} to {args.geocode_cache_file}"
        )
    elif args.geocode_cache_file is not None and args.read_only_geocode_cache:
        print(f"Skipped saving geocoding cache (read-only): {args.geocode_cache_file}")
