"""Enrich Marcos-imported items with Zotero metadata by matching on DOI."""

from __future__ import annotations

import argparse
import sys

from pyzotero import zotero as pyzotero
from sqlmodel import select

from app import crud
from app.core.config import settings
from app.core.db import SessionLocal
from app.models import Creator, Item
from app.services import Zotero


def prompt_for_collection(zot: Zotero) -> str | None:
    """Fetch available Zotero collections and let the user pick one.

    Returns:
        The selected collection key, or None to fetch all items.
    """
    print("\nFetching collections from Zotero...")
    try:
        collections = zot.collections()  # pyright: ignore[reportUnknownMemberType]
    except Exception as exc:  # noqa: BLE001
        print(f"Could not fetch collections ({exc}). Will fetch all items.")
        return None
    if not collections:
        print("No collections found — will fetch all items.")
        return None

    print("\nAvailable collections:")
    print(f"  [0] (all items — no collection filter)")
    for i, col in enumerate(collections, start=1):
        data = col.get("data", {})
        name = data.get("name", "(unnamed)")
        num_items = col.get("meta", {}).get("numItems", "?")
        print(f"  [{i}] {name} ({num_items} items)")

    while True:
        choice = input("\nSelect a collection [0]: ").strip()
        if not choice:
            return None
        try:
            idx = int(choice)
        except ValueError:
            print("Please enter a number.")
            continue
        if idx == 0:
            return None
        if 1 <= idx <= len(collections):
            selected = collections[idx - 1]
            key = selected.get("data", {}).get("key", selected.get("key"))
            name = selected.get("data", {}).get("name", "(unnamed)")
            print(f"Selected: {name} ({key})")
            return key
        print(f"Please enter a number between 0 and {len(collections)}.")


def fetch_zotero_items(
    zot: Zotero,
    collection_id: str | None = None,
) -> list[dict]:
    """Fetch all Zotero items using paginated batches of 100.

    Args:
        zot: Authenticated Zotero client.
        collection_id: Optional collection to restrict to.

    Returns:
        List of Zotero item data dicts (parentItems excluded).
    """
    items: list[dict] = []
    start = 0
    while True:
        if collection_id:
            batch = zot.collection_items(collection_id, start=start)  # pyright: ignore[reportUnknownMemberType]
        else:
            batch = zot.items(start=start, limit=100)  # pyright: ignore[reportUnknownMemberType]
        if not batch:
            break
        items.extend(batch)
        if len(batch) < 100:
            break
        start += 100

    # Return only top-level items (skip child/attachment items)
    return [
        item["data"]
        for item in items
        if item.get("data", {}).get("parentItem") is None
    ]


def build_doi_map(zot_items: list[dict]) -> dict[str, dict]:
    """Build a mapping of lowercase DOI -> Zotero item data."""
    doi_map: dict[str, dict] = {}
    for item_data in zot_items:
        doi = item_data.get("DOI") or ""
        if doi:
            doi_map[doi.strip().lower()] = item_data
    return doi_map


def zotero_has_richer_creators(zot_creators: list[dict], local_creators: list[Creator]) -> bool:
    """Check if Zotero creator data is richer than local.

    Zotero data is considered richer if it has firstName+lastName pairs
    while local data lacks firstNames.
    """
    if not zot_creators:
        return False
    if not local_creators:
        return bool(zot_creators)
    # Richer if Zotero has firstName on any creator but local doesn't
    zot_has_first = any(c.get("firstName") for c in zot_creators)
    local_has_first = any(c.firstName for c in local_creators)
    return zot_has_first and not local_has_first


def enrich_item(item: Item, zot_data: dict, *, dry_run: bool = False) -> list[str]:
    """Update a local item with Zotero metadata.

    Returns a list of field names that were (or would be) updated.
    """
    changes: list[str] = []

    # key is ALWAYS updated
    zot_key = zot_data.get("key", "")
    if zot_key and item.key != zot_key:
        changes.append(f"key: {item.key} -> {zot_key}")
        if not dry_run:
            item.key = zot_key

    # Fields that overwrite only when local is None
    none_fields = {
        "volume": "volume",
        "issue": "issue",
        "pages": "pages",
        "language": "language",
        "journalAbbreviation": "journalAbbreviation",
        "issn": "ISSN",
        "rights": "rights",
    }
    for local_attr, zot_field in none_fields.items():
        local_val = getattr(item, local_attr)
        zot_val = zot_data.get(zot_field)
        if local_val is None and zot_val:
            changes.append(f"{local_attr}: None -> {zot_val!r}")
            if not dry_run:
                setattr(item, local_attr, zot_val)

    # Fields that overwrite only when local is empty string or None
    empty_fields = {
        "title": "title",
        "abstractNote": "abstractNote",
        "publicationTitle": "publicationTitle",
        "url": "url",
        "shortTitle": "shortTitle",
        "extra": "extra",
    }
    for local_attr, zot_field in empty_fields.items():
        local_val = getattr(item, local_attr)
        zot_val = zot_data.get(zot_field)
        if not local_val and zot_val:
            short_val = zot_val[:60] + "..." if len(str(zot_val)) > 60 else zot_val
            changes.append(f"{local_attr}: {local_val!r} -> {short_val!r}")
            if not dry_run:
                setattr(item, local_attr, zot_val)

    return changes


