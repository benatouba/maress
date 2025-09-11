"""Extract study site locations from scientific papers in PDF format.

This module uses regex patterns and NLP techniques to identify
geographic coordinates and named locations within the text of scientific
papers. It also includes functionality to validate and rank the
extracted locations.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, final

import numpy as np
import spacy
from geopy.geocoders import Nominatim
from geopy.point import Point
from pydantic import BaseModel, Field
from pydantic_extra_types.coordinate import Coordinate, Latitude, Longitude
from sklearn.cluster import DBSCAN
from sklearn.neighbors import NearestNeighbors
from spacy.matcher import Matcher, PhraseMatcher
from spacy.tokens import Span

from maress_types import CoordinateExtractionMethod, CoordinateSourceType

from .nlp_logger import logger
from .pdf_extractors import CamelotTableExtractor, PyPDFTextExtractor

if TYPE_CHECKING:
    from re import Match

    import numpy.typing as npt
    import pandas as pd
    from geopy.location import Location as GeopyLocation
    from spacy.language import Language

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

coordinate_patterns = {
    "decimal_degrees_with_hemisphere": r"""
        (?x)
        (
            # Decimal degrees with mandatory hemisphere letter
            -?\\d{1,3}\\.\\d+\\s*[NSEW]
            |
            # Degrees Minutes Seconds with mandatory hemisphere
            \\d{1,3}°\\s*\\d{1,2}'\\s*\\d{1,2}(?:\\.\\d+)?\\"\\s*[NSEW]
            |
            # Degrees and decimal minutes with hemisphere
            \\d{1,3}°\\s*\\d{1,2}(?:\\.\\d+)'\\s*[NSEW]
        )
    """,
    "lat_lon_pair": r"""
        (?x)
        # Latitude/Longitude pair patterns
        (
            # Pattern: lat, lon or (lat, lon)
            (?:latitude|lat)\\s*[=:]?\\s*(-?\\d{1,3}\\.\\d+)\\s*[,;]?\\s*
            (?:longitude|lon|long)\\s*[=:]?\\s*(-?\\d{1,3}\\.\\d+)
            |
            # Pattern: (lat°, lon°)
            \\(\\s*(-?\\d{1,3}\\.\\d+)°?\\s*[,;]\\s*(-?\\d{1,3}\\.\\d+)°?\\s*\\)
            |
            # Pattern: lat°N, lon°W
            (-?\\d{1,3}\\.\\d+)°?\\s*[NS]\\s*[,;]?\\s*(-?\\d{1,3}\\.\\d+)°?\\s*[EW]
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


class CoordinateCandidate(BaseModel):
    """Represents a potential coordinate found in the document."""

    latitude: Latitude  # validates -90 <= value <= 90
    longitude: Longitude  # validates -180 <= value <= 180
    confidence_score: float = Field(ge=0.0)
    source_type: CoordinateSourceType = Field(
        description="Source type of the coordinate extraction",
    )
    context: str = Field(description="Context around the coordinate in the text")
    page_number: int = Field(ge=1)
    extraction_method: CoordinateExtractionMethod


class LocationCandidate(BaseModel):
    """Represents a named location that could be geocoded."""

    name: str
    confidence_score: float
    source_type: CoordinateSourceType
    context: str
    page_number: int
    # Optional coordinates, validated as lat/lon if present
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    coordinates: Coordinate | None = None


class StudySiteResult(BaseModel):
    """Final result of study site extraction."""

    coordinates: list[CoordinateCandidate] = Field(default_factory=list)
    locations: list[LocationCandidate] = Field(default_factory=list)
    validation_score: float = 0.0
    primary_study_site: CoordinateCandidate | None = None


class CoordinateExtractor:
    """Extracts coordinates using regex patterns and NLP."""

    def __init__(self) -> None:
        """Extract coordinates using regex patterns and NLP (spaCy)."""
        # Comprehensive regex patterns for different coordinate formats
        self.coordinate_patterns: dict[str, str] = coordinate_patterns

        # Study site keywords for context filtering
        self.study_site_keywords: list[str] = geo_phrases

    def extract_coordinates_from_text(
        self,
        text: str,
        page_number: int,
    ) -> list[CoordinateCandidate]:
        """Extract coordinates from text using regex patterns."""
        candidates: list[CoordinateCandidate] = []

        for pattern_name, pattern in self.coordinate_patterns.items():
            matches = re.finditer(pattern, text, re.IGNORECASE | re.VERBOSE)

            for match in matches:
                context = self._get_context(text, match.start(), match.end())
                confidence = self._calculate_confidence(context, match.group())

                # Parse the coordinate based on pattern type
                coords = self._parse_coordinate_match(match, pattern_name)
                if coords:
                    candidates.append(
                        CoordinateCandidate(
                            latitude=coords[0],
                            longitude=coords[1],
                            confidence_score=confidence,
                            source_type=CoordinateSourceType.TEXT,
                            context=context,
                            page_number=page_number,
                            extraction_method=CoordinateExtractionMethod.REGEX,
                        ),
                    )

        return candidates

    def extract_coordinates_from_tables(
        self,
        tables: list[pd.DataFrame],
    ) -> list[CoordinateCandidate]:
        """Extract coordinates from table data."""
        candidates: list[CoordinateCandidate] = []

        for table in tables:
            page_num = int(getattr(table, "attrs", {}).get("page_number", 1))

            # Look for coordinate columns
            lat_cols = self._find_coordinate_columns(table, ["lat", "latitude", "y"])
            lon_cols = self._find_coordinate_columns(
                table,
                ["lon", "longitude", "long", "x"],
            )

            if lat_cols and lon_cols:
                lat_col = lat_cols[0]
                lon_col = lon_cols[0]

                for idx, row in table.iterrows():
                    try:
                        lat = Latitude(str(row[lat_col]).replace("°", "").strip())
                        lon = Longitude(str(row[lon_col]).replace("°", "").strip())

                        if self._is_valid_coordinate(lat, lon):
                            candidates.append(
                                CoordinateCandidate(
                                    latitude=lat,
                                    longitude=lon,
                                    confidence_score=0.9,  # High confidence for table data
                                    source_type=CoordinateSourceType.TABLE,
                                    context=f"Row {idx}: {row.to_string()}",
                                    page_number=page_num,
                                    extraction_method=CoordinateExtractionMethod.TABLE_PARSING,
                                ),
                            )
                    except (ValueError, TypeError):
                        continue

        return candidates

    def _find_coordinate_columns(
        self,
        df: pd.DataFrame,
        keywords: list[str],
    ) -> list[str]:
        """Find columns that likely contain coordinates."""
        matching_cols: list[str] = []
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
        # This is a simplified parser - you'd expand this for all patterns
        if pattern_name == "lat_lon_pair":
            groups = match.groups()
            min_len = 2  # Minimum groups needed for lat/lon
            if len(groups) >= min_len and groups[0] and groups[1]:
                try:
                    lat = Latitude(groups[0])
                    lon = Longitude(groups[1])
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

    def _calculate_confidence(self, context: str) -> float:
        """Calculate confidence score based on context."""
        confidence = 0  # Base confidence

        context_lower = context.lower()
        for keyword in self.study_site_keywords:
            if keyword in context_lower:
                confidence += 0.1

        # Boost confidence if in methods or study area section
        if any(
            section in context_lower
            for section in [
                "study site",
                "study area",
                "study location",
                "sampling site",
                "field site",
                "research site",
            ]
        ):
            confidence += 0.2

        return min(confidence, 1.0)

    def _is_valid_coordinate(self, lat: float, lon: float) -> bool:
        """Validate coordinate ranges."""
        min_lat, max_lat = -90, 90
        min_lon, max_lon = -180, 180
        return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon


class LocationExtractor:
    """Extract named locations using spaCy NER."""

    def __init__(self, model_name: str = "en_core_web_lg"):
        try:
            self.nlp: Language = spacy.load(model_name)
        except OSError:
            logger.error(f"spaCy model {model_name} not found. Please install it.")
            raise
        self.nlp_matcher: Matcher = Matcher(self.nlp.vocab)
        self.nlp_phrase_matcher: PhraseMatcher = PhraseMatcher(self.nlp.vocab)
        self.nlp_phrase_matcher.add(
            "GEO_CUES",
            [self.nlp.make_doc(phrase) for phrase in geo_phrases],
        )
        self.nlp_matcher.add("LOCATED_IN", [[{"LEMMA": "locate"}, {"LOWER": "in"}]])

        self.geocoder: Nominatim = Nominatim(user_agent="study_site_extractor")

    def sentence_has_geo_signals(self, sent: Span) -> bool:
        text = sent.text
        # Regex for coordinates
        for coord_re in coord_re_list:
            if coord_re.search(text):
                return True
        # Phrase cues
        if self.nlp_phrase_matcher(sent):
            return True
        # Verb pattern cues
        if self.nlp_matcher(sent):
            return True
        # NER cues: any GPE/LOC/FAC with geo keywords
        ents = [e for e in sent.ents if e.label_ in ("GPE", "LOC", "FAC")]
        return bool(
            ents
            and any(
                k in text.lower()
                for k in (
                    "study area",
                    "site",
                    "coordinate",
                    "latitude",
                    "longitude",
                    "utm",
                    "wgs",
                )
            )
        )

    # NOTE: Should return sentences with geo signals only
    # but currently not used in main extraction flow
    # TODO: integrate into extraction pipeline if needed
    def extract_geo_metadata_sentences(self, text: str) -> list[str]:
        doc = self.nlp(text)
        return [sent.text.strip() for sent in doc.sents if self.sentence_has_geo_signals(sent)]

    def extract_locations(self, text: str, page_number: int) -> list[LocationCandidate]:
        """Extract named locations using spaCy NER."""
        doc = self.nlp(text)
        candidates: list[LocationCandidate] = []

        for ent in doc.ents:
            # eliminate non-alphanumeric character from entity text
            ent_text_alphanums = re.sub(r"[^\w\s]", "", ent.text).strip()
            min_length = 3  # Minimum length for a valid location name
            if ent.label_ in ("GPE", "LOC") and len(ent_text_alphanums) >= min_length:
                logger.debug(f"Found entity: {ent.text} ({ent.label_})")

                # Get context around the entity
                context = self._get_entity_context(doc, ent)
                confidence = self._calculate_location_confidence(context)

                candidates.append(
                    LocationCandidate(
                        name=ent.text,
                        confidence_score=confidence,
                        source_type=CoordinateSourceType.TEXT,
                        context=context,
                        page_number=page_number,
                    ),
                )

        return candidates

    def geocode_locations(
        self,
        locations: list[LocationCandidate],
        near_point: Point | None = None,
    ) -> list[LocationCandidate]:
        """Geocode location names to coordinates."""
        for location in locations:
            try:
                geocoded: GeopyLocation | None = self.geocoder.geocode(
                    location.name,
                    timeout=10,
                    viewbox=near_point,
                )
                if geocoded:
                    location.coordinates = Coordinate(
                        Latitude(geocoded.latitude),
                        Longitude(geocoded.longitude),
                    )
                    logger.info(f"Geocoded {location.name}: {location.coordinates}")
            except Exception as e:
                logger.warning(f"Failed to geocode {location.name}: {e}")

        return locations

    def _get_entity_context(self, doc: str, ent, window: int = 50) -> str:
        """Get context around a named entity."""
        start_token = max(0, ent.start - window)
        end_token = min(len(doc), ent.end + window)
        return doc[start_token:end_token].text

    def _calculate_location_confidence(self, context: str) -> float:
        """Calculate confidence for location extraction."""
        confidence = 0.0

        context_lower = context.lower()

        for keyword in geo_phrases:
            if keyword in context_lower:
                confidence += 0.1

        return min(confidence, 1.0)


class CoordinateClusterer:
    """Clusters coordinates and filters out outliers using DBSCAN."""

    def __init__(self, eps_km: float | None = None, min_samples: int = 2):
        """Args:
        eps_km: Clustering radius in kilometers.
        min_samples: Minimum points to form a dense region (cluster).

        """
        self.eps_km: float | None = eps_km
        self.min_samples: int = min_samples

    @staticmethod
    def estimate_eps_km(coordinates: list[tuple[float, float]]) -> float:
        if len(coordinates) < 2:
            return 1.0  # Default if not enough points
        X = np.radians(np.array(coordinates))
        nbrs = NearestNeighbors(n_neighbors=2, metric="haversine").fit(X)
        knbrs: tuple[npt.NDArray[np.float64], npt.NDArray[np.int32]] = nbrs.kneighbors(
            X,
        )
        distances: npt.NDArray[np.float64] = knbrs[0]
        earth_radius_km = 6371.0088
        # distances[:, 1] skips itself (distance 0)
        closest_distances_km = distances[:, 1] * earth_radius_km
        # Heuristic: use the 75th percentile
        return float(np.percentile(closest_distances_km, 75))

    def cluster_and_filter(
        self,
        coordinates: list[tuple[float, float]],
    ) -> list[tuple[float, float]]:
        if not coordinates:
            return []

        # Convert input to radians for haversine metric
        X = np.radians(np.array(coordinates))
        # DBSCAN uses radians for haversine distances; convert kilometers to radians
        earth_radius_km = 6371.0088
        if not self.eps_km:
            # Estimate eps_km if not provided
            self.eps_km = self.estimate_eps_km(coordinates)
        eps = self.eps_km / earth_radius_km
        logger.info(
            f"Using eps={eps:.6f} radians ({self.eps_km:.2f} km) for clustering",
        )

        labels = DBSCAN(
            eps=eps,
            min_samples=self.min_samples,
            metric="haversine",
        ).fit_predict(X)

        for i, label in enumerate(labels):
            if label == -1:
                logger.debug(f"Point {coordinates[i]} is considered noise (label -1)")
            else:
                logger.debug(
                    f"Point {coordinates[i]} is in cluster {label} (label {label})",
                )
        logger.info(
            f"DBSCAN found {len(set(labels)) - (1 if -1 in labels else 0)} clusters",
        )
        # get label of largest cluster that is not noise (-1)
        if len(set(labels)) <= 1:
            logger.info("Only one cluster found or all points are noise.")
            return coordinates
        cluster_labels = labels[labels != -1]
        label_largest_cluster: int = max(
            set(cluster_labels),
            key=list(cluster_labels).count,
        )

        return [
            coord
            for coord, label in zip(coordinates, labels, strict=False)
            if label == label_largest_cluster
        ]


class StudySiteValidator:
    """Validates and ranks extracted study sites."""

    def validate_study_sites(self, result: StudySiteResult) -> StudySiteResult:
        """Validate and rank study site candidates."""
        # Combine coordinates and geocoded locations
        all_candidates = result.coordinates[:]

        for location in result.locations:
            if location.coordinates:
                coord_candidate = CoordinateCandidate(
                    latitude=location.coordinates.latitude,
                    longitude=location.coordinates.longitude,
                    confidence_score=location.confidence_score,
                    source_type=location.source_type,
                    context=location.context,
                    page_number=location.page_number,
                    extraction_method=CoordinateExtractionMethod.GEOCODED,
                )
                all_candidates.append(coord_candidate)

        # Remove duplicates and rank by confidence
        unique_candidates = self._remove_duplicate_coordinates(all_candidates)
        ranked_candidates = sorted(
            unique_candidates,
            key=lambda x: x.confidence_score,
            reverse=True,
        )

        # Set primary study site (highest confidence)
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
        unique_candidates = []

        for candidate in candidates:
            is_duplicate = False
            for unique in unique_candidates:
                if (
                    abs(candidate.latitude - unique.latitude) < threshold
                    and abs(candidate.longitude - unique.longitude) < threshold
                ):
                    # Keep the one with higher confidence
                    if candidate.confidence_score > unique.confidence_score:
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

        # Weight by confidence and number of sources
        total_confidence = sum(c.confidence_score for c in candidates)
        avg_confidence = total_confidence / len(candidates)

        # Bonus for multiple extraction methods
        extraction_methods = set(c.extraction_method for c in candidates)
        method_bonus = len(extraction_methods) * 0.1

        return min(avg_confidence + method_bonus, 1.0)


@final
class StudySiteExtractor:
    """Main class orchestrating the study site extraction process."""

    def __init__(self, spacy_model: str = "en_core_web_lg"):
        self.text_extractor = PyPDFTextExtractor()
        self.table_extractor = CamelotTableExtractor()
        self.coordinate_extractor = CoordinateExtractor()
        self.location_extractor = LocationExtractor(spacy_model)
        self.validator = StudySiteValidator()
        self.clusterer = CoordinateClusterer(eps_km=100.0)

    def extract_site_from_title(self, title: str) -> LocationCandidate | None:
        """Extract location from the paper title."""
        locations = self.location_extractor.extract_locations(title, page_number=0)
        if locations:
            geocoded_locations = self.location_extractor.geocode_locations(locations)
            if geocoded_locations:
                # Return the highest confidence location
                return max(
                    geocoded_locations,
                    key=lambda loc: loc.confidence_score,
                    default=None,
                )
        return None

    def extract_study_site(
        self,
        pdf_path: Path,
        title: str | None = None,
    ) -> StudySiteResult:
        """Main method to extract study site from a PDF paper."""
        logger.info(f"Processing PDF: {pdf_path}")

        # Initialize result
        result = StudySiteResult()

        if title:
            title_location = self.extract_site_from_title(title)
            if title_location:
                result.locations.append(title_location)
                logger.info(f"Extracted location from title: {title_location.name}")
            title_coords = (
                Point(
                    latitude=title_location.latitude,
                    longitude=title_location.longitude,
                )
                if title_location and title_location.coordinates
                else None
            )
        else:
            title_coords = None
        text_data = self.text_extractor.extract_text(pdf_path)
        if not text_data["full_text"]:
            logger.warning(f"No text extracted from {pdf_path}")
            return result

        tables = self.table_extractor.extract_tables(pdf_path)

        for page_data in text_data["pages"]:
            coords = self.coordinate_extractor.extract_coordinates_from_text(
                page_data["text"],
                page_data["page_number"],
            )
            result.coordinates.extend(coords)

        # Extract coordinates from tables
        table_coords = self.coordinate_extractor.extract_coordinates_from_tables(tables)
        result.coordinates.extend(table_coords)

        # Cluster coordinates to remove outliers
        if len(result.coordinates) == 0:
            logger.info("No coordinate candidates found in text or tables.")

        # Extract named locations
        for page_data in text_data["pages"]:
            locations = self.location_extractor.extract_locations(
                page_data["text"],
                page_data["page_number"],
            )
            result.locations.extend(locations)

        # Geocode locations
        result.locations = self.location_extractor.geocode_locations(
            result.locations,
            title_coords,
        )

        coords_list: list[tuple[float, float]] = [
            (c.latitude, c.longitude) for c in result.coordinates
        ]
        coords_list.extend(
            (loc.coordinates.latitude, loc.coordinates.longitude)
            for loc in result.locations
            if loc.coordinates
        )
        logger.info(f"Clustering {len(coords_list)} coordinate candidates")
        logger.info(f"Initial coordinates: {coords_list}")
        # remove duplicates and filter outliers
        coords_list = list(set(coords_list))
        clustered_coords = self.clusterer.cluster_and_filter(coords_list)

        logger.info(f"Clustered coordinates: {clustered_coords}")
        # Update result with clustered coordinates
        result.coordinates = [
            CoordinateCandidate(
                latitude=Latitude(lat),
                longitude=Longitude(lon),
                confidence_score=c.confidence_score,
                source_type=c.source_type,
                context=c.context,
                page_number=c.page_number,
                extraction_method=c.extraction_method,
            )
            for (lat, lon), c in zip(clustered_coords, result.coordinates, strict=False)
        ]
        result.locations = [
            loc
            for loc in result.locations
            if loc.coordinates
            and (loc.coordinates.latitude, loc.coordinates.longitude)
            in clustered_coords
        ]

        # Validate and rank results
        result = self.validator.validate_study_sites(result)

        logger.info(
            f"Extraction complete. Found {len(result.coordinates)} coordinate candidates",
        )
        if result.primary_study_site:
            logger.info(
                f"Primary study site: {result.primary_study_site.latitude}, {result.primary_study_site.longitude}",
            )

        return result

    def extract_multiple_papers(
        self,
        pdf_paths: list[Path],
    ) -> dict[str, StudySiteResult]:
        """Extract study sites from multiple papers."""
        results = {}

        for pdf_path in pdf_paths:
            try:
                results[str(pdf_path)] = self.extract_study_site(pdf_path)
            except Exception as e:
                logger.error(f"Failed to process {pdf_path}: {e}")
                results[str(pdf_path)] = StudySiteResult()

        return results


if __name__ == "__main__":
    extractor = StudySiteExtractor()
    pdf_path = Path.cwd() / "manuscript_revision2.pdf"

    if pdf_path.exists():
        result = extractor.extract_study_site(pdf_path)

        print(f"Validation Score: {result.validation_score:.2f}")

        if result.primary_study_site:
            site = result.primary_study_site
            print(f"Primary Study Site: {site.latitude:.4f}, {site.longitude:.4f}")
            print(f"Confidence: {site.confidence_score:.2f}")
            print(f"Source: {site.source_type}")
            print(f"Context: {site.context}")

        print(f"Total candidates found: {len(result.coordinates)}")
    else:
        print(f"PDF file {pdf_path} not found")
