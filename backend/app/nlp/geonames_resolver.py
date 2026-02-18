"""GeoNames entity linking for location disambiguation.

This module provides entity linking to the GeoNames database for:
- Disambiguating ambiguous location names (e.g., "Washington" -> state or DC)
- Enriching location entities with structured metadata
- Improving geocoding accuracy with feature class hints

Uses the GeoNames API (http://www.geonames.org/export/web-services.html).
Requires a free GeoNames username (register at http://www.geonames.org/login).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import TYPE_CHECKING, ClassVar

import httpx

from app.nlp.nlp_logger import logger

if TYPE_CHECKING:
    from app.nlp.domain_models import GeoEntity


@dataclass
class GeoNameMatch:
    """A match from the GeoNames database."""

    geoname_id: int
    name: str
    country_code: str
    country_name: str
    admin1_code: str  # State/province
    admin1_name: str
    feature_class: str  # P=populated place, H=hydrological, T=terrain, etc.
    feature_code: str  # More specific (PPLA=admin center, STM=stream, etc.)
    latitude: float
    longitude: float
    population: int
    score: float = 0.0  # Relevance score (computed)

    @property
    def full_name(self) -> str:
        """Get full hierarchical name."""
        parts = [self.name]
        if self.admin1_name and self.admin1_name != self.name:
            parts.append(self.admin1_name)
        if self.country_name:
            parts.append(self.country_name)
        return ", ".join(parts)


@dataclass
class GeoNamesCache:
    """In-memory cache for GeoNames lookups."""

    cache: dict[str, list[GeoNameMatch]] = field(default_factory=dict)
    ttl: int = 60 * 60 * 24 * 7  # 7 days

    def get(self, key: str) -> list[GeoNameMatch] | None:
        """Get cached results."""
        return self.cache.get(key)

    def set(self, key: str, value: list[GeoNameMatch]) -> None:
        """Cache results."""
        self.cache[key] = value

    def clear(self) -> None:
        """Clear cache."""
        self.cache.clear()


class GeoNamesResolver:
    """Resolve location names to GeoNames entries with disambiguation.

    Uses context clues to rank matches:
    - Feature class hints (e.g., "river" suggests H class)
    - Population (prefer larger/more notable places)
    - Country/region bias from paper context
    """

    BASE_URL: ClassVar[str] = "http://api.geonames.org/searchJSON"

    # Feature class mapping for context-aware disambiguation
    FEATURE_CLASS_HINTS: ClassVar[dict[str, str]] = {
        # Water bodies -> H (hydrological)
        "river": "H", "stream": "H", "creek": "H", "lake": "H",
        "ocean": "H", "sea": "H", "bay": "H", "gulf": "H",
        "wetland": "H", "estuary": "H", "delta": "H",
        # Terrain -> T
        "mountain": "T", "volcano": "T", "hill": "T", "ridge": "T",
        "valley": "T", "canyon": "T", "plateau": "T", "glacier": "T",
        "basin": "T",
        # Vegetation -> V
        "forest": "V", "woodland": "V", "grassland": "V",
        # Parks/reserves -> L (area)
        "park": "L", "reserve": "L", "sanctuary": "L",
        # Populated places -> P
        "city": "P", "town": "P", "village": "P",
    }

    # Feature code priorities (higher = more relevant for study sites)
    FEATURE_CODE_PRIORITY: ClassVar[dict[str, int]] = {
        # Hydrological (very relevant for earth science)
        "STM": 10,   # Stream
        "LK": 10,    # Lake
        "RSV": 9,    # Reservoir
        "GLCR": 10,  # Glacier
        "WTLD": 10,  # Wetland
        "MRSH": 9,   # Marsh
        "SEA": 8,    # Sea
        "OCN": 8,    # Ocean
        # Terrain (very relevant)
        "MT": 10,    # Mountain
        "VLC": 10,   # Volcano
        "VAL": 9,    # Valley
        "PLN": 8,    # Plain
        "PLAT": 8,   # Plateau
        # Administrative (less relevant but common)
        "PCLI": 5,   # Country
        "ADM1": 6,   # First-order admin (state)
        "ADM2": 5,   # Second-order admin (county)
        "PPL": 4,    # Populated place
        "PPLA": 5,   # Admin center
        "PPLC": 6,   # Capital
    }

    def __init__(
        self,
        username: str | None = None,
        rate_limit: float = 1.0,
        max_results: int = 10,
    ) -> None:
        """Initialize the GeoNames resolver.

        Args:
            username: GeoNames username (get free account at geonames.org)
            rate_limit: Minimum seconds between API requests
            max_results: Maximum results per query
        """
        self.username = username
        self.rate_limit = rate_limit
        self.max_results = max_results
        self.cache = GeoNamesCache()
        self._last_request_time: float = 0.0
        self._client = httpx.Client(timeout=15.0)

    def resolve(
        self,
        location_name: str,
        context: str | None = None,
        country_bias: str | None = None,
    ) -> list[GeoNameMatch]:
        """Resolve a location name to GeoNames entries.

        Args:
            location_name: Location name to resolve
            context: Surrounding text for disambiguation hints
            country_bias: Preferred country code (e.g., "US", "DE")

        Returns:
            List of GeoNameMatch objects, ranked by relevance
        """
        if not self.username:
            logger.warning("GeoNames username not configured, skipping resolution")
            return []

        # Check cache
        cache_key = f"{location_name}|{country_bias or ''}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return self._rerank_with_context(cached, context)

        # Rate limiting
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)

        # Query GeoNames API
        try:
            matches = self._query_geonames(location_name, country_bias)
            self.cache.set(cache_key, matches)
            self._last_request_time = time.time()

            return self._rerank_with_context(matches, context)

        except Exception as e:
            logger.warning(f"GeoNames query failed for '{location_name}': {e}")
            return []

    def _query_geonames(
        self,
        location_name: str,
        country_bias: str | None = None,
    ) -> list[GeoNameMatch]:
        """Query the GeoNames API.

        Args:
            location_name: Location to search
            country_bias: Preferred country code

        Returns:
            List of GeoNameMatch objects
        """
        params = {
            "q": location_name,
            "maxRows": self.max_results,
            "username": self.username,
            "style": "FULL",
            "orderby": "relevance",
        }

        if country_bias:
            params["countryBias"] = country_bias

        response = self._client.get(self.BASE_URL, params=params)
        response.raise_for_status()

        data = response.json()

        if "geonames" not in data:
            if "status" in data:
                logger.warning(f"GeoNames API error: {data['status'].get('message', 'Unknown error')}")
            return []

        matches = []
        for item in data["geonames"]:
            match = GeoNameMatch(
                geoname_id=item.get("geonameId", 0),
                name=item.get("name", ""),
                country_code=item.get("countryCode", ""),
                country_name=item.get("countryName", ""),
                admin1_code=item.get("adminCode1", ""),
                admin1_name=item.get("adminName1", ""),
                feature_class=item.get("fcl", ""),
                feature_code=item.get("fcode", ""),
                latitude=float(item.get("lat", 0)),
                longitude=float(item.get("lng", 0)),
                population=int(item.get("population", 0)),
            )
            matches.append(match)

        return matches

    def _rerank_with_context(
        self,
        matches: list[GeoNameMatch],
        context: str | None,
    ) -> list[GeoNameMatch]:
        """Rerank matches based on context clues.

        Args:
            matches: List of matches to rerank
            context: Surrounding text for hints

        Returns:
            Reranked list of matches
        """
        if not matches:
            return matches

        # Extract feature class hint from context
        preferred_class = None
        if context:
            context_lower = context.lower()
            for keyword, fclass in self.FEATURE_CLASS_HINTS.items():
                if keyword in context_lower:
                    preferred_class = fclass
                    break

        # Score each match
        for match in matches:
            score = 0.0

            # Feature class match bonus
            if preferred_class and match.feature_class == preferred_class:
                score += 5.0

            # Feature code priority
            score += self.FEATURE_CODE_PRIORITY.get(match.feature_code, 0)

            # Population bonus (log scale)
            if match.population > 0:
                import math
                score += math.log10(match.population + 1) * 0.5

            # Exact name match bonus
            if match.name.lower() == context.lower() if context else False:
                score += 3.0

            match.score = score

        # Sort by score (descending)
        return sorted(matches, key=lambda m: m.score, reverse=True)

    def resolve_entity(
        self,
        entity: GeoEntity,
        country_bias: str | None = None,
    ) -> GeoNameMatch | None:
        """Resolve a GeoEntity to the best GeoNames match.

        Args:
            entity: Entity to resolve
            country_bias: Preferred country code

        Returns:
            Best matching GeoNameMatch, or None
        """
        matches = self.resolve(
            entity.text,
            context=entity.context,
            country_bias=country_bias,
        )

        if matches:
            return matches[0]
        return None

    def enrich_entities(
        self,
        entities: list[GeoEntity],
        country_bias: str | None = None,
    ) -> list[tuple[GeoEntity, GeoNameMatch | None]]:
        """Enrich multiple entities with GeoNames matches.

        Args:
            entities: List of entities to enrich
            country_bias: Preferred country code

        Returns:
            List of (entity, match) tuples
        """
        results = []
        for entity in entities:
            # Only resolve location-type entities
            if entity.entity_type in ["LOC", "GPE", "WATER_BODY", "GEO_FEATURE"]:
                match = self.resolve_entity(entity, country_bias)
                results.append((entity, match))
            else:
                results.append((entity, None))

        return results

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()


# Singleton instance
_resolver: GeoNamesResolver | None = None


def get_geonames_resolver(username: str | None = None) -> GeoNamesResolver:
    """Get the GeoNames resolver instance.

    Args:
        username: GeoNames username (only needed on first call)

    Returns:
        GeoNamesResolver instance
    """
    global _resolver
    if _resolver is None:
        # Try to get username from settings
        if username is None:
            try:
                from app.core.config import settings
                username = getattr(settings, "GEONAMES_USERNAME", None)
            except ImportError:
                pass

        _resolver = GeoNamesResolver(username=username)

    return _resolver


@lru_cache(maxsize=1000)
def get_feature_class_for_context(context: str) -> str | None:
    """Get the likely GeoNames feature class for a context string.

    Uses LRU cache for performance.

    Args:
        context: Context text

    Returns:
        Feature class code or None
    """
    context_lower = context.lower()
    for keyword, fclass in GeoNamesResolver.FEATURE_CLASS_HINTS.items():
        if keyword in context_lower:
            return fclass
    return None
