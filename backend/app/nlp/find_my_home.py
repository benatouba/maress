"""Study site extraction with priority-based ranking."""

from __future__ import annotations

import re
import time
from enum import IntEnum
from pathlib import Path
from typing import TYPE_CHECKING, final

import numpy as np
import spacy
from geopy.geocoders import Nominatim
from geopy.point import Point
from pydantic import BaseModel, Field
from pydantic_extra_types.coordinate import Coordinate, Latitude, Longitude
from rich import print as rprint
from sklearn.cluster import DBSCAN
from sklearn.neighbors import NearestNeighbors
from spacy.matcher import Matcher, PhraseMatcher

from app.core.config import settings
from app.nlp.nlp_logger import logger
from app.nlp.pdf_text_extractor import PyPDFTextExtractor

# Import your existing types and modules
from maress_types import CoordinateExtractionMethod, CoordinateSourceType, PaperSections

if TYPE_CHECKING:
    from re import Match

    from geopy.location import Location as GeopyLocation
    from spacy.language import Language
    from spacy.tokens import Doc, Span

import pandas as pd

# Use your existing geo_phrases
geo_phrases = [
    "coordinates",
    "department of",
    "coordinates of",
    "epsg",
    "experimental site",
    "field location",
    "field site",
    "geographic coordinates",
    "GPS coordinates",
    "latitude",
    "located at",
    "located in",
    "longitude",
    "monitoring site",
    "observation site",
    "province of",
    "research site",
    "sampling location",
    "sampling site",
    "site coordinates",
    "site description",
    "site is",
    "study area",
    "study coordinates",
    "study location",
    "study site",
    "the region of",
    "utm",
    "conducted fieldwork in",
    "wgs84",
]

# Use your existing coordinate patterns
coordinate_patterns = {
    "decimal_degrees_with_hemisphere": r"""
        (?x)
        (
            # Decimal degrees with mandatory hemisphere letter
            -?\d{1,3}\.\d+\s*[NSEW]
            |
            # Degrees Minutes Seconds with mandatory hemisphere
            \d{1,3}°\s*\d{1,2}'\s*\d{1,2}(?:\.\d+)?\"\s*[NSEW]
            |
            # Degrees and decimal minutes with hemisphere
            \d{1,3}°\s*\d{1,2}(?:\.\d+)'\s*[NSEW]
        )
    """,
    "lat_lon_pair": r"""
        (?x)
        # Latitude/Longitude pair patterns
        (
            # Pattern: lat, lon or (lat, lon)
            (?:latitude|lat)\s*[=:]?\s*(-?\d{1,3}\.\d+)\s*[,;]?\s*
            (?:longitude|lon|long)\s*[=:]?\s*(-?\d{1,3}\.\d+)
            |
            # Pattern: (lat°, lon°)
            \(\s*(-?\d{1,3}\.\d+)°?\s*[,;]\s*(-?\d{1,3}\.\d+)°?\s*\)
            |
            # Pattern: lat°N, lon°W
            (-?\d{1,3}\.\d+)°?\s*[NS]\s*[,;]?\s*(-?\d{1,3}\.\d+)°?\s*[EW]
        )
    """,
}

# Compile regex for quick checks
coord_re_list = [
    re.compile(
        coordinate_patterns["decimal_degrees_with_hemisphere"],
        re.IGNORECASE | re.VERBOSE,
    ),
    re.compile(coordinate_patterns["lat_lon_pair"], re.IGNORECASE | re.VERBOSE),
]


# Priority levels for extraction methods
class ExtractionPriority(IntEnum):
    """Priority levels for different extraction methods (higher = better)."""

    REGEX_COORDINATES = 100  # Highest priority
    SPACY_TEXT_HIGH_CONFIDENCE = 80
    SPACY_TEXT_MEDIUM_CONFIDENCE = 60
    TABLE_COORDINATES = 50
    SPACY_TEXT_LOW_CONFIDENCE = 40
    GEOCODED_LOCATIONS = 30


class CoordinateCandidate(BaseModel):
    """Coordinate candidate with priority-based scoring."""

    latitude: Latitude  # validates -90 <= value <= 90
    longitude: Longitude  # validates -180 <= value <= 180
    confidence_score: float = Field(ge=0.0, le=1.0)
    priority_score: int = Field(description="Priority level from ExtractionPriority")
    source_type: CoordinateSourceType = Field(
        description="Source type of the coordinate extraction",
    )
    context: str = Field(description="Context around the coordinate in the text")
    section: PaperSections = Field(description="Document section where Coordinate was found")
    name: str = Field(default="Unknown", description="Optional name associated with the coordinate")
    extraction_method: CoordinateExtractionMethod
    cluster_label: int | None = Field(
        default=None, description="Cluster ID from DBSCAN (-1 for noise)"
    )

    @property
    def final_score(self) -> float:
        """Combined score for ranking (priority + confidence)."""
        return self.priority_score + self.confidence_score


