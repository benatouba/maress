"""Geocoding with caching and rate limiting (Phase 1 improvement).

This module provides a geocoding service that:
- Caches results to avoid duplicate API calls
- Enforces rate limiting (1 req/sec for Nominatim)
- Supports geographic biasing for better accuracy
"""

from __future__ import annotations

from collections import Counter
import re
import time
from typing import TYPE_CHECKING, ClassVar, Mapping

from geopy.adapters import AdapterHTTPError
from geopy.distance import geodesic
from geopy.exc import GeocoderServiceError
from geopy.geocoders import Nominatim
from geopy.point import Point

from app.core.config import settings
from app.nlp.domain_models import GeoEntity
from app.nlp.geonames_resolver import get_geonames_resolver
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

    def get(
        self,
        location_name: str,
        bias_point: Point | None = None,
        country_hints: set[str] | None = None,
    ) -> tuple[float, float] | None:
        """Get cached coordinates for location.

        Args:
            location_name: Location name to look up
            bias_point: Geographic bias point (for cache key)
        """
        cache_key = self._make_key(location_name, bias_point, country_hints)
        return self._cache[cache_key]

    def set(
        self,
        location_name: str,
        coordinates: tuple[float, float] | None,
        bias_point: Point | None = None,
        country_hints: set[str] | None = None,
    ) -> None:
        """Cache geocoding result.

        Args:
            location_name: Location name
            coordinates: Coordinates tuple or None if not found
            bias_point: Geographic bias point
        """
        cache_key = self._make_key(location_name, bias_point, country_hints)
        self._cache[cache_key] = coordinates

    def _make_key(
        self,
        location_name: str,
        bias_point: Point | None,
        country_hints: set[str] | None,
    ) -> str:
        """Create cache key."""
        normalized_name = self._normalise_location_name(location_name)
        hints_part = ""
        if country_hints:
            hints_part = "|cc=" + ",".join(sorted(code.lower() for code in country_hints))

        if bias_point:
            lat = round(float(bias_point[0]), 3)
            lon = round(float(bias_point[1]), 3)
            return f"{normalized_name}_{lat}_{lon}{hints_part}"
        return f"{normalized_name}{hints_part}"

    @staticmethod
    def _normalise_location_name(location_name: str) -> str:
        """Normalise location names for cache reuse."""
        return " ".join(location_name.strip().lower().split())

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

    GENERIC_LOCATION_TERMS: ClassVar[set[str]] = {
        "study area",
        "study site",
        "study sites",
        "study region",
        "research site",
        "sampling site",
        "field site",
        "site",
        "sites",
        "area",
        "region",
        "location",
        "locations",
        "station",
        "stations",
        "this study",
        "our study",
    }
    STOPWORD_LIKE_TOKENS: ClassVar[set[str]] = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "in",
        "on",
        "at",
        "to",
        "from",
        "for",
        "by",
        "near",
        "with",
        "between",
        "around",
        "within",
    }
    GENERIC_FUSED_PREFIX_TERMS: ClassVar[set[str]] = {
        "bank",
        "banks",
        "shore",
        "flank",
        "area",
        "region",
        "site",
        "sites",
        "valley",
        "basin",
        "plateau",
    }
    DETERMINER_PREFIXES: ClassVar[set[str]] = {
        "the",
        "this",
        "that",
        "these",
        "those",
        "its",
        "their",
        "our",
    }
    NON_LOCATION_CONTENT_TOKENS: ClassVar[set[str]] = {
        "regression",
        "correlation",
        "sampling",
        "equipment",
        "atmosphere",
        "development",
        "biomass",
        "surface",
        "campaign",
        "season",
        "linear",
        "figure",
        "table",
        "supplementary",
        "method",
        "methods",
        "result",
        "results",
        "discussion",
    }
    MAX_LOCATION_NAME_CHARS: ClassVar[int] = 80
    MAX_LOCATION_NAME_TOKENS: ClassVar[int] = 6
    COUNTRY_HINTS: ClassVar[dict[str, str]] = {
        "argentina": "ar",
        "chile": "cl",
        "bolivia": "bo",
        "peru": "pe",
        "ecuador": "ec",
        "colombia": "co",
        "brazil": "br",
        "uruguay": "uy",
        "paraguay": "py",
        "mexico": "mx",
        "canada": "ca",
        "united states": "us",
        "usa": "us",
        "u.s.": "us",
        "u.s.a.": "us",
        "germany": "de",
        "france": "fr",
        "spain": "es",
        "italy": "it",
        "switzerland": "ch",
        "austria": "at",
        "uk": "gb",
        "united kingdom": "gb",
        "england": "gb",
        "scotland": "gb",
        "wales": "gb",
        "ireland": "ie",
        "iceland": "is",
        "norway": "no",
        "sweden": "se",
        "finland": "fi",
        "denmark": "dk",
        "netherlands": "nl",
        "belgium": "be",
        "poland": "pl",
        "czech republic": "cz",
        "slovakia": "sk",
        "hungary": "hu",
        "romania": "ro",
        "bulgaria": "bg",
        "greece": "gr",
        "turkey": "tr",
        "russia": "ru",
        "china": "cn",
        "india": "in",
        "japan": "jp",
        "korea": "kr",
        "south korea": "kr",
        "indonesia": "id",
        "australia": "au",
        "new zealand": "nz",
        "south africa": "za",
        "namibia": "na",
        "botswana": "bw",
        "egypt": "eg",
        "morocco": "ma",
    }
    FEATURE_HINTS: ClassVar[dict[str, str]] = {
        "city": "city",
        "town": "city",
        "village": "city",
        "capital": "city",
    }
    CONTEXT_FEATURE_HINTS: ClassVar[dict[str, str]] = {
        "city": "city",
        "town": "city",
        "village": "city",
        "capital": "city",
    }
    MAX_GEOCODE_DISTANCE_WITHOUT_BIAS_KM: ClassVar[float] = 3000.0
    MAX_GEOCODE_DISTANCE_WITH_BIAS_KM: ClassVar[float] = 1200.0
    MAX_GEOCODE_DISTANCE_PER_CANDIDATE_KM: ClassVar[float] = 1800.0
    GEOCODER_TOP_K: ClassVar[int] = 5
    LOW_SIGNAL_SECTIONS: ClassVar[set[str]] = {
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
    STUDY_SITE_CONTEXT_CUE_PATTERNS: ClassVar[list[re.Pattern[str]]] = [
        re.compile(
            r"(?:study|sampling|field|research)\s+(?:site|sites|area|location|station|plot)",
            re.IGNORECASE,
        ),
        re.compile(r"\b(?:located|situated|established|collected|sampled)\s+(?:at|in|near)\b", re.IGNORECASE),
        re.compile(r"\b(?:coordinates?|latitude|longitude|lat\.?|lon\.?)\b", re.IGNORECASE),
        re.compile(r"\b\d{1,2}(?:\.\d+)?\s*[°º]?\s*[NS]\b", re.IGNORECASE),
    ]

    @staticmethod
    def _tokenize_text(value: str) -> set[str]:
        return {token for token in re.findall(r"[A-Za-z]+", value.lower()) if token}

    def _infer_country_hints(self, entities: list[GeoEntity], bias_point: Point | None) -> set[str]:
        """Infer likely country hints from extracted entities.

        Hints are used to constrain geocoder candidate search when possible.
        """
        hints: set[str] = set()

        for entity in entities:
            tokens = self._tokenize_text(entity.text)
            for country_name, code in self.COUNTRY_HINTS.items():
                if country_name in entity.text.lower():
                    hints.add(code)
                elif any(part in tokens for part in country_name.split()):
                    # only add for exact token matches to avoid over-triggering
                    if all(part in tokens for part in country_name.split()):
                        hints.add(code)

        # Bias point in South America often appears in this dataset. Keep this
        # conservative and only infer broad hints when no explicit country was found.
        if not hints and bias_point is not None:
            lat = float(bias_point[0])
            lon = float(bias_point[1])
            if -60 <= lat <= 20 and -90 <= lon <= -30:
                hints.update({"ar", "cl", "bo", "pe"})

        return hints

    def _infer_feature_hint(self, entity: GeoEntity) -> str | None:
        """Infer geocoder feature type hint from entity text/context."""
        if entity.entity_type == "GPE":
            return "city"

        text_tokens = self._tokenize_text(entity.text)
        context_tokens = self._tokenize_text(entity.context)

        for keyword, hint in self.FEATURE_HINTS.items():
            if keyword in text_tokens:
                return hint

        for keyword, hint in self.CONTEXT_FEATURE_HINTS.items():
            if keyword in context_tokens:
                return hint

        return None

    def _resolve_bias_for_entity(
        self,
        entity: GeoEntity,
        *,
        default_bias: Point | None,
        country_hints: set[str],
    ) -> Point | None:
        """Resolve a tighter bias point using GeoNames when available."""
        if not self.geonames_resolver.username:
            return default_bias

        geonames_match = self.geonames_resolver.resolve_entity(entity)
        if geonames_match is not None:
            country = geonames_match.country_code.lower()
            if not country_hints or country in country_hints:
                return Point(
                    latitude=geonames_match.latitude,
                    longitude=geonames_match.longitude,
                )
        return default_bias

    @staticmethod
    def _name_quality_score(name: str) -> float:
        """Return a compact quality score for a location string."""
        tokens = [t for t in re.findall(r"[A-Za-z]+", name)]
        if not tokens:
            return 0.0

        score = 0.0
        if len(tokens) > 1:
            score += 0.25
        if any(token[0].isupper() for token in tokens if token):
            score += 0.15
        if any(len(token) >= 6 for token in tokens):
            score += 0.1
        if "," in name:
            score += 0.15
        if "-" in name:
            score += 0.05
        return min(score, 0.6)

    @staticmethod
    def _normalised_match_score(query: str, candidate: str) -> float:
        q_tokens = {t.lower() for t in re.findall(r"[A-Za-z]+", query) if t}
        c_tokens = {t.lower() for t in re.findall(r"[A-Za-z]+", candidate) if t}
        if not q_tokens or not c_tokens:
            return 0.0
        intersection = len(q_tokens.intersection(c_tokens))
        union = len(q_tokens.union(c_tokens))
        return intersection / union

    @staticmethod
    def _candidate_distance_km(first: GeopyLocation, second: GeopyLocation) -> float:
        """Return geodesic distance between two geocoding candidates."""
        return geodesic(
            (float(first.latitude), float(first.longitude)),
            (float(second.latitude), float(second.longitude)),
        ).km

    def _has_study_site_context_cue(self, context: str) -> bool:
        """Return whether context has explicit study-site cues."""
        if not context:
            return False
        return any(pattern.search(context) for pattern in self.STUDY_SITE_CONTEXT_CUE_PATTERNS)

    def _score_geocode_candidate(
        self,
        *,
        query_name: str,
        candidate: GeopyLocation,
        candidate_bias: Point | None,
        country_hints: set[str],
    ) -> float:
        """Score a geocoding candidate using lexical and spatial signals."""
        score = 0.0

        raw_name = str(candidate.address or "")
        score += 2.0 * self._normalised_match_score(query_name, raw_name)

        if candidate.raw:
            candidate_country = str(candidate.raw.get("address", {}).get("country_code", "")).lower()
            if country_hints and candidate_country and candidate_country in country_hints:
                score += 1.0
            elif country_hints and candidate_country and candidate_country not in country_hints:
                score -= 1.25

            importance = candidate.raw.get("importance")
            try:
                score += float(importance) * 0.5
            except (TypeError, ValueError):
                pass

            place_rank = candidate.raw.get("place_rank")
            try:
                rank_val = float(place_rank)
            except (TypeError, ValueError):
                rank_val = 0.0

            if 8 <= rank_val <= 24:
                score += 0.25

        if candidate_bias is not None:
            dist_km = geodesic(
                (float(candidate.latitude), float(candidate.longitude)),
                (float(candidate_bias[0]), float(candidate_bias[1])),
            ).km
            score += max(0.0, 1.0 - min(dist_km / self.max_distance_per_candidate_km, 1.0))

        return score

    def _build_query_variants(self, location_name: str, country_hints: set[str]) -> list[str]:
        """Build high-signal query variants for geocoding."""
        base = " ".join(location_name.strip().split())
        if not base:
            return []

        variants = [base]
        if "," not in base:
            tokens = base.split()
            if len(tokens) == 1 and country_hints:
                # keep single-token names but add one constrained variant
                variants.append(f"{base}, {next(iter(sorted(country_hints))).upper()}")

        # Deduplicate while preserving order
        deduped: list[str] = []
        seen: set[str] = set()
        for item in variants:
            key = item.lower()
            if key not in seen:
                seen.add(key)
                deduped.append(item)

        return deduped

    def _select_best_location(
        self,
        *,
        location_name: str,
        country_hints: set[str],
        feature_hint: str | None,
        bias_point: Point | None,
        bias_radius_km: float,
    ) -> GeopyLocation | None:
        """Fetch and select best location from geocoder candidates."""
        self._last_selection_rejection_reason = None
        query_variants = self._build_query_variants(location_name, country_hints)
        if not query_variants:
            self._last_selection_rejection_reason = "no_query_variants"
            return None

        viewbox: tuple[Point, Point] | None = None
        if bias_point:
            delta = bias_radius_km / 111.0
            viewbox = (
                Point(
                    latitude=float(bias_point[0]) - delta,
                    longitude=float(bias_point[1]) - delta,
                ),
                Point(
                    latitude=float(bias_point[0]) + delta,
                    longitude=float(bias_point[1]) + delta,
                ),
            )

        candidates: list[GeopyLocation] = []
        for query_variant in query_variants:
            kwargs: dict[str, object] = {
                "exactly_one": False,
                "limit": self.GEOCODER_TOP_K,
                "timeout": 10,
                "addressdetails": True,
            }
            if feature_hint:
                kwargs["featuretype"] = feature_hint
            if country_hints:
                kwargs["country_codes"] = ",".join(sorted(country_hints))
            if viewbox is not None:
                kwargs["viewbox"] = viewbox
                kwargs["bounded"] = True

            result = self.geocoder.geocode(query_variant, **kwargs)
            if isinstance(result, list):
                candidates.extend(result)
            elif result is not None:
                candidates.append(result)

            # Unbounded fallback when bounded search returns nothing
            if not candidates and viewbox is not None:
                unbounded_kwargs = dict(kwargs)
                unbounded_kwargs.pop("viewbox", None)
                unbounded_kwargs.pop("bounded", None)
                result = self.geocoder.geocode(query_variant, **unbounded_kwargs)
                if isinstance(result, list):
                    candidates.extend(result)
                elif result is not None:
                    candidates.append(result)

            if candidates:
                break

        if not candidates:
            self._last_selection_rejection_reason = "no_candidates"
            return None

        return self._select_best_location_from_candidates(
            location_name=location_name,
            candidates=candidates,
            country_hints=country_hints,
            bias_point=bias_point,
        )

    def _select_best_location_from_candidates(
        self,
        *,
        location_name: str,
        candidates: list[GeopyLocation],
        country_hints: set[str],
        bias_point: Point | None,
    ) -> GeopyLocation | None:
        """Select the best geocoding candidate with precision guards."""
        if not candidates:
            self._last_selection_rejection_reason = "no_candidates"
            return None

        scored = [
            (
                self._score_geocode_candidate(
                    query_name=location_name,
                    candidate=c,
                    candidate_bias=bias_point,
                    country_hints=country_hints,
                ),
                c,
            )
            for c in candidates
        ]
        scored.sort(key=lambda item: item[0], reverse=True)

        top_score, top_candidate = scored[0]
        if top_score < self.min_top_candidate_score:
            self._last_selection_rejection_reason = "top_score_below_threshold"
            logger.debug(
                "Rejecting geocode for '%s': top score %.3f below %.3f",
                location_name,
                top_score,
                self.min_top_candidate_score,
            )
            return None

        if len(scored) > 1:
            second_score, second_candidate = scored[1]
            score_margin = top_score - second_score
            if score_margin < self.ambiguity_score_margin:
                candidate_distance = self._candidate_distance_km(top_candidate, second_candidate)
                if candidate_distance >= self.ambiguity_distance_km:
                    self._last_selection_rejection_reason = "ambiguous_top_candidates"
                    logger.info(
                        "Rejecting ambiguous geocode for '%s': margin %.3f < %.3f and "
                        "candidate distance %.1f km >= %.1f km",
                        location_name,
                        score_margin,
                        self.ambiguity_score_margin,
                        candidate_distance,
                        self.ambiguity_distance_km,
                    )
                    return None

        self._last_selection_rejection_reason = None
        return top_candidate

    @staticmethod
    def _compute_centroid(points: list[tuple[float, float]]) -> tuple[float, float] | None:
        if not points:
            return None
        lat_sum = sum(p[0] for p in points)
        lon_sum = sum(p[1] for p in points)
        n = float(len(points))
        return (lat_sum / n, lon_sum / n)

    def _compute_document_bias_point(
        self,
        entities: list[GeoEntity],
        explicit_bias: Point | None,
    ) -> Point | None:
        """Compute a robust bias point from explicit bias and hard coordinates."""
        coordinate_points = [
            (float(e.coordinates[0]), float(e.coordinates[1]))
            for e in entities
            if e.coordinates is not None
        ]

        if explicit_bias is not None:
            coordinate_points.append((float(explicit_bias[0]), float(explicit_bias[1])))

        centroid = self._compute_centroid(coordinate_points)
        if centroid is None:
            return None

        return Point(latitude=centroid[0], longitude=centroid[1])

    def _passes_distance_guard(
        self,
        coords: tuple[float, float],
        *,
        document_bias: Point | None,
        per_candidate_bias: Point | None,
    ) -> bool:
        """Reject geocodes that are implausibly far from document signal."""
        candidate_point = (float(coords[0]), float(coords[1]))

        if document_bias is not None:
            dist_to_doc = geodesic(
                candidate_point,
                (float(document_bias[0]), float(document_bias[1])),
            ).km
            if dist_to_doc > self.max_distance_without_bias_km:
                return False

        if per_candidate_bias is not None:
            dist_to_bias = geodesic(
                candidate_point,
                (float(per_candidate_bias[0]), float(per_candidate_bias[1])),
            ).km
            if dist_to_bias > self.max_distance_with_bias_km:
                return False

        return True

    def __init__(
        self,
        user_agent: str = "maress_study_site_extractor",
        rate_limit: float = 1.0,  # seconds between requests
        *,
        allow_live_requests: bool = True,
        max_candidates_per_doc: int = 20,
        min_candidate_confidence: float = 0.55,
        strict_other_section_min_confidence: float = 0.8,
        reject_determiner_prefix: bool = True,
        reject_non_location_content: bool = True,
        require_capitalized_multi_token: bool = True,
        max_distance_without_bias_km: float = 3000.0,
        max_distance_with_bias_km: float = 1200.0,
        max_distance_per_candidate_km: float = 1800.0,
        strict_low_signal_section_min_confidence: float = 0.9,
        require_context_cue_for_low_signal_section: bool = True,
        min_top_candidate_score: float = 0.85,
        ambiguity_score_margin: float = 0.35,
        ambiguity_distance_km: float = 250.0,
    ) -> None:
        """Initialize geocoder.

        Args:
            user_agent: User agent for Nominatim
            rate_limit: Minimum seconds between API requests
            allow_live_requests: Whether outbound geocoding requests are allowed
            max_candidates_per_doc: Max unique location names to geocode per document
            min_candidate_confidence: Min confidence required for geocoding candidates
            strict_other_section_min_confidence: Min confidence for entities from 'other' section
            reject_determiner_prefix: Reject candidates beginning with determiner-like terms
            reject_non_location_content: Reject content-like non-location phrases
            require_capitalized_multi_token: Require capitalization for multi-token candidates
            max_distance_without_bias_km: Max allowed distance from document bias
            max_distance_with_bias_km: Max allowed distance from per-candidate bias
            max_distance_per_candidate_km: Distance scale used for candidate scoring
            strict_low_signal_section_min_confidence: Minimum confidence for low-signal sections
            require_context_cue_for_low_signal_section: Require explicit study cues in low-signal sections
            min_top_candidate_score: Minimum score required for top geocoding candidate
            ambiguity_score_margin: Minimum score gap between top and second candidate
            ambiguity_distance_km: Distance threshold for rejecting close-score ambiguous candidates
        """
        self.geocoder = Nominatim(user_agent=user_agent, timeout=15)
        self.geonames_resolver = get_geonames_resolver()
        self.cache = GeocodingCache()
        self.rate_limit = rate_limit
        self.allow_live_requests = allow_live_requests
        self.max_candidates_per_doc = max_candidates_per_doc
        self.min_candidate_confidence = min_candidate_confidence
        self.strict_other_section_min_confidence = strict_other_section_min_confidence
        self.reject_determiner_prefix = reject_determiner_prefix
        self.reject_non_location_content = reject_non_location_content
        self.require_capitalized_multi_token = require_capitalized_multi_token
        self.max_distance_without_bias_km = max_distance_without_bias_km
        self.max_distance_with_bias_km = max_distance_with_bias_km
        self.max_distance_per_candidate_km = max_distance_per_candidate_km
        self.strict_low_signal_section_min_confidence = strict_low_signal_section_min_confidence
        self.require_context_cue_for_low_signal_section = require_context_cue_for_low_signal_section
        self.min_top_candidate_score = min_top_candidate_score
        self.ambiguity_score_margin = ambiguity_score_margin
        self.ambiguity_distance_km = ambiguity_distance_km
        self._last_request_time: float = 0.0
        self._last_error_was_rate_limit = False
        self._last_selection_rejection_reason: str | None = None
        self._last_geocode_failure_reason: str | None = None
        self._last_document_stats: dict[str, int] = {}

    def set_live_requests_enabled(self, enabled: bool) -> None:
        """Enable or disable outbound geocoding requests."""
        self.allow_live_requests = enabled

    def geocode(
        self,
        location_name: str,
        bias_point: Point | None = None,
        bias_radius_km: float = 500.0,
        country_hints: set[str] | None = None,
        feature_hint: str | None = None,
    ) -> tuple[float, float] | None:
        """Geocode location with caching and rate limiting.

        Args:
            location_name: Location name to geocode
            bias_point: Optional point to bias results toward
            bias_radius_km: Radius for geographic bias (km)
            country_hints: Optional ISO country-code hints
            feature_hint: Optional feature type hint for geocoder

        Returns:
            Tuple of (latitude, longitude) or None if not found
        """
        self._last_selection_rejection_reason = None
        self._last_geocode_failure_reason = None

        # Check cache first
        try:
            cached_result = self.cache.get(location_name, bias_point, country_hints)
        except KeyError:
            cached_result = None
            has_cache = False
        else:
            has_cache = True

        if has_cache:
            if cached_result is not None:
                logger.debug(f"Cache hit for {location_name}")
            return cached_result

        self._last_error_was_rate_limit = False

        if not self.allow_live_requests:
            logger.debug("Offline geocoding cache miss for %s", location_name)
            self.cache.set(location_name, None, bias_point, country_hints)
            self._last_geocode_failure_reason = "offline_cache_miss"
            return None

        # Rate limiting
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit:
            sleep_time = self.rate_limit - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)

        # Geocode
        try:
            geocoded = self._select_best_location(
                location_name=location_name,
                country_hints=country_hints or set(),
                feature_hint=feature_hint,
                bias_point=bias_point,
                bias_radius_km=bias_radius_km,
            )

            self._last_request_time = time.time()

            if geocoded:
                coords = (geocoded.latitude, geocoded.longitude)
                self.cache.set(location_name, coords, bias_point, country_hints)
                logger.info(f"Geocoded {location_name}: {coords}")
                self._last_geocode_failure_reason = None
                return coords

            # Cache negative result
            self.cache.set(location_name, None, bias_point, country_hints)
            logger.info(f"Could not geocode {location_name}")
            self._last_geocode_failure_reason = self._last_selection_rejection_reason or "not_found"
            return None

        except (GeocoderServiceError, AdapterHTTPError, TimeoutError, OSError) as e:
            error_text = str(e)
            self._last_error_was_rate_limit = "429" in error_text
            if self._last_error_was_rate_limit:
                logger.warning("Geocoding provider rate limit hit (429); applying cooldown")
                self._last_request_time = time.time() + max(self.rate_limit, 2.0)
                self._last_geocode_failure_reason = "provider_rate_limited"
            else:
                self._last_geocode_failure_reason = "provider_error"
            logger.warning(f"Geocoding error for {location_name}: {e}")
            # Cache failure to avoid retrying
            self.cache.set(location_name, None, bias_point, country_hints)
            return None

    def _geocoding_candidate_decision(
        self,
        entity: GeoEntity,
        min_confidence: float | None = None,
    ) -> tuple[bool, str]:
        """Return candidate acceptance decision and reason.

        The reason value is used for per-document telemetry.
        """
        if entity.coordinates is not None:
            return (False, "already_has_coordinates")
        if entity.entity_type not in {"LOC", "GPE"}:
            return (False, "unsupported_entity_type")

        effective_min_confidence = (
            self.min_candidate_confidence if min_confidence is None else min_confidence
        )

        if entity.confidence < effective_min_confidence:
            return (False, "below_min_confidence")

        candidate = " ".join(entity.text.strip().split())
        if not candidate:
            return (False, "empty_candidate")
        if len(candidate) > self.MAX_LOCATION_NAME_CHARS:
            return (False, "name_too_long")

        tokens = [token for token in re.split(r"[\s,]+", candidate) if token]
        if not tokens:
            return (False, "empty_token_list")
        if len(tokens) > self.MAX_LOCATION_NAME_TOKENS:
            return (False, "too_many_tokens")

        section_normalized = entity.section.lower().strip()
        if section_normalized in self.LOW_SIGNAL_SECTIONS:
            section_min_confidence = self.strict_low_signal_section_min_confidence
            if section_normalized == "other":
                section_min_confidence = max(
                    section_min_confidence,
                    self.strict_other_section_min_confidence,
                )
            if entity.confidence < max(effective_min_confidence, section_min_confidence):
                return (False, "low_signal_section_confidence")

            if self.require_context_cue_for_low_signal_section and not self._has_study_site_context_cue(
                entity.context,
            ):
                return (False, "low_signal_section_without_context_cue")

        # Reject obviously malformed candidates
        if any(char.isdigit() for char in candidate):
            return (False, "contains_digit")
        if re.search(r"[;:=\[\]{}<>|]", candidate):
            return (False, "contains_symbol_noise")

        alpha_tokens = re.findall(r"[A-Za-z]+", candidate)
        if not alpha_tokens:
            return (False, "no_alpha_tokens")

        alpha_tokens_lower = [token.lower() for token in alpha_tokens]

        candidate_lower = candidate.lower()
        if candidate_lower in self.GENERIC_LOCATION_TERMS:
            return (False, "generic_location_term")

        if self.reject_determiner_prefix and alpha_tokens_lower[0] in self.DETERMINER_PREFIXES:
            return (False, "determiner_prefix")

        if self.reject_non_location_content and any(
            token in self.NON_LOCATION_CONTENT_TOKENS for token in alpha_tokens_lower
        ):
            return (False, "non_location_content")

        # OCR often fuses a leading article into generic nouns
        # (for example: "thebanks").
        if len(tokens) == 1 and candidate_lower.startswith("the"):
            fused_suffix = candidate_lower[3:]
            if fused_suffix in self.GENERIC_FUSED_PREFIX_TERMS:
                return (False, "generic_fused_prefix")

        # Very short single-token strings are usually OCR fragments/noise.
        if len(alpha_tokens) == 1 and len(alpha_tokens[0]) <= 2:
            return (False, "single_token_too_short")

        # Most valid toponyms retain capitalization even in noisy OCR. Reject
        # multi-token all-lowercase strings that look like sentence fragments.
        if self.require_capitalized_multi_token and len(alpha_tokens) > 1:
            has_capitalized = any(token[0].isupper() for token in alpha_tokens if token)
            if not has_capitalized:
                return (False, "multi_token_not_capitalized")

        # Reject all-lowercase short phrases made only of stopword-like tokens.
        if (
            all(token.islower() for token in alpha_tokens)
            and all(token.lower() in self.STOPWORD_LIKE_TOKENS for token in alpha_tokens)
        ):
            return (False, "stopword_like_phrase")

        return (True, "accepted")

    def _is_geocoding_candidate(self, entity: GeoEntity, min_confidence: float | None = None) -> bool:
        """Return whether an entity is worth geocoding.

        Filters low-signal candidates that commonly produce API noise and
        false positives during live geocoding.
        """
        is_candidate, _reason = self._geocoding_candidate_decision(entity, min_confidence)
        return is_candidate

    def _section_priority_boost(self, section: str) -> float:
        """Bias geocoding toward sections likely containing study sites."""
        section_lower = section.lower()
        if "study" in section_lower or "method" in section_lower:
            return 0.2
        if "abstract" in section_lower or "results" in section_lower:
            return 0.1
        return 0.0

    def geocode_entities(
        self,
        entities: list[GeoEntity],
        bias_point: Point | None = None,
        *,
        max_candidates: int | None = None,
        min_confidence: float | None = None,
    ) -> list[GeoEntity]:
        """Geocode multiple entities, updating their coordinates.

        Args:
            entities: List of entities to geocode
            bias_point: Optional geographic bias
            max_candidates: Maximum unique location names to geocode per document
            min_confidence: Minimum confidence required before geocoding

        Returns:
            List of entities (some with updated coordinates)
        """
        from pydantic import ValidationError

        updated_entities = list(entities)
        stats = Counter[str]()
        stats["entities_total"] = len(entities)
        stats["entities_already_with_coordinates"] = sum(
            1 for e in entities if e.coordinates is not None
        )

        document_bias = self._compute_document_bias_point(entities, bias_point)
        country_hints = self._infer_country_hints(entities, document_bias)
        effective_max_candidates = (
            self.max_candidates_per_doc if max_candidates is None else max_candidates
        )
        effective_min_confidence = (
            self.min_candidate_confidence if min_confidence is None else min_confidence
        )

        candidate_groups: dict[str, list[int]] = {}
        for idx, entity in enumerate(entities):
            is_candidate, rejection_reason = self._geocoding_candidate_decision(
                entity,
                min_confidence=effective_min_confidence,
            )
            if not is_candidate:
                stats[f"candidate_reject_{rejection_reason}"] += 1
                continue
            normalized_key = GeocodingCache._normalise_location_name(entity.text)
            candidate_groups.setdefault(normalized_key, []).append(idx)

        stats["candidate_mentions_accepted"] = sum(len(v) for v in candidate_groups.values())
        stats["unique_candidates_total"] = len(candidate_groups)

        if not candidate_groups:
            stats["unique_candidates_budgeted"] = 0
            stats["unique_candidates_skipped_budget"] = 0
            stats["unique_candidates_attempted"] = 0
            stats["unique_candidates_geocoded"] = 0
            stats["mentions_resolved"] = 0
            stats["mentions_with_coordinates_after_geocoding"] = sum(
                1 for e in updated_entities if e.coordinates is not None
            )
            self._last_document_stats = dict(stats)
            return updated_entities

        def _group_priority(indexes: list[int]) -> tuple[float, int, int]:
            representative = max(
                indexes,
                key=lambda i: (
                    entities[i].confidence + self._section_priority_boost(entities[i].section),
                    len(entities[i].text),
                ),
            )
            representative_entity = entities[representative]
            score = representative_entity.confidence + self._section_priority_boost(
                representative_entity.section,
            )
            score += self._name_quality_score(representative_entity.text)
            mention_count = len(indexes)
            return (score, mention_count, len(representative_entity.text))

        ranked_groups = sorted(
            candidate_groups.values(),
            key=_group_priority,
            reverse=True,
        )

        total_unique_candidates = len(ranked_groups)
        groups_to_geocode = ranked_groups[:effective_max_candidates]
        skipped_candidates = total_unique_candidates - len(groups_to_geocode)
        stats["unique_candidates_budgeted"] = len(groups_to_geocode)
        stats["unique_candidates_skipped_budget"] = skipped_candidates

        if skipped_candidates > 0:
            logger.info(
                "Geocoding candidate budget applied: %s/%s unique names will be geocoded",
                len(groups_to_geocode),
                total_unique_candidates,
            )

        geocoded_count = 0
        rate_limited_failures = 0

        for indexes in groups_to_geocode:
            stats["unique_candidates_attempted"] += 1
            representative_index = max(
                indexes,
                key=lambda i: (
                    entities[i].confidence + self._section_priority_boost(entities[i].section),
                    len(entities[i].text),
                ),
            )
            representative = entities[representative_index]
            effective_bias = document_bias if document_bias is not None else bias_point
            effective_bias = self._resolve_bias_for_entity(
                representative,
                default_bias=effective_bias,
                country_hints=country_hints,
            )
            feature_hint = self._infer_feature_hint(representative)
            coords = self.geocode(
                representative.text,
                bias_point=effective_bias,
                country_hints=country_hints,
                feature_hint=feature_hint,
            )

            if coords is None:
                if self._last_error_was_rate_limit:
                    stats["geocode_fail_provider_rate_limited"] += 1
                    rate_limited_failures += 1
                    if rate_limited_failures >= 3:
                        logger.warning(
                            "Stopping geocoding early after repeated 429 responses",
                        )
                        break
                else:
                    failure_reason = self._last_geocode_failure_reason or "not_found"
                    stats[f"geocode_fail_{failure_reason}"] += 1
                continue

            if not self._passes_distance_guard(
                coords,
                document_bias=document_bias,
                per_candidate_bias=effective_bias,
            ):
                stats["geocode_reject_distance_guard"] += 1
                logger.info(
                    "Rejected geocode for %s due to distance guard: %s",
                    representative.text,
                    coords,
                )
                continue

            rate_limited_failures = 0
            geocoded_count += 1
            stats["unique_candidates_geocoded"] += 1
            stats["mentions_resolved"] += len(indexes)

            for entity_index in indexes:
                source_entity = updated_entities[entity_index]
                try:
                    updated_entities[entity_index] = GeoEntity(
                        text=source_entity.text,
                        entity_type=source_entity.entity_type,
                        context=source_entity.context,
                        section=source_entity.section,
                        confidence=min(source_entity.confidence + 0.1, 1.0),
                        start_char=source_entity.start_char,
                        end_char=source_entity.end_char,
                        coordinates=coords,
                        bounding_box=source_entity.bounding_box,
                    )
                except ValidationError as e:
                    logger.warning(f"Failed to create geocoded entity: {e}")

        logger.info(
            "Geocoding summary: resolved %s/%s unique candidates",
            geocoded_count,
            len(groups_to_geocode),
        )

        stats["mentions_with_coordinates_after_geocoding"] = sum(
            1 for e in updated_entities if e.coordinates is not None
        )
        self._last_document_stats = dict(stats)
        logger.info("Geocoding telemetry: %s", self._last_document_stats)

        return updated_entities

    def get_last_document_stats(self) -> dict[str, int]:
        """Return geocoding telemetry from the most recent document run."""
        return dict(self._last_document_stats)

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

    def export_cache_entries(self) -> dict[str, list[float] | None]:
        """Return cache entries in a JSON-serializable form."""
        return {
            key: [float(coords[0]), float(coords[1])] if coords is not None else None
            for key, coords in self.cache._cache.items()
        }

    def import_cache_entries(self, entries: Mapping[str, object]) -> int:
        """Load cache entries from a serialized mapping.

        Args:
            entries: Mapping of cache key to ``[lat, lon]`` or ``None``

        Returns:
            Number of entries successfully loaded
        """
        loaded = 0
        for key, value in entries.items():
            if value is None:
                self.cache._cache[key] = None
                loaded += 1
                continue

            if not isinstance(value, list | tuple) or len(value) != 2:
                continue

            try:
                lat = float(value[0])
                lon = float(value[1])
            except (TypeError, ValueError):
                continue

            self.cache._cache[key] = (lat, lon)
            loaded += 1

        return loaded