def main() -> None:
    """Entry point for the enrich-from-zotero CLI command."""
    parser = argparse.ArgumentParser(
        description="Enrich Marcos-imported items with Zotero metadata (matched by DOI).",
    )
    parser.add_argument(
        "--email",
        required=True,
        help="Email of the user who owns the local items.",
    )
    parser.add_argument(
        "--library-type",
        choices=["user", "group"],
        default=None,
        help=f"Zotero library type (default: {settings.ZOTERO_LIBRARY_TYPE}).",
    )
    parser.add_argument(
        "--zotero-id",
        default=None,
        help="Zotero user/group library ID (overrides the value stored on the user).",
    )
    parser.add_argument(
        "--zotero-api-key",
        default=None,
        help="Zotero API key (overrides the value stored on the user).",
    )
    parser.add_argument(
        "--collection-id",
        default=None,
        help="Only fetch items from a specific Zotero collection.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without writing to DB.",
    )
    args = parser.parse_args()

    library_type = args.library_type or settings.ZOTERO_LIBRARY_TYPE

    with SessionLocal() as session:
        # Look up user
        user = crud.get_user_by_email(session=session, email=args.email)
        if not user:
            print(f"ERROR: No user found with email '{args.email}'")
            sys.exit(1)
        print(f"User: {user.full_name} ({user.email})")

        # Build Zotero client — use explicit credentials if provided, otherwise from user
        if args.zotero_id or args.zotero_api_key:
            user_data = user.model_dump()
            zot_id = args.zotero_id or user_data["zotero_id"]
            zot_key = args.zotero_api_key or user_data["enc_zotero_api_key"]
            zot = pyzotero.Zotero(zot_id, library_type, zot_key)
            print(f"Using {'CLI-provided' if args.zotero_id else 'user'} library ID: {zot_id}")
        else:
            zot = Zotero(user=user, library_type=library_type)
        collection_id = args.collection_id
        if collection_id is None:
            collection_id = prompt_for_collection(zot)

        # Fetch Zotero items
        print(f"\nFetching items from Zotero ({library_type} library)...")
        zot_items = fetch_zotero_items(zot, collection_id=collection_id)
        print(f"Fetched {len(zot_items)} top-level items from Zotero")

        # Build DOI map
        doi_map = build_doi_map(zot_items)
        print(f"Found {len(doi_map)} items with DOIs in Zotero")

        # Query local items with a DOI
        local_items = session.exec(
            select(Item).where(
                Item.owner_id == user.id,
                Item.doi.isnot(None),  # noqa: FBT003
            )
        ).all()
        print(f"Found {len(local_items)} local items with DOIs")

        # Match and enrich
        matched = 0
        updated = 0
        skipped = 0

        for item in local_items:
            doi_key = (item.doi or "").strip().lower()
            if not doi_key or doi_key not in doi_map:
                continue
            matched += 1
            zot_data = doi_map[doi_key]

            changes = enrich_item(item, zot_data, dry_run=args.dry_run)

            # Handle creators separately
            zot_creators = zot_data.get("creators", [])
            if zotero_has_richer_creators(zot_creators, item.creators):
                changes.append(f"creators: {len(item.creators)} -> {len(zot_creators)} (richer)")
                if not args.dry_run:
                    # Remove existing creators
                    for creator in list(item.creators):
                        session.delete(creator)
                    session.flush()
                    # Add Zotero creators
                    for creator_data in zot_creators:
                        creator = Creator(
                            item_id=item.id,
                            creatorType=creator_data.get("creatorType", "author"),
                            firstName=creator_data.get("firstName", ""),
                            lastName=creator_data.get("lastName", ""),
                        )
                        session.add(creator)

            if changes:
                updated += 1
                prefix = "[DRY RUN] " if args.dry_run else ""
                print(f"\n{prefix}Updating: {item.doi}")
                for change in changes:
                    print(f"  {change}")
            else:
                skipped += 1

        if not args.dry_run:
            session.commit()

        # Summary
        print(f"\n{'=' * 60}")
        print("SUMMARY")
        print(f"{'=' * 60}")
        print(f"  Zotero items fetched:    {len(zot_items)}")
        print(f"  Local items with DOI:    {len(local_items)}")
        print(f"  DOI matches:             {matched}")
        print(f"  Items updated:           {updated}")
        print(f"  Items unchanged:         {skipped}")
        if args.dry_run:
            print("\n  (Dry run — no changes written to DB)")


if __name__ == "__main__":
    main()