class LocationCandidate(BaseModel):
    """Location candidate with priority scoring."""

    name: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    priority_score: int = Field(description="Priority level from ExtractionPriority")
    source_type: CoordinateSourceType
    context: str
    section: PaperSections
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    coordinates: Coordinate | None = None

    @property
    def final_score(self) -> float:
        """Combined score for ranking (priority + confidence)."""
        return self.priority_score + self.confidence_score


class StudySiteResult(BaseModel):
    """Result with priority-ranked candidates."""

    coordinates: list[CoordinateCandidate] = Field(default_factory=list)
    locations: list[LocationCandidate] = Field(default_factory=list)
    validation_score: float = 0.0
    primary_study_site: CoordinateCandidate | None = None
    cluster_info: dict[str, int] = Field(default_factory=dict)


class LocationExtractor:
    """Optimised location extractor focused on geographic entities."""

    def __init__(self, model_name: str = settings.SPACY_MODEL):
        # Load spaCy with only components needed for geographic extraction
        try:
            self.nlp: Language = spacy.load(
                model_name,
                disable=["textcat"],  # Keep lemmatizer for LEMMA-based patterns
            )
        except OSError:
            logger.error(f"spaCy model {model_name} not found")
            raise

        # Optimise pipeline for geographic entities only
        if "ner" in self.nlp.pipe_names:
            # Filter NER to only geographic labels during processing
            self.geo_labels = {"GPE", "LOC", "FAC", "NORP"}

        # Enhanced matchers for geographic context
        self.matcher = Matcher(self.nlp.vocab)
        self.phrase_matcher = PhraseMatcher(self.nlp.vocab, attr="LOWER")

        # Add sophisticated geographic patterns
        self._setup_geographic_patterns()

        # Enhanced geocoder with better error handling
        self.geocoder = Nominatim(
            user_agent="study_site_extractor",
            timeout=15,
        )

        # Geocoding cache and rate limiting
        self._geocode_cache: dict[str, tuple[float, float] | None] = {}
        self._last_geocode_time: float = 0.0

    def _setup_geographic_patterns(self):
        """Set up enhanced patterns for geographic context detection."""
        # High-confidence geographic phrases
        high_confidence_phrases = [
            "study site",
            "study area",
            "field site",
            "sampling site",
            "research site",
            "experimental site",
            "monitoring site",
            "study location",
            "field location",
            "sampling location",
        ]

        # Medium-confidence geographic phrases
        medium_confidence_phrases = [
            "coordinates",
            "latitude",
            "longitude",
            "GPS coordinates",
            "geographic coordinates",
            "site coordinates",
            "located at",
            "located in",
            "situated in",
            "positioned at",
        ]

        # Low-confidence geographic phrases
        low_confidence_phrases = [
            "region of",
            "province of",
            "department of",
            "area of",
            "vicinity of",
            "near",
            "close to",
            "adjacent to",
        ]

        # Add phrase patterns with different confidence levels
        self.phrase_matcher.add(
            "HIGH_CONF_GEO",
            [self.nlp.make_doc(phrase) for phrase in high_confidence_phrases],
        )
        self.phrase_matcher.add(
            "MED_CONF_GEO",
            [self.nlp.make_doc(phrase) for phrase in medium_confidence_phrases],
        )
        self.phrase_matcher.add(
            "LOW_CONF_GEO",
            [self.nlp.make_doc(phrase) for phrase in low_confidence_phrases],
        )

        # Use TEXT attribute instead of LEMMA to avoid lemmatizer dependency
        self.matcher.add(
            "LOCATION_VERBS",
            [
                [
                    {
                        "TEXT": {
                            "IN": ["located", "situated", "positioned", "established"],
                        },
                    },
                ],
                [{"TEXT": "conducted"}, {"LOWER": {"IN": ["in", "at", "near"]}}],
                [
                    {"TEXT": "carried"},
                    {"TEXT": "out"},
                    {"LOWER": {"IN": ["in", "at", "near"]}},
                ],
            ],
        )

    def calculate_spacy_confidence(
        self,
        entity: Span,
        context: str,
    ) -> tuple[float, int]:
        """Calculate confidence and priority for spaCy entities with
        heuristics."""
        confidence = 0.5  # Base confidence for spaCy NER
        context_lower = context.lower()

        # Process context with full pipeline for matcher
        doc = self.nlp(context)
        matches = self.phrase_matcher(doc)

        priority = ExtractionPriority.SPACY_TEXT_LOW_CONFIDENCE

        for match_id, _, _ in matches:
            match_label = self.nlp.vocab.strings[match_id]
            if match_label == "HIGH_CONF_GEO":
                confidence += 0.3
                priority = ExtractionPriority.SPACY_TEXT_HIGH_CONFIDENCE
            elif match_label == "MED_CONF_GEO":
                confidence += 0.2
                priority = ExtractionPriority.SPACY_TEXT_MEDIUM_CONFIDENCE
            elif match_label == "LOW_CONF_GEO":
                confidence += 0.1

        # Check for verb patterns - use simple string matching as fallback
        verb_indicators = [
            "located",
            "situated",
            "positioned",
            "established",
            "conducted",
        ]
        if any(verb in context_lower for verb in verb_indicators):
            confidence += 0.15
            if priority == ExtractionPriority.SPACY_TEXT_LOW_CONFIDENCE:
                priority = ExtractionPriority.SPACY_TEXT_MEDIUM_CONFIDENCE

        # Boost confidence for certain entity types and characteristics
        if entity.label_ == "GPE":
            confidence += 0.1
        elif entity.label_ == "LOC":
            confidence += 0.15  # LOC often more specific for study sites

        # Length-based confidence (longer names often more specific)
        if len(entity.text.split()) >= 2:
            confidence += 0.1

        # Capitalisation check (proper nouns)
        if entity.text[0].isupper() and not entity.text.isupper():
            confidence += 0.05

        # Section-based boosting
        section_indicators = [
            "methods",
            "methodology",
            "study area",
            "site description",
            "materials and methods",
            "field work",
            "data collection",
        ]
        if any(indicator in context_lower for indicator in section_indicators):
            confidence += 0.2
            priority = max(priority, ExtractionPriority.SPACY_TEXT_MEDIUM_CONFIDENCE)

        return min(confidence, 1.0), priority

    def extract_locations(
        self,
        text: str,
        section: PaperSections,
    ) -> list[LocationCandidate]:
        """Extract named locations with enhanced confidence scoring."""
        # Process with full pipeline (need lemmatizer for patterns)
        doc = self.nlp(text)
        print(f"text analysed for section {section}\n")
        print("Sentences found:")
        rprint([sent.text for sent in doc.sents])

        candidates: list[LocationCandidate] = []

        for ent in doc.ents:
            # Only process geographic entities
            if ent.label_ not in self.geo_labels:
                continue

            # Filter out very short or non-alphabetic entities
            clean_text = re.sub(r"[^\w\s]", "", ent.text).strip()
            if len(clean_text) < 2 or not any(c.isalpha() for c in clean_text):
                continue

            # Get enhanced context
            context = self._get_context(doc, ent)
            confidence, priority = self.calculate_spacy_confidence(ent, context)

            candidates.append(
                LocationCandidate(
                    name=ent.text,
                    confidence_score=confidence,
                    priority_score=priority,
                    source_type=CoordinateSourceType.TEXT,
                    context=context,
                    section=section,
                ),
            )

        return candidates

    def geocode_with_bias(
        self,
        locations: list[LocationCandidate],
        bias_point: Point | None = None,
    ) -> list[LocationCandidate]:
        """Geocoding with geographic bias, caching, and rate limiting."""
        for location in locations:
            # Create cache key from location name and bias point
            cache_key = f"{location.name}_{bias_point.latitude if bias_point else 'none'}_{bias_point.longitude if bias_point else 'none'}"

            # Check cache first
            if cache_key in self._geocode_cache:
                cached_coords = self._geocode_cache[cache_key]
                if cached_coords:
                    location.coordinates = Coordinate(
                        Latitude(cached_coords[0]),
                        Longitude(cached_coords[1]),
                    )
                    location.confidence_score = min(
                        location.confidence_score + 0.1,
                        1.0,
                    )
                    logger.info(f"Using cached geocode for {location.name}: {location.coordinates}")
                else:
                    logger.info(f"Skipping {location.name} (cached as not found)")
                continue

            # Rate limiting: ensure minimum time between requests (Nominatim requires 1 req/sec)
            elapsed = time.time() - self._last_geocode_time
            if elapsed < settings.GEOCODING_RATE_LIMIT:
                sleep_time = settings.GEOCODING_RATE_LIMIT - elapsed
                logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
                time.sleep(sleep_time)

            try:
                # Use bias point if available
                geocoded: GeopyLocation | None = None

                if bias_point:
                    delta = 4.5  # approximately 500km
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
                        location.name,
                        viewbox=viewbox,
                        bounded=True,
                        timeout=10,
                    )

                # Fallback to unbounded search
                if not geocoded:
                    geocoded = self.geocoder.geocode(location.name, timeout=10)

                # Update last geocode time after request
                self._last_geocode_time = time.time()

                if geocoded:
                    # Cache the result
                    self._geocode_cache[cache_key] = (geocoded.latitude, geocoded.longitude)

                    location.coordinates = Coordinate(
                        Latitude(geocoded.latitude),
                        Longitude(geocoded.longitude),
                    )
                    # Boost confidence for successfully geocoded locations
                    location.confidence_score = min(
                        location.confidence_score + 0.1,
                        1.0,
                    )
                    logger.info(f"Geocoded {location.name}: {location.coordinates}")
                else:
                    # Cache negative result to avoid repeated failed lookups
                    self._geocode_cache[cache_key] = None
                    logger.info(f"Could not geocode {location.name}")

            except Exception as e:
                logger.warning(f"Failed to geocode {location.name}: {e}")
                # Cache failure to avoid retrying
                self._geocode_cache[cache_key] = None

        return locations

    def _get_context(self, doc: Doc, ent: Span, window: int = 75) -> str:
        """Get enhanced context with sentence boundaries."""
        # Try to get full sentences containing the entity
        sent = ent.sent
        context_sents = [sent]

        # Add previous and next sentences if available
        sent_list = list(doc.sents)
        sent_idx = sent_list.index(sent)

        if sent_idx > 0:
            context_sents.insert(0, sent_list[sent_idx - 1])
        if sent_idx < len(sent_list) - 1:
            context_sents.append(sent_list[sent_idx + 1])

        full_context = " ".join([s.text for s in context_sents])

        # Fallback to token-based window if sentences are too long
        if len(full_context) > 400:
            start_token = max(0, ent.start - window)
            end_token = min(len(doc), ent.end + window)
            full_context = doc[start_token:end_token].text

        return full_context.strip()