# Global geocoder instance (singleton pattern)
_geocoder: CachedGeocoder | None = None


def get_geocoder() -> CachedGeocoder:
    """Get global geocoder instance."""
    global _geocoder
    if _geocoder is None:
        _geocoder = CachedGeocoder(
            rate_limit=settings.GEOCODING_RATE_LIMIT,
            allow_live_requests=settings.GEOCODING_ALLOW_LIVE_REQUESTS,
            max_candidates_per_doc=settings.GEOCODING_MAX_CANDIDATES_PER_DOC,
            min_candidate_confidence=settings.GEOCODING_MIN_CANDIDATE_CONFIDENCE,
            strict_other_section_min_confidence=(
                settings.GEOCODING_STRICT_OTHER_SECTION_MIN_CONFIDENCE
            ),
            reject_determiner_prefix=settings.GEOCODING_REJECT_DETERMINER_PREFIX,
            reject_non_location_content=settings.GEOCODING_REJECT_NON_LOCATION_CONTENT,
            require_capitalized_multi_token=(
                settings.GEOCODING_REQUIRE_CAPITALIZED_MULTI_TOKEN
            ),
            max_distance_without_bias_km=settings.GEOCODING_MAX_DISTANCE_WITHOUT_BIAS_KM,
            max_distance_with_bias_km=settings.GEOCODING_MAX_DISTANCE_WITH_BIAS_KM,
            max_distance_per_candidate_km=settings.GEOCODING_MAX_DISTANCE_PER_CANDIDATE_KM,
            strict_low_signal_section_min_confidence=(
                settings.GEOCODING_STRICT_LOW_SIGNAL_SECTION_MIN_CONFIDENCE
            ),
            require_context_cue_for_low_signal_section=(
                settings.GEOCODING_REQUIRE_CONTEXT_CUE_FOR_LOW_SIGNAL_SECTION
            ),
            min_top_candidate_score=settings.GEOCODING_MIN_TOP_CANDIDATE_SCORE,
            ambiguity_score_margin=settings.GEOCODING_AMBIGUITY_SCORE_MARGIN,
            ambiguity_distance_km=settings.GEOCODING_AMBIGUITY_DISTANCE_KM,
        )
    return _geocoder
