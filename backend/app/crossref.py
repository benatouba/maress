"""CrossRef API integration for enriching publication metadata."""

from __future__ import annotations

import logging
import re
import time
from urllib.parse import quote

import httpx

from app.models import Item

logger = logging.getLogger(__name__)

CROSSREF_API_BASE = "https://api.crossref.org/works"
CROSSREF_POLITE_DELAY = 0.5  # seconds between requests (polite pool)


def _crossref_headers(email: str) -> dict[str, str]:
    """Build polite CrossRef API headers."""
    return {
        "User-Agent": f"Maress/0.1 (mailto:{email})",
        "Accept": "application/json",
    }


def _parse_crossref_work(work: dict) -> dict:
    """Extract relevant fields from a CrossRef work object."""
    title = None
    if work.get("title"):
        title = work["title"][0][:255]

    abstract = work.get("abstract", "") or ""
    # CrossRef abstracts may contain JATS XML tags -- strip them
    abstract = re.sub(r"<[^>]+>", "", abstract)[:8192]

    doi = work.get("DOI", "")[:128] or None

    year = None
    for date_field in ("published-print", "published-online", "issued"):
        date_parts = work.get(date_field, {}).get("date-parts", [[]])
        if date_parts and date_parts[0] and date_parts[0][0]:
            year = str(date_parts[0][0])
            break

    authors = []
    for author in work.get("author", []):
        family = author.get("family", "")
        given = author.get("given")
        if family:
            authors.append({
                "lastName": family,
                "firstName": given,
                "creatorType": "author",
            })

    return {
        "title": title,
        "doi": doi,
        "abstract": abstract,
        "year": year,
        "authors": authors,
    }


def fetch_crossref_by_doi(doi: str, *, email: str) -> dict | None:
    """Fetch metadata from CrossRef by DOI.

    Args:
        doi: The DOI string (e.g. "10.1234/example").
        email: Contact email for polite pool.

    Returns:
        Parsed metadata dict, or None on failure.
    """
    url = f"{CROSSREF_API_BASE}/{quote(doi, safe='')}"
    try:
        resp = httpx.get(url, headers=_crossref_headers(email), timeout=15)
        if resp.status_code == 200:  # noqa: PLR2004
            work = resp.json().get("message", {})
            return _parse_crossref_work(work)
        logger.warning("CrossRef lookup by DOI %s returned %d", doi, resp.status_code)
    except httpx.HTTPError:
        logger.warning("CrossRef request failed for DOI %s", doi, exc_info=True)
    return None


def fetch_crossref_by_title(title: str, year: str | None, *, email: str) -> dict | None:
    """Search CrossRef by title (and optionally year) and return best match.

    Args:
        title: Paper title to search.
        year: Publication year for filtering (optional).
        email: Contact email for polite pool.

    Returns:
        Parsed metadata dict, or None if no good match.
    """
    params: dict[str, str | int] = {
        "query.bibliographic": title,
        "rows": 3,
    }
    if year:
        params["filter"] = f"from-pub-date:{year},until-pub-date:{year}"

    try:
        resp = httpx.get(
            CROSSREF_API_BASE,
            params=params,
            headers=_crossref_headers(email),
            timeout=15,
        )
        if resp.status_code != 200:  # noqa: PLR2004
            logger.warning("CrossRef title search returned %d", resp.status_code)
            return None

        items = resp.json().get("message", {}).get("items", [])
        if not items:
            return None

        # Take the first (highest relevance) result
        return _parse_crossref_work(items[0])
    except httpx.HTTPError:
        logger.warning("CrossRef title search failed for '%s'", title, exc_info=True)
    return None


def enrich_item(item: Item, *, email: str) -> dict[str, bool]:
    """Enrich an Item's missing title/abstract/DOI via CrossRef.

    Tries DOI lookup first, then title+year search as fallback.

    Args:
        item: The database Item to enrich.
        email: Contact email for CrossRef polite pool.

    Returns:
        Dict of which fields were updated (e.g. {"title": True, "abstract": True}).
    """
    needs_title = not item.title
    needs_abstract = not item.abstractNote
    needs_doi = not item.doi

    if not (needs_title or needs_abstract or needs_doi):
        return {}

    cr_data = None

    # Try DOI lookup first (more reliable)
    if item.doi:
        cr_data = fetch_crossref_by_doi(item.doi, email=email)
        time.sleep(CROSSREF_POLITE_DELAY)

    # Fallback: title+year search
    if cr_data is None and item.title and item.date:
        cr_data = fetch_crossref_by_title(item.title, item.date, email=email)
        time.sleep(CROSSREF_POLITE_DELAY)

    if cr_data is None:
        return {}

    updated: dict[str, bool] = {}

    if needs_title and cr_data.get("title"):
        item.title = cr_data["title"]
        updated["title"] = True

    if needs_abstract and cr_data.get("abstract"):
        item.abstractNote = cr_data["abstract"]
        updated["abstract"] = True

    if needs_doi and cr_data.get("doi"):
        item.doi = cr_data["doi"]
        updated["doi"] = True

    return updated