class CoordinateExtractor:
    """Coordinate extraction with priority scoring."""

    def __init__(self):
        self.coordinate_patterns = coordinate_patterns
        self.coord_re_list = coord_re_list
        self.study_site_keywords = geo_phrases

    def extract_coordinates_from_text(
        self,
        text: str,
        section: PaperSections,
    ) -> list[CoordinateCandidate]:
        """Extract coordinates with highest priority scoring."""
        candidates = []

        for pattern_name, pattern in self.coordinate_patterns.items():
            matches = re.finditer(pattern, text, re.IGNORECASE | re.VERBOSE)

            for match in matches:
                context = self._get_context(text, match.start(), match.end())

                # Parse coordinates
                coords = self._parse_coordinate_match(match, pattern_name)
                if coords:
                    # Regex coordinates get highest priority and confidence
                    confidence = self._calculate_regex_confidence(
                        context,
                        match.group(),
                    )

                    candidates.append(
                        CoordinateCandidate(
                            latitude=coords[0],
                            longitude=coords[1],
                            confidence_score=confidence,
                            priority_score=ExtractionPriority.REGEX_COORDINATES,
                            source_type=CoordinateSourceType.TEXT,
                            context=context,
                            section=PaperSections(section),
                            name=None,
                            extraction_method=CoordinateExtractionMethod.REGEX,
                        ),
                    )

        return candidates

    def extract_coordinates_from_tables(
        self,
        tables: list[pd.DataFrame],
    ) -> list[CoordinateCandidate]:
        """Extract coordinates from table data with table priority."""
        candidates = []

        for i, table in enumerate(tables, 1):
            lat_cols = self._find_coordinate_columns(table, ["lat", "latitude", "y"])
            lon_cols = self._find_coordinate_columns(
                table,
                ["lon", "longitude", "long", "x"],
            )

            if lat_cols and lon_cols:
                lat_col = lat_cols[0]
                lon_col = lon_cols[0]

                logger.info(
                    f"Table {i}: Found coordinate columns - lat: {lat_col}, lon: {lon_col}",
                )

                for idx, row in table.iterrows():
                    try:
                        # Clean coordinate values
                        lat_val = str(row[lat_col]).replace("°", "").strip()
                        lon_val = str(row[lon_col]).replace("°", "").strip()

                        # Skip empty or non-numeric values
                        if not lat_val or not lon_val or lat_val == "nan" or lon_val == "nan":
                            continue

                        lat = Latitude(float(lat_val))
                        lon = Longitude(float(lon_val))

                        if self._is_valid_coordinate(lat, lon):
                            # Extract name from table if available
                            name_col = self._find_coordinate_columns(
                                table,
                                ["name", "site", "location", "station", "plot"],
                            )
                            name = (
                                str(row[name_col[0]])
                                if name_col
                                else row.get("name") or row.get("site") or f"Table_{idx}_Row_{row}"
                            )

                            candidates.append(
                                CoordinateCandidate(
                                    latitude=lat,
                                    longitude=lon,
                                    confidence_score=0.9,  # High confidence for table data
                                    priority_score=ExtractionPriority.TABLE_COORDINATES,
                                    source_type=CoordinateSourceType.TABLE,
                                    context=f"Table {i}, Row {idx}: {row.to_string()[:200]}",
                                    section=PaperSections.METHODS,  # Tables usually in methods
                                    name=name,
                                    extraction_method=CoordinateExtractionMethod.TABLE_PARSING,
                                ),
                            )
                            logger.debug(f"Extracted coordinate from table: {lat}, {lon}")

                    except (ValueError, TypeError) as e:
                        logger.debug(f"Failed to parse table row {idx}: {e}")
                        continue

        return candidates

    def _find_coordinate_columns(
        self,
        df: pd.DataFrame,
        keywords: list[str],
    ) -> list[str]:
        """Find columns that likely contain coordinates."""
        matching_cols = []
        for col in df.columns:
            col_str = str(col).lower()
            if any(keyword in col_str for keyword in keywords):
                matching_cols.append(col)
        return matching_cols

    def _parse_coordinate_match(
        self,
        match: Match[str],
        pattern_name: str,
    ) -> tuple[Latitude, Longitude] | None:
        """Parse regex match to extract latitude/longitude."""
        if pattern_name == "lat_lon_pair":
            groups = match.groups()
            # Find non-None groups for lat/lon pairs
            non_none_groups = [g for g in groups if g is not None]
            if len(non_none_groups) >= 2:
                try:
                    lat = Latitude(non_none_groups[0])
                    lon = Longitude(non_none_groups[1])
                    if self._is_valid_coordinate(lat, lon):
                        return (lat, lon)
                except ValueError:
                    pass
        return None

    def _get_context(self, text: str, start: int, end: int, window: int = 100) -> str:
        """Get context around a match."""
        context_start = max(0, start - window)
        context_end = min(len(text), end + window)
        full_context = text[context_start:context_end].strip()
        # strip before and after full stop punctuation
        full_context = re.sub(r"^[^a-zA-Z0-9]+", "", full_context)
        return re.sub(r"[^a-zA-Z0-9]+$", "", full_context)

    def _calculate_regex_confidence(self, context: str, match: str) -> float:
        """Calculate confidence for regex-matched coordinates."""
        confidence = 0.8  # High base confidence for regex matches

        context_lower = context.lower()

        # Boost for explicit coordinate indicators
        coordinate_indicators = [
            "coordinates",
            "lat",
            "lon",
            "latitude",
            "longitude",
            "°",
            "′",
            "″",
            "GPS",
            "WGS84",
            "UTM",
            "EPSG",
        ]

        for indicator in coordinate_indicators:
            if indicator in context_lower or indicator in match:
                confidence += 0.05

        # Boost for study site context
        for keyword in self.study_site_keywords:
            if keyword in context_lower:
                confidence += 0.02  # Small boost per keyword

        return min(confidence, 1.0)

    def _is_valid_coordinate(self, lat: float, lon: float) -> bool:
        """Validate coordinate ranges."""
        min_lat, max_lat = -90, 90
        min_lon, max_lon = -180, 180
        return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon


