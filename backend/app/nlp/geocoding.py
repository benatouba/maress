"""Geocoding with caching and rate limiting (Phase 1 improvement).

This module provides a geocoding service that:
- Caches results to avoid duplicate API calls
- Enforces rate limiting (1 req/sec for Nominatim)
- Supports geographic biasing for better accuracy
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from geopy.geocoders import Nominatim
from geopy.point import Point

from app.core.config import settings
from app.nlp.domain_models import GeoEntity
from app.nlp.nlp_logger import logger

if TYPE_CHECKING:
    from geopy.location import Location as GeopyLocation


class GeocodingCache:
    """In-memory cache for geocoding results."""

    def __init__(self, ttl: int = 60 * 60 * 24 * 30) -> None:  # 30 days default
        """Initialize cache.

        Args:
            ttl: Time to live in seconds (not enforced, for future use)
        """
        self.ttl = ttl
        self._cache: dict[str, tuple[float, float] | None] = {}

    def get(self, location_name: str, bias_point: Point | None = None) -> tuple[float, float] | None | type[KeyError]:
        """Get cached coordinates for location.

        Args:
            location_name: Location name to look up
            bias_point: Geographic bias point (for cache key)

        Returns:
            Coordinates tuple, None if location not found, or KeyError if not cached
        """
        cache_key = self._make_key(location_name, bias_point)
        if cache_key in self._cache:
            return self._cache[cache_key]
        return KeyError

    def set(
        self,
        location_name: str,
        coordinates: tuple[float, float] | None,
        bias_point: Point | None = None,
    ) -> None:
        """Cache geocoding result.

        Args:
            location_name: Location name
            coordinates: Coordinates tuple or None if not found
            bias_point: Geographic bias point
        """
        cache_key = self._make_key(location_name, bias_point)
        self._cache[cache_key] = coordinates

    def _make_key(self, location_name: str, bias_point: Point | None) -> str:
        """Create cache key."""
        if bias_point:
            return f"{location_name}_{bias_point.latitude}_{bias_point.longitude}"
        return location_name

    def clear(self) -> None:
        """Clear cache."""
        self._cache.clear()

    def size(self) -> int:
        """Get cache size."""
        return len(self._cache)


class CachedGeocoder:
    """Geocoder with caching and rate limiting.

    Implements Phase 1 improvements:
    - In-memory cache to prevent duplicate API calls
    - Rate limiting (1 req/sec for Nominatim compliance)
    - Geographic biasing for better accuracy
    """

    def __init__(
        self,
        user_agent: str = "maress_study_site_extractor",
        rate_limit: float = 1.0,  # seconds between requests
    ) -> None:
        """Initialize geocoder.

        Args:
            user_agent: User agent for Nominatim
            rate_limit: Minimum seconds between API requests
        """
        self.geocoder = Nominatim(user_agent=user_agent, timeout=15)
        self.cache = GeocodingCache()
        self.rate_limit = rate_limit
        self._last_request_time: float = 0.0

    def geocode(
        self,
        location_name: str,
        bias_point: Point | None = None,
        bias_radius_km: float = 500.0,
    ) -> tuple[float, float] | None:
        """Geocode location with caching and rate limiting.

        Args:
            location_name: Location name to geocode
            bias_point: Optional point to bias results toward
            bias_radius_km: Radius for geographic bias (km)

        Returns:
            Tuple of (latitude, longitude) or None if not found
        """
        # Check cache first
        cached_result = self.cache.get(location_name, bias_point)
        if cached_result is not KeyError:
            if cached_result is not None:
                logger.debug(f"Cache hit for {location_name}")
            return cached_result

        # Rate limiting
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit:
            sleep_time = self.rate_limit - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)

        # Geocode
        try:
            geocoded: GeopyLocation | None = None

            if bias_point:
                # Calculate viewbox (approximate square around bias point)
                # 1 degree ≈ 111 km at equator
                delta = bias_radius_km / 111.0

                viewbox = (
                    Point(
                        latitude=bias_point.latitude - delta,
                        longitude=bias_point.longitude - delta,
                    ),
                    Point(
                        latitude=bias_point.latitude + delta,
                        longitude=bias_point.longitude + delta,
                    ),
                )

                # Try with bias first
                geocoded = self.geocoder.geocode(
                    location_name,
                    viewbox=viewbox,
                    bounded=True,
                    timeout=10,
                )

            # Fallback to unbounded search
            if not geocoded:
                geocoded = self.geocoder.geocode(location_name, timeout=10)

            self._last_request_time = time.time()

            if geocoded:
                coords = (geocoded.latitude, geocoded.longitude)
                self.cache.set(location_name, coords, bias_point)
                logger.info(f"Geocoded {location_name}: {coords}")
                return coords

            # Cache negative result
            self.cache.set(location_name, None, bias_point)
            logger.info(f"Could not geocode {location_name}")
            return None

        except Exception as e:
            logger.warning(f"Geocoding error for {location_name}: {e}")
            # Cache failure to avoid retrying
            self.cache.set(location_name, None, bias_point)
            return None

    def geocode_entities(
        self,
        entities: list[GeoEntity],
        bias_point: Point | None = None,
    ) -> list[GeoEntity]:
        """Geocode multiple entities, updating their coordinates.

        Args:
            entities: List of entities to geocode
            bias_point: Optional geographic bias

        Returns:
            List of entities (some with updated coordinates)
        """
        geocoded_entities: list[GeoEntity] = []

        for entity in entities:
            # Skip if already has coordinates
            if entity.coordinates is not None:
                geocoded_entities.append(entity)
                continue

            # Skip if not a location entity
            if entity.entity_type not in ["LOC", "GPE", "SPATIAL_RELATION", "CONTEXTUAL_LOCATION"]:
                geocoded_entities.append(entity)
                continue

            # Geocode
            coords = self.geocode(entity.text, bias_point)

            if coords:
                # Create new entity with coordinates (GeoEntity is immutable)
                from pydantic import ValidationError

                try:
                    geocoded_entity = GeoEntity(
                        text=entity.text,
                        entity_type=entity.entity_type,
                        context=entity.context,
                        section=entity.section,
                        confidence=min(entity.confidence + 0.1, 1.0),  # Boost confidence
                        start_char=entity.start_char,
                        end_char=entity.end_char,
                        coordinates=coords,
                    )
                    geocoded_entities.append(geocoded_entity)
                except ValidationError as e:
                    logger.warning(f"Failed to create geocoded entity: {e}")
                    geocoded_entities.append(entity)
            else:
                geocoded_entities.append(entity)

        return geocoded_entities

    def clear_cache(self) -> None:
        """Clear geocoding cache."""
        self.cache.clear()
        logger.info("Geocoding cache cleared")

    def cache_stats(self) -> dict[str, int]:
        """Get cache statistics."""
        return {
            "size": self.cache.size(),
            "ttl_seconds": self.cache.ttl,
        }


# Global geocoder instance (singleton pattern)
_geocoder: CachedGeocoder | None = None


def get_geocoder() -> CachedGeocoder:
    """Get global geocoder instance."""
    global _geocoder
    if _geocoder is None:
        _geocoder = CachedGeocoder(rate_limit=settings.GEOCODING_RATE_LIMIT)
    return _geocoder
