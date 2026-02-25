"""Benchmark NLP study site extraction against Marcos' manual ground-truth data."""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from geopy.distance import geodesic
from sqlalchemy.orm import selectinload
from sqlmodel import select

from app import crud
from app.core.db import SessionLocal
from app.models import Item, StudySite
from app.nlp.adapters import StudySiteResultAdapter
from app.nlp.factories import PipelineFactory
from app.nlp.model_config import ModelConfig


@dataclass
class SiteCoord:
    """A study site with its coordinates."""

    name: str | None
    lat: float
    lon: float


@dataclass
class PaperResult:
    """Benchmark result for a single paper."""

    doi: str
    title: str | None
    manual_item_id: str
    zotero_item_id: str
    manual_count: int
    auto_count: int
    exact_matches: int  # <0.1 km
    close_1km: int  # <1 km
    close_5km: int  # <5 km
    close_10km: int  # <10 km
    min_distances: list[float] = field(default_factory=list)  # km, one per manual site

    @property
    def mean_min_distance(self) -> float:
        """Mean of minimum distances from each manual site to nearest auto site."""
        if not self.min_distances:
            return float("inf")
        return sum(self.min_distances) / len(self.min_distances)

    @property
    def median_min_distance(self) -> float:
        """Median of minimum distances."""
        if not self.min_distances:
            return float("inf")
        s = sorted(self.min_distances)
        n = len(s)
        if n % 2 == 1:
            return s[n // 2]
        return (s[n // 2 - 1] + s[n // 2]) / 2


def find_matched_papers(
    session,  # noqa: ANN001
) -> list[tuple[Item, Item]]:
    """Find papers that exist as both manual (Marcos) and Zotero (with PDF) items.

    Returns list of (manual_item, zotero_item) pairs matched by DOI.
    """
    # Get all items with manual study sites
    manual_items_query = (
        select(Item)
        .join(StudySite, StudySite.item_id == Item.id)
        .where(StudySite.is_manual.is_(True))  # noqa: FBT003
        .distinct()
    )
    manual_items = session.exec(manual_items_query).all()

    # Build DOI → manual_item map (skip items without DOI)
    doi_to_manual: dict[str, Item] = {}
    for item in manual_items:
        if item.doi:
            doi_to_manual[item.doi.strip().lower()] = item

    if not doi_to_manual:
        return []

    # Find Zotero items with the same DOIs that have a PDF attachment
    matched = []
    for doi, manual_item in doi_to_manual.items():
        zotero_items = session.exec(
            select(Item).where(
                Item.doi.isnot(None),
                Item.attachment.isnot(None),
                Item.id != manual_item.id,
            )
        ).all()

        for z_item in zotero_items:
            if z_item.doi and z_item.doi.strip().lower() == doi:
                matched.append((manual_item, z_item))
                break  # one match per DOI

    return matched


def get_site_coords(session, item: Item, *, manual_only: bool = False) -> list[SiteCoord]:  # noqa: ANN001
    """Get coordinates for an item's study sites."""
    query = (
        select(StudySite)
        .options(selectinload(StudySite.location))
        .where(StudySite.item_id == item.id)
    )
    if manual_only:
        query = query.where(StudySite.is_manual.is_(True))  # noqa: FBT003
    else:
        query = query.where(StudySite.is_manual.is_(False))  # noqa: FBT003

    sites = session.exec(query).all()
    coords = []
    for site in sites:
        if site.location:
            coords.append(SiteCoord(
                name=site.name,
                lat=float(site.location.latitude),
                lon=float(site.location.longitude),
            ))
    return coords


def compute_distances(manual_sites: list[SiteCoord], auto_sites: list[SiteCoord]) -> PaperResult:
    """Compare manual vs auto sites and compute distance metrics.

    Returns a partially filled PaperResult (caller sets DOI/title/IDs).
    """
    exact = 0
    close_1 = 0
    close_5 = 0
    close_10 = 0
    min_dists: list[float] = []

    for m_site in manual_sites:
        if not auto_sites:
            min_dists.append(float("inf"))
            continue

        best_dist = float("inf")
        for a_site in auto_sites:
            dist = geodesic((m_site.lat, m_site.lon), (a_site.lat, a_site.lon)).km
            if dist < best_dist:
                best_dist = dist

        min_dists.append(best_dist)
        if best_dist < 0.1:
            exact += 1
        if best_dist < 1.0:
            close_1 += 1
        if best_dist < 5.0:
            close_5 += 1
        if best_dist < 10.0:
            close_10 += 1

    return PaperResult(
        doi="",
        title=None,
        manual_item_id="",
        zotero_item_id="",
        manual_count=len(manual_sites),
        auto_count=len(auto_sites),
        exact_matches=exact,
        close_1km=close_1,
        close_5km=close_5,
        close_10km=close_10,
        min_distances=min_dists,
    )


def run_extraction(item: Item) -> list[SiteCoord]:
    """Run NLP extraction on an item in-memory (no DB writes).

    Returns list of SiteCoord from the extraction pipeline.
    """
    if not item.attachment:
        print(f"  WARNING: Item {item.id} has no attachment, skipping extraction")
        return []

    path = Path(item.attachment).resolve(strict=True)

    config = ModelConfig()
    pipeline = PipelineFactory.create_pipeline_for_api(config=config)

    print(f"  Extracting from: {path.name}")
    result = pipeline.extract_from_pdf(path, title=item.title or None)

    study_sites = StudySiteResultAdapter.to_study_sites(
        result=result,
        item_id=item.id,
        min_confidence=config.MIN_CONFIDENCE,
    )

    if not study_sites:
        print(f"  No study sites found for item {item.id}")
        return []

    top_sites = study_sites[: config.MAX_STUDY_SITES]
    print(f"  Found {len(top_sites)} study sites ({len(study_sites)} total candidates)")

    return [
        SiteCoord(name=site.name, lat=float(site.latitude), lon=float(site.longitude))
        for site in top_sites
        if site.latitude is not None and site.longitude is not None
    ]


def print_report(results: list[PaperResult]) -> None:
    """Print benchmark report to stdout."""
    if not results:
        print("\nNo results to report.")
        return

    print("\n" + "=" * 90)
    print("BENCHMARK REPORT: NLP Extraction vs Manual Ground Truth")
    print("=" * 90)

    # Per-paper summary
    print(f"\n{'DOI':<40} {'Manual':>6} {'Auto':>6} {'Exact':>6} {'<1km':>6} {'<5km':>6} {'Mean km':>8}")
    print("-" * 90)

    for r in results:
        doi_short = (r.doi[:37] + "...") if len(r.doi) > 40 else r.doi
        mean_d = f"{r.mean_min_distance:.1f}" if r.mean_min_distance != float("inf") else "N/A"
        print(
            f"{doi_short:<40} {r.manual_count:>6} {r.auto_count:>6} "
            f"{r.exact_matches:>6} {r.close_1km:>6} {r.close_5km:>6} {mean_d:>8}"
        )

    # Aggregate statistics
    total_papers = len(results)
    total_manual = sum(r.manual_count for r in results)
    total_auto = sum(r.auto_count for r in results)
    total_exact = sum(r.exact_matches for r in results)
    total_close_1 = sum(r.close_1km for r in results)
    total_close_5 = sum(r.close_5km for r in results)
    total_close_10 = sum(r.close_10km for r in results)

    all_dists = [d for r in results for d in r.min_distances if d != float("inf")]

    print("\n" + "=" * 90)
    print("AGGREGATE STATISTICS")
    print("=" * 90)
    print(f"  Papers evaluated:      {total_papers}")
    print(f"  Total manual sites:    {total_manual}")
    print(f"  Total auto sites:      {total_auto}")
    print(f"  Count delta:           {total_auto - total_manual:+d} ({'over' if total_auto > total_manual else 'under'}-detection)")

    if total_manual > 0:
        print(f"\n  Recall @ <0.1 km:      {total_exact}/{total_manual} ({100 * total_exact / total_manual:.1f}%)")
        print(f"  Recall @ <1 km:        {total_close_1}/{total_manual} ({100 * total_close_1 / total_manual:.1f}%)")
        print(f"  Recall @ <5 km:        {total_close_5}/{total_manual} ({100 * total_close_5 / total_manual:.1f}%)")
        print(f"  Recall @ <10 km:       {total_close_10}/{total_manual} ({100 * total_close_10 / total_manual:.1f}%)")

    if all_dists:
        sorted_dists = sorted(all_dists)
        n = len(sorted_dists)
        mean_d = sum(sorted_dists) / n
        median_d = sorted_dists[n // 2] if n % 2 == 1 else (sorted_dists[n // 2 - 1] + sorted_dists[n // 2]) / 2
        print(f"\n  Mean min distance:     {mean_d:.2f} km")
        print(f"  Median min distance:   {median_d:.2f} km")
        print(f"  Min distance:          {sorted_dists[0]:.2f} km")
        print(f"  Max distance:          {sorted_dists[-1]:.2f} km")

    # Over/under detection
    over = sum(1 for r in results if r.auto_count > r.manual_count)
    under = sum(1 for r in results if r.auto_count < r.manual_count)
    equal = sum(1 for r in results if r.auto_count == r.manual_count)
    print(f"\n  Over-detection:        {over} papers")
    print(f"  Under-detection:       {under} papers")
    print(f"  Equal count:           {equal} papers")


def write_markdown_report(
    results: list[PaperResult],
    output_path: str,
    *,
    doi_filter: list[str] | None = None,
) -> None:
    """Write benchmark results as a markdown report."""
    lines: list[str] = []

    # Header
    lines.append("# Benchmark Report: NLP Extraction vs Manual Ground Truth")
    lines.append("")
    lines.append(f"**Date:** {date.today().isoformat()}")
    lines.append(f"**Papers evaluated:** {len(results)}")
    if doi_filter:
        lines.append(f"**DOI filter:** {', '.join(doi_filter)}")
    lines.append("")

    if not results:
        lines.append("No results to report.")
        Path(output_path).write_text("\n".join(lines))
        print(f"\nMarkdown report written to: {output_path}")
        return

    # Per-paper table
    lines.append("## Per-Paper Results")
    lines.append("")
    lines.append("| DOI | Title | Manual | Auto | Exact | <1km | <5km | <10km | Mean dist (km) |")
    lines.append("|-----|-------|-------:|-----:|------:|-----:|-----:|------:|---------------:|")

    for r in results:
        doi_short = (r.doi[:35] + "...") if len(r.doi) > 38 else r.doi
        title_short = ((r.title[:40] + "...") if len(r.title) > 43 else r.title) if r.title else ""
        mean_d = f"{r.mean_min_distance:.1f}" if r.mean_min_distance != float("inf") else "N/A"
        lines.append(
            f"| {doi_short} | {title_short} | {r.manual_count} | {r.auto_count} "
            f"| {r.exact_matches} | {r.close_1km} | {r.close_5km} | {r.close_10km} | {mean_d} |"
        )

    lines.append("")

    # Aggregate statistics
    total_manual = sum(r.manual_count for r in results)
    total_auto = sum(r.auto_count for r in results)
    total_exact = sum(r.exact_matches for r in results)
    total_close_1 = sum(r.close_1km for r in results)
    total_close_5 = sum(r.close_5km for r in results)
    total_close_10 = sum(r.close_10km for r in results)

    all_dists = [d for r in results for d in r.min_distances if d != float("inf")]

    lines.append("## Aggregate Statistics")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|------:|")
    lines.append(f"| Papers evaluated | {len(results)} |")
    lines.append(f"| Total manual sites | {total_manual} |")
    lines.append(f"| Total auto sites | {total_auto} |")
    delta = total_auto - total_manual
    lines.append(f"| Count delta | {delta:+d} ({'over' if delta > 0 else 'under'}-detection) |")

    if total_manual > 0:
        lines.append(f"| Recall @ <0.1 km | {total_exact}/{total_manual} ({100 * total_exact / total_manual:.1f}%) |")
        lines.append(f"| Recall @ <1 km | {total_close_1}/{total_manual} ({100 * total_close_1 / total_manual:.1f}%) |")
        lines.append(f"| Recall @ <5 km | {total_close_5}/{total_manual} ({100 * total_close_5 / total_manual:.1f}%) |")
        lines.append(f"| Recall @ <10 km | {total_close_10}/{total_manual} ({100 * total_close_10 / total_manual:.1f}%) |")

    if all_dists:
        sorted_dists = sorted(all_dists)
        n = len(sorted_dists)
        mean_d = sum(sorted_dists) / n
        median_d = sorted_dists[n // 2] if n % 2 == 1 else (sorted_dists[n // 2 - 1] + sorted_dists[n // 2]) / 2
        lines.append(f"| Mean min distance | {mean_d:.2f} km |")
        lines.append(f"| Median min distance | {median_d:.2f} km |")
        lines.append(f"| Min distance | {sorted_dists[0]:.2f} km |")
        lines.append(f"| Max distance | {sorted_dists[-1]:.2f} km |")

    lines.append("")

    # Detection balance
    over = sum(1 for r in results if r.auto_count > r.manual_count)
    under = sum(1 for r in results if r.auto_count < r.manual_count)
    equal = sum(1 for r in results if r.auto_count == r.manual_count)

    lines.append("## Detection Balance")
    lines.append("")
    lines.append("| Category | Count |")
    lines.append("|----------|------:|")
    lines.append(f"| Over-detection | {over} papers |")
    lines.append(f"| Under-detection | {under} papers |")
    lines.append(f"| Equal count | {equal} papers |")
    lines.append("")

    Path(output_path).write_text("\n".join(lines))
    print(f"\nMarkdown report written to: {output_path}")


def write_csv(results: list[PaperResult], output_path: str) -> None:
    """Write per-paper results to CSV."""
    with open(output_path, "w", newline="") as f:  # noqa: PTH123
        writer = csv.writer(f)
        writer.writerow([
            "doi",
            "title",
            "manual_item_id",
            "zotero_item_id",
            "manual_count",
            "auto_count",
            "exact_matches",
            "close_1km",
            "close_5km",
            "close_10km",
            "mean_min_distance_km",
            "median_min_distance_km",
        ])
        for r in results:
            mean_d = r.mean_min_distance if r.mean_min_distance != float("inf") else ""
            median_d = r.median_min_distance if r.median_min_distance != float("inf") else ""
            writer.writerow([
                r.doi,
                r.title or "",
                r.manual_item_id,
                r.zotero_item_id,
                r.manual_count,
                r.auto_count,
                r.exact_matches,
                r.close_1km,
                r.close_5km,
                r.close_10km,
                mean_d,
                median_d,
            ])
    print(f"\nCSV written to: {output_path}")


def main() -> None:
    """Entry point for the benchmark-extraction CLI command."""
    parser = argparse.ArgumentParser(
        description="Benchmark NLP extraction against manual ground-truth study sites.",
    )
    parser.add_argument(
        "--email",
        required=True,
        help="Email of the user who owns the items.",
    )
    parser.add_argument(
        "--no-extract",
        action="store_true",
        help="Skip extraction; only evaluate items that already have auto-extracted sites.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-run extraction even if auto sites already exist in DB.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to write output file (CSV or markdown). Default: benchmark_report_YYYY-MM-DD.md",
    )
    parser.add_argument(
        "--doi",
        nargs="+",
        metavar="DOI",
        help="Only benchmark specific papers (one or more DOIs).",
    )
    args = parser.parse_args()

    # Determine output paths
    default_md_path = f"benchmark_report_{date.today().isoformat()}.md"
    md_output = default_md_path
    csv_output: str | None = None

    if args.output:
        if args.output.endswith(".csv"):
            csv_output = args.output
            # Also write markdown to default path
        else:
            md_output = args.output

    with SessionLocal() as session:
        # Look up user
        user = crud.get_user_by_email(session=session, email=args.email)
        if not user:
            print(f"ERROR: No user found with email '{args.email}'")
            sys.exit(1)
        print(f"User: {user.full_name} ({user.email})")

        # Find matched papers
        print("\nFinding papers with both manual sites and PDF attachments...")
        matched = find_matched_papers(session)
        print(f"Found {len(matched)} matched paper pairs")

        if not matched:
            print("No matched papers found. Ensure Marcos data is imported and Zotero items share DOIs.")
            sys.exit(0)

        # Filter by DOI if requested
        if args.doi:
            requested_dois = {d.strip().lower() for d in args.doi}
            matched_dois = {(m.doi or "").strip().lower() for m, _ in matched}
            missing = requested_dois - matched_dois
            for d in missing:
                print(f"  WARNING: Requested DOI not found in matched set: {d}")

            matched = [
                (m, z)
                for m, z in matched
                if (m.doi or "").strip().lower() in requested_dois
            ]
            print(f"Filtered to {len(matched)} papers matching requested DOIs")

            if not matched:
                print("No papers match the requested DOIs.")
                sys.exit(0)

        # Process each matched pair
        results: list[PaperResult] = []

        for i, (manual_item, zotero_item) in enumerate(matched, start=1):
            doi = manual_item.doi or ""
            title = manual_item.title or zotero_item.title
            print(f"\n[{i}/{len(matched)}] DOI: {doi}")
            print(f"  Title: {title}")

            # Get existing auto sites from DB
            existing_auto_sites = get_site_coords(session, zotero_item, manual_only=False)

            if args.no_extract:
                # Use only existing DB auto-sites
                auto_sites = existing_auto_sites
            elif args.force or not existing_auto_sites:
                # Run extraction in-memory (no DB writes)
                print("  Running NLP extraction...")
                try:
                    auto_sites = run_extraction(zotero_item)
                except Exception as e:
                    print(f"  ERROR during extraction: {e}")
                    continue
            else:
                # Auto sites exist and no --force, use DB sites
                auto_sites = existing_auto_sites

            manual_sites = get_site_coords(session, manual_item, manual_only=True)

            if not manual_sites:
                print("  WARNING: No manual sites with coordinates found")
                continue

            if not auto_sites:
                print(f"  No auto-extracted sites (manual: {len(manual_sites)})")
                if args.no_extract:
                    print("  Use without --no-extract to run extraction")

            # Compute distances
            paper_result = compute_distances(manual_sites, auto_sites)
            paper_result.doi = doi
            paper_result.title = title
            paper_result.manual_item_id = str(manual_item.id)
            paper_result.zotero_item_id = str(zotero_item.id)
            results.append(paper_result)

            print(
                f"  Manual: {paper_result.manual_count}, Auto: {paper_result.auto_count}, "
                f"Exact: {paper_result.exact_matches}, <1km: {paper_result.close_1km}"
            )

        # Print report to stdout
        print_report(results)

        # Write markdown report (always)
        write_markdown_report(results, md_output, doi_filter=args.doi)

        # Write CSV if requested
        if csv_output:
            write_csv(results, csv_output)


if __name__ == "__main__":
    main()