class CoordinateClusterer:
    """Clustering that preserves multiple study sites."""

    def __init__(self, eps_km: float = 50.0, min_samples: int = 1):
        self.eps_km = eps_km
        self.min_samples = min_samples

    def cluster_coordinates(
        self,
        candidates: list[CoordinateCandidate],
    ) -> tuple[list[CoordinateCandidate], dict[str, int]]:
        """Cluster coordinates and return ALL clusters with metadata.

        Returns:
            Tuple of (all candidates with cluster labels, cluster size info)
        """
        if len(candidates) <= 1:
            # No clustering needed for single candidate
            if candidates:
                candidates[0].cluster_label = 0
            return candidates, {0: len(candidates)} if candidates else {}

        # Extract coordinates for clustering
        coords = [(float(c.latitude), float(c.longitude)) for c in candidates]
        X = np.radians(np.array(coords))

        # Adaptive eps based on data distribution
        if len(coords) >= 3:
            self.eps_km = self.estimate_optimal_eps(coords)

        earth_radius_km = 6371.0088
        eps_rad = self.eps_km / earth_radius_km

        # Perform clustering
        clustering: DBSCAN = DBSCAN(
            eps=eps_rad,
            min_samples=self.min_samples,
            metric="haversine",
        ).fit(X)

        # Get cluster labels
        labels = clustering.labels_

        # Group candidates by cluster and assign cluster labels
        clustered: dict[int, list[CoordinateCandidate]] = {}
        for label, candidate in zip(labels, candidates, strict=False):
            # Assign cluster label to candidate
            candidate.cluster_label = int(label)

            if label not in clustered:
                clustered[label] = []
            clustered[label].append(candidate)

        logger.info(f"DBSCAN found {len(clustered)} clusters with eps={self.eps_km:.1f} km")

        # Return ALL clusters, sorted by size (largest first)
        if not clustered:
            return [], {}

        # Sort clusters by size (descending)
        sorted_cluster_labels = sorted(
            clustered.keys(),
            key=lambda k: len(clustered[k]),
            reverse=True,
        )

        # Combine all candidates from all clusters (sorted by cluster size)
        all_candidates_ranked = []
        cluster_info = {}

        for cluster_label in sorted_cluster_labels:
            cluster = clustered[cluster_label]
            cluster_info[f"cluster_{cluster_label}"] = len(cluster)

            # Sort candidates within cluster by final_score
            cluster_sorted = sorted(cluster, key=lambda x: x.final_score, reverse=True)
            all_candidates_ranked.extend(cluster_sorted)

            logger.info(
                f"Cluster {cluster_label}: {len(cluster)} candidates "
                f"(top score: {cluster_sorted[0].final_score:.1f})",
            )

        logger.info(
            f"Returning {len(all_candidates_ranked)} candidates from {len(clustered)} clusters",
        )

        return all_candidates_ranked, cluster_info

    def estimate_optimal_eps(self, coordinates: list[tuple[float, float]]) -> float:
        """Estimate optimal eps based on k-distance plot heuristic."""
        if len(coordinates) < 3:
            return 50.0  # Default

        X = np.radians(np.array(coordinates))
        k = min(3, len(coordinates) - 1)  # Use k=3 or less if not enough points

        nbrs: NearestNeighbors = NearestNeighbors(
            n_neighbors=k + 1,
            metric="haversine",
        ).fit(X)
        distances, _ = nbrs.kneighbors(X)

        # Convert to km and take k-th nearest neighbour distances
        earth_radius_km = 6371.0088
        k_distances = np.sort(distances[:, k] * earth_radius_km)

        # Use knee point detection or percentile-based heuristic
        # Simple heuristic: use 90th percentile
        optimal_eps = np.percentile(k_distances, 90)

        # Bound the eps to reasonable values for study sites
        optimal_eps = max(10.0, min(optimal_eps, 200.0))

        logger.info(f"Estimated optimal eps: {optimal_eps:.1f} km")
        return optimal_eps


