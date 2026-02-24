"""Import Marcos' curated publication and study site data into the Maress
database."""

from __future__ import annotations

import argparse
import logging
import random
import re
import string
import sys
from pathlib import Path

import geopandas as gpd
import openpyxl
from sqlmodel import select

from app import crud
from app.core.db import SessionLocal
from app.models import CreatorCreate, Item, ItemCreate, StudySiteCreate
from maress_types import CoordinateExtractionMethod, CoordinateSourceType, PaperSections

logger = logging.getLogger(__name__)


def generate_key() -> str:
    """Generate a random 8-character [A-Z0-9] key."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))  # noqa: S311


def parse_authors(authors_year: str) -> list[dict[str, str]]:
    """Parse Authors_year string like 'Araya_Lopez_et_al2018' into author
    records.

    Returns list of dicts with 'lastName' and 'creatorType' keys.
    """
    # Remove trailing year (4 digits at end)
    name_part = re.sub(r"\d{4}$", "", authors_year).strip("_")
    if not name_part:
        return []

    # Split on _et_al (remaining part is just "et al", skip it)
    has_et_al = "_et_al" in name_part
    name_part = re.split(r"_et_al", name_part)[0]

    # Split on _and_ for multiple authors
    author_parts = re.split(r"_and_", name_part)

    authors = []
    for part in author_parts:
        # Replace remaining underscores with spaces for multi-word last names
        last_name = part.replace("_", " ").strip()
        if last_name:
            authors.append({"lastName": last_name, "creatorType": "author"})

    # If there was "et al", add a placeholder
    if has_et_al:
        authors.append({"lastName": "et al.", "creatorType": "author"})

    return authors


def read_publications(path: Path) -> dict[int, dict]:
    """Read publications.xlsx and return {pub_id: {title, doi, abstract, year,
    authors_year}}."""
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active
    if ws is None:
        msg = f"No active sheet in {path}"
        raise ValueError(msg)

    # Find column indices from header row
    headers = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]
    col_map = {}
    for i, h in enumerate(headers):
        if h is not None:
            col_map[str(h).strip()] = i

    required = {"id", "Authors_year", "year", "title", "doi", "abstract"}
    missing = required - set(col_map.keys())
    if missing:
        msg = f"Missing columns in publications.xlsx: {missing}"
        raise ValueError(msg)

    publications = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        pub_id = row[col_map["id"]]
        if pub_id is None:
            continue
        pub_id = int(pub_id)

        title = row[col_map["title"]]
        doi = row[col_map["doi"]]
        abstract = row[col_map["abstract"]]
        year = row[col_map["year"]]
        authors_year = row[col_map["Authors_year"]]

        publications[pub_id] = {
            "title": str(title)[:255] if title else None,
            "doi": str(doi)[:128] if doi and str(doi).strip() else None,
            "abstract": str(abstract)[:8192] if abstract else "",
            "year": str(int(year)) if year else None,
            "authors_year": str(authors_year) if authors_year else "",
        }

    wb.close()
    return publications


def read_sites_publications(path: Path) -> dict[int, list[int]]:
    """Read sites_publications.xlsx and return {pub_id: [site_ids]}."""
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active
    if ws is None:
        msg = f"No active sheet in {path}"
        raise ValueError(msg)

    pub_to_sites: dict[int, list[int]] = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        site_id = row[0]
        pub_id = row[1]
        if site_id is None or pub_id is None:
            continue
        site_id = int(site_id)
        pub_id = int(pub_id)
        pub_to_sites.setdefault(pub_id, []).append(site_id)

    wb.close()
    return pub_to_sites


def read_sites_shapefile(path: Path) -> dict[int, tuple[float, float]]:
    """Read sites.shp and return {site_id: (latitude, longitude)}."""
    gdf = gpd.read_file(path)
    site_coords: dict[int, tuple[float, float]] = {}
    for _, row in gdf.iterrows():
        site_id = int(row["site_id"])
        # Shapefile geometry is Point(lon, lat)
        lon = row.geometry.x
        lat = row.geometry.y
        site_coords[site_id] = (lat, lon)
    return site_coords


def main() -> None:  # noqa: PLR0912, PLR0915
    """Entry point for the import-marcos-data CLI command."""
    parser = argparse.ArgumentParser(
        description="Import Marcos' curated data into the Maress database.",
    )
    parser.add_argument(
        "--email",
        required=True,
        help="Email of the user who will own the imported items.",
    )
    parser.add_argument(
        "--data-dir",
        default="../marcos-custom-data",
        help="Path to marcos-custom-data directory (default: ../marcos-custom-data).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate data without writing to the database.",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    pub_path = data_dir / "publications.xlsx"
    sites_pub_path = data_dir / "sites_publications.xlsx"
    shapefile_path = data_dir / "gis" / "sites.shp"

    for p in [pub_path, sites_pub_path, shapefile_path]:
        if not p.exists():
            print(f"ERROR: File not found: {p}")
            sys.exit(1)

    # Read all data sources
    print("Reading publications.xlsx...")
    all_pubs = read_publications(pub_path)
    print(f"  Found {len(all_pubs)} publications")

    print("Reading sites_publications.xlsx...")
    pub_to_sites = read_sites_publications(sites_pub_path)
    print(f"  Found {len(pub_to_sites)} publications with linked sites")

    print("Reading gis/sites.shp...")
    site_coords = read_sites_shapefile(shapefile_path)
    print(f"  Found {len(site_coords)} site coordinates")

    # Filter: every pub that has id AND (doi OR (title AND year)) AND linked sites
    eligible_pub_ids = set()
    skipped_ineligible = 0
    for pub_id, pub in all_pubs.items():
        has_doi = bool(pub.get("doi"))
        has_title_year = bool(pub.get("title")) and bool(pub.get("year"))
        if has_doi or has_title_year:
            eligible_pub_ids.add(pub_id)
        else:
            skipped_ineligible += 1

    # Only import publications that have linked study sites
    pub_ids_with_sites = eligible_pub_ids & set(pub_to_sites.keys())

    print(f"\nEligible publications (have DOI or title+year): {len(eligible_pub_ids)}")
    print(f"  With linked sites (will import): {len(pub_ids_with_sites)}")
    print(f"  Without linked sites (skipped):  {len(eligible_pub_ids) - len(pub_ids_with_sites)}")
    if skipped_ineligible:
        print(f"  Skipped (no DOI and no title+year): {skipped_ineligible}")

    # Check for missing site coordinates
    missing_coords = 0
    for pub_id in pub_ids_with_sites:
        for site_id in pub_to_sites[pub_id]:
            if site_id not in site_coords:
                missing_coords += 1
    if missing_coords:
        print(f"  WARNING: {missing_coords} site references lack coordinates in shapefile")

    if args.dry_run:
        print("\n--- DRY RUN: No database changes will be made ---")
        total_sites = sum(len(pub_to_sites.get(pid, [])) for pid in pub_ids_with_sites)
        print(f"  Would import {len(pub_ids_with_sites)} items (only those with sites)")
        print(f"  Would create up to {total_sites} study sites")
        # Show a sample
        if pub_ids_with_sites:
            sample_id = next(iter(pub_ids_with_sites))
            pub = all_pubs[sample_id]
            print(f"\n  Sample publication (id={sample_id}):")
            print(f"    Title: {pub['title']}")
            print(f"    DOI: {pub['doi']}")
            print(f"    Year: {pub['year']}")
            print(f"    Authors: {parse_authors(pub['authors_year'])}")
            print(f"    Sites: {pub_to_sites.get(sample_id, [])}")
        return

    # Database operations
    with SessionLocal() as session:
        # Look up user
        user = crud.get_user_by_email(session=session, email=args.email)
        if not user:
            print(f"ERROR: No user found with email '{args.email}'")
            sys.exit(1)
        print(f"\nImporting as user: {user.full_name} ({user.email})")

        items_created = 0
        items_skipped = 0
        items_replaced = 0
        sites_created = 0
        sites_skipped = 0
        errors = 0

        for pub_id in sorted(pub_ids_with_sites):
            pub = all_pubs[pub_id]

            # Idempotency: skip if existing item has manual study sites,
            # otherwise replace (delete + re-create)
            existing = None
            if pub["doi"]:
                existing = session.exec(
                    select(Item).where(
                        Item.doi == pub["doi"],
                        Item.owner_id == user.id,
                    ),
                ).first()
            elif pub["title"] and pub["year"]:
                existing = session.exec(
                    select(Item).where(
                        Item.title == pub["title"],
                        Item.date == pub["year"],
                        Item.owner_id == user.id,
                    ),
                ).first()

            if existing:
                has_manual = any(s.is_manual for s in (existing.study_sites or []))
                if has_manual:
                    items_skipped += 1
                    print(
                        f"  SKIP (has manual sites): {pub.get('doi') or pub.get('title', '')[:60]}"
                    )
                    continue
                # Replace: delete existing (cascades to study sites)
                session.delete(existing)
                session.flush()
                items_replaced += 1

            try:
                # Create the Item
                key = generate_key()
                item_data = ItemCreate.model_validate(
                    {
                        "key": key,
                        "title": pub["title"],
                        "DOI": pub["doi"],
                        "abstractNote": pub["abstract"],
                        "date": pub["year"],
                        "itemType": "journalArticle",
                    },
                )
                db_item = crud.create_item(
                    session=session,
                    item_in=item_data,
                    owner_id=user.id,
                )
                items_created += 1

                # Create Creators from authors_year
                authors = parse_authors(pub["authors_year"])
                for author in authors:
                    creator_data = CreatorCreate(
                        lastName=author["lastName"],
                        creatorType=author["creatorType"],
                    )
                    crud.create_creator(session, creator_data, item_id=db_item.id)

                # Create StudySites
                if pub_id in pub_to_sites:
                    for site_id in pub_to_sites[pub_id]:
                        if site_id not in site_coords:
                            sites_skipped += 1
                            continue

                        lat, lon = site_coords[site_id]
                        study_site_data = StudySiteCreate(
                            item_id=db_item.id,
                            latitude=lat,
                            longitude=lon,
                            is_manual=True,
                            confidence_score=1.0,
                            validation_score=1.0,
                            extraction_method=CoordinateExtractionMethod.MANUAL,
                            source_type=CoordinateSourceType.MANUAL,
                            section=PaperSections.OTHER,
                            context="Imported from marcos-custom-data",
                        )
                        crud.create_study_site(session, study_site_data)
                        sites_created += 1

                session.commit()

            except Exception as e:
                session.rollback()
                errors += 1
                print(f"  ERROR (pub_id={pub_id}): {e}")

        print("\n--- Import Summary ---")
        print(f"  Items created:  {items_created}")
        print(f"  Items replaced: {items_replaced} (existing without manual sites)")
        print(f"  Items skipped:  {items_skipped} (existing with manual sites)")
        print(f"  Sites created:  {sites_created}")
        print(f"  Sites skipped:  {sites_skipped} (missing coordinates)")
        print(f"  Errors:         {errors}")


if __name__ == "__main__":
    main()