class StudySiteValidator:
    """Validator with priority-aware ranking."""

    def validate_study_sites(
        self,
        result: StudySiteResult,
    ) -> StudySiteResult:
        """Validate and rank study site candidates by priority and
        confidence."""
        # Combine coordinates and geocoded locations
        all_candidates = result.coordinates[:]

        for location in result.locations:
            if location.coordinates:
                coord_candidate = CoordinateCandidate(
                    latitude=location.coordinates.latitude,
                    longitude=location.coordinates.longitude,
                    confidence_score=location.confidence_score,
                    priority_score=ExtractionPriority.GEOCODED_LOCATIONS,
                    source_type=location.source_type,
                    context=location.context,
                    section=location.section,
                    name=location.name,
                    extraction_method=CoordinateExtractionMethod.GEOCODED,
                )
                all_candidates.append(coord_candidate)

        # Remove duplicates and rank by final score
        unique_candidates = self._remove_duplicate_coordinates(all_candidates)
        ranked_candidates = sorted(
            unique_candidates,
            key=lambda x: x.final_score,
            reverse=True,
        )

        # Set primary study site (highest final score)
        primary_site = ranked_candidates[0] if ranked_candidates else None

        # Calculate overall validation score
        validation_score = self._calculate_validation_score(ranked_candidates)

        result.coordinates = ranked_candidates
        result.primary_study_site = primary_site
        result.validation_score = validation_score

        return result

    def _remove_duplicate_coordinates(
        self,
        candidates: list[CoordinateCandidate],
        threshold: float = 0.01,
    ) -> list[CoordinateCandidate]:
        """Remove duplicate coordinates within threshold distance."""
        unique_candidates: list[CoordinateCandidate] = []

        for candidate in candidates:
            is_duplicate = False
            for unique in unique_candidates:
                if (
                    abs(float(candidate.latitude) - float(unique.latitude)) < threshold
                    and abs(float(candidate.longitude) - float(unique.longitude)) < threshold
                ):
                    # Keep the one with higher final score
                    if candidate.final_score > unique.final_score:
                        unique_candidates.remove(unique)
                        unique_candidates.append(candidate)
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique_candidates.append(candidate)

        return unique_candidates

    def _calculate_validation_score(
        self,
        candidates: list[CoordinateCandidate],
    ) -> float:
        """Calculate overall validation score for the extraction."""
        if not candidates:
            return 0.0

        # Weight by final score and number of sources
        total_score = sum(c.final_score for c in candidates[:5])  # Top 5 candidates
        max_possible_score = ExtractionPriority.REGEX_COORDINATES + 1.0  # Max priority + confidence
        avg_score = total_score / (min(len(candidates), 5) * max_possible_score)

        # Bonus for multiple extraction methods
        extraction_methods = {c.extraction_method for c in candidates}
        method_bonus = len(extraction_methods) * 0.05

        return min(avg_score + method_bonus, 1.0)


@final
class StudySiteExtractor:
    """Main extractor with priority-based ranking and multiple site support."""

    def __init__(self, spacy_model: str = settings.SPACY_MODEL) -> None:
        self.text_extractor = PyPDFTextExtractor()
        self.coordinate_extractor = CoordinateExtractor()
        self.location_extractor = LocationExtractor(spacy_model)
        self.clusterer = CoordinateClusterer(eps_km=75.0)
        self.validator = StudySiteValidator()

    def _parse_table_to_dataframe(self, table_span: Span) -> pd.DataFrame | None:
        """Convert table span to pandas DataFrame.

        Args:
            table_span: spaCy Span object representing a table

        Returns:
            DataFrame with parsed table data, or None if parsing fails
        """
        import pandas as pd

        try:
            # Get table text
            table_text = table_span.text.strip()

            # Split into lines
            lines = [line.strip() for line in table_text.split("\n") if line.strip()]

            if len(lines) < 2:
                logger.debug("Table has fewer than 2 lines, skipping")
                return None

            # Split each line by multiple spaces or tabs
            rows = []
            for line in lines:
                # Split by tabs or multiple spaces (2+)
                row = re.split(r"\t+|\s{2,}", line)
                row = [cell.strip() for cell in row if cell.strip()]
                if row:
                    rows.append(row)

            if not rows or len(rows) < 2:
                return None

            # Use first row as header, rest as data
            header = rows[0]
            data_rows = rows[1:]

            # Ensure all rows have the same length
            max_cols = max(len(header), max(len(row) for row in data_rows))
            header = header + [""] * (max_cols - len(header))
            data_rows = [row + [""] * (max_cols - len(row)) for row in data_rows]

            df = pd.DataFrame(data_rows, columns=header)
            logger.debug(f"Parsed table with {len(df)} rows and {len(df.columns)} columns")

            return df

        except Exception as e:
            logger.warning(f"Failed to parse table: {e}")
            return None

    def extract_study_sites(
        self,
        pdf_path: Path,
        title: str | None = None,
    ) -> StudySiteResult:
        """Extract with proper priority ranking."""
        logger.info(f"Processing PDF: {pdf_path}")
        result = StudySiteResult()

        # 1. Extract title location for geocoding bias
        title_bias_point = None
        if title:
            title_location = self._extract_title_location(title)
            if title_location and title_location.coordinates:
                title_bias_point = Point(
                    latitude=title_location.coordinates.latitude,
                    longitude=title_location.coordinates.longitude,
                )
                result.locations.append(title_location)

        # 2. Extract text and tables
        text_data = self.text_extractor.process_scientific_pdf(pdf_path)
        if not text_data.full_doc:
            logger.warning(f"No text extracted from {pdf_path}")
            return result

        # 3. Priority 1: Extract regex coordinates (highest priority)
        all_candidates: list[CoordinateCandidate] = []
        for section, text in text_data.sections.items():
            regex_coords = self.coordinate_extractor.extract_coordinates_from_text(
                text,
                section=PaperSections(section),
            )
            all_candidates.extend(regex_coords)

        logger.info(f"Found {len(all_candidates)} regex coordinate candidates")

        # 4. Priority 2: Extract spaCy locations from text
        for section, text in text_data.sections.items():
            locations = self.location_extractor.extract_locations(
                text,
                section=PaperSections(section),
            )
            result.locations.extend(locations)

        logger.info(f"Found {len(result.locations)} location candidates from text")

        # 5. Priority 3: Extract coordinates from tables
        if text_data.tables:
            logger.info(f"Processing {len(text_data.tables)} tables for coordinate extraction")

            # Convert table spans to DataFrames
            table_dfs = []
            for table_span in text_data.tables:
                df = self._parse_table_to_dataframe(table_span)
                if df is not None:
                    table_dfs.append(df)

            if table_dfs:
                table_coords = self.coordinate_extractor.extract_coordinates_from_tables(table_dfs)
                all_candidates.extend(table_coords)
                logger.info(f"Found {len(table_coords)} coordinates from tables")
            else:
                logger.info("No tables could be parsed into DataFrames")
        else:
            logger.info("No tables found in document")

        # 6. Priority 4: Geocode locations with bias
        geocoded_locations = self.location_extractor.geocode_with_bias(
            result.locations,
            title_bias_point,
        )

        # Convert geocoded locations to coordinate candidates
        for location in geocoded_locations:
            if location.coordinates:
                coord_candidate = CoordinateCandidate(
                    latitude=location.coordinates.latitude,
                    longitude=location.coordinates.longitude,
                    confidence_score=location.confidence_score,
                    priority_score=ExtractionPriority.GEOCODED_LOCATIONS,
                    source_type=location.source_type,
                    context=location.context,
                    section=location.section,
                    name=location.name,
                    extraction_method=CoordinateExtractionMethod.GEOCODED,
                )
                all_candidates.append(coord_candidate)

        # 7. Cluster coordinates to identify areas
        final_candidates, cluster_info = self.clusterer.cluster_coordinates(all_candidates)

        # 9. Final ranking: all candidates by final score
        result.coordinates = sorted(
            final_candidates,
            key=lambda x: x.final_score,
            reverse=True,
        )

        # Store cluster information
        result.cluster_info = cluster_info

        # 10. Set primary study site (highest scoring overall)
        result.primary_study_site = result.coordinates[0] if result.coordinates else None

        # 11. Calculate validation score
        result.validation_score = self._calculate_validation_score(result.coordinates)

        logger.info("Extraction complete:")
        logger.info(f"  - Total candidates: {len(result.coordinates)}")
        logger.info(f"  - Clusters found: {len(cluster_info)}")
        logger.info(f"  - Validation score: {result.validation_score:.3f}")

        if result.primary_study_site:
            site = result.primary_study_site
            logger.info(
                "Primary site: %.4f, %.4f (score: %.1f, method: %s, cluster: %s)",
                site.latitude,
                site.longitude,
                site.final_score,
                site.extraction_method,
                site.cluster_label,
            )

        return result

    def _extract_title_location(self, title: str) -> LocationCandidate | None:
        """Extract location from paper title for geocoding bias."""
        locations = self.location_extractor.extract_locations(title, section=PaperSections.TITLE)
        if locations:
            # Get the highest confidence title location
            best_location = max(locations, key=lambda x: x.final_score)
            # Try to geocode it
            geocoded = self.location_extractor.geocode_with_bias([best_location])
            if geocoded and geocoded[0].coordinates:
                return geocoded[0]
        return None

    def _calculate_validation_score(
        self,
        candidates: list[CoordinateCandidate],
    ) -> float:
        """Calculate validation score for clustered coordinates."""
        if not candidates:
            return 0.0

        # Base score from candidate quality
        total_score = sum(c.final_score for c in candidates[:5])  # Top 5 candidates
        max_possible_score = ExtractionPriority.REGEX_COORDINATES + 9  # Max priority + confidence
        avg_score = total_score / (min(len(candidates), 5) * max_possible_score)

        # Bonus for extraction method diversity
        extraction_methods = {c.extraction_method for c in candidates}
        diversity_bonus = len(extraction_methods) * 0.05

        # Bonus for having regex coordinates (most reliable)
        regex_bonus = (
            0.1
            if any(c.priority_score == ExtractionPriority.REGEX_COORDINATES for c in candidates)
            else 0.0
        )

        final_score = avg_score + diversity_bonus + regex_bonus
        return min(max(final_score, 0.0), 1.0)


# Usage example
if __name__ == "__main__":
    extractor = StudySiteExtractor()
    pdf_folder = Path.cwd() / "zotero_files"
    pdf_path = next(iter(pdf_folder.glob("*.pdf")))

    if pdf_path.exists():
        # You can also provide a title for better geocoding bias
        title = "Late Holocene eruptive activity at Nevado Cayambe Volcano, Ecuador"
        result = extractor.extract_study_sites(pdf_path, title=title)

        print(f"Validation Score: {result.validation_score:.3f}")
        print(f"Clusters found: {result.cluster_info}")

        print("\nAll candidates (ranked by priority and confidence):")
        for i, candidate in enumerate(result.coordinates[:10], 1):  # Top 10
            print(f"{i:2d}. {candidate.latitude:.4f}, {candidate.longitude:.4f}")
            print(
                f"    Score: {candidate.final_score:.1f} | Priority: {candidate.priority_score}",
            )
            print(
                f"    Method: {candidate.extraction_method} | Context: {candidate.context}",
            )
            print()
    else:
        print(f"PDF file {pdf_path} not found")
