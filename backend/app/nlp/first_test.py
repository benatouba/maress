import re
from pathlib import Path

import camelot
import pdfplumber
import spacy
from geopy.geocoders import Nominatim
from pypdf import PdfReader

# Load spaCy NLP model
SPACY_MODEL = spacy.load("en_core_web_lg")

# Regex for coordinate matching (more refined)
COORD_PATTERN = re.compile(
    r"""
    (?x)                                    # verbose mode
    (
        # Decimal degrees with hemisphere
        -?\d{1,3}\.\d+\s*[NSEW]
      |
        # DMS: 45°30'15.5"N or 45°30'15.5" N
        \d{1,3}°\s*\d{1,2}'\s*\d{1,2}(?:\.\d+)?\"\s*[NSEW]
      |
        # Degrees and decimal minutes: 45°30.25'N
        \d{1,3}°\s*\d{1,2}(?:\.\d+)'[NSEW]
    )
    """,
    re.VERBOSE,
)


class PDFProcessor:
    def __init__(self, path: str):
        self.path = path

    def extract_text(self) -> str:
        texts = []
        with pdfplumber.open(self.path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    texts.append(text)
        return "\n".join(texts)

    def extract_tables(self, flavor: str = "lattice") -> list:
        # Using camelot to extract all tables
        tables = camelot.read_pdf(self.path, pages="all", flavor=flavor)
        return [table.df for table in tables]


class GeoEntityExtractor:
    def __init__(self, text: str):
        self.text = text
        self.doc = SPACY_MODEL(self.text)

    def extract_geopolitical_entities(self) -> list[str]:
        # Extract GPE and LOC entities
        return [ent.text for ent in self.doc.ents if ent.label_ in ("GPE", "LOC")]

    def extract_coordinates(self) -> list[tuple[float, float]]:
        # Extract potential coordinate strings using regex
        matches = COORD_PATTERN.findall(self.text)
        coords = []
        for match in matches:
            # Parse and validate coordinate string
            coords.extend(self.parse_coordinate_string(match))
        return coords

    def parse_coordinate_string(self, coord_str: str) -> list[tuple[float, float]]:
        # Parses coordinate string, returns list of (lat, lon)
        # Implement detailed parsing here: DMS, decimal, hemisphere, etc.
        # For brevity, here's a simplified version:
        try:
            # Check decimal with hemispheres
            decimal_match = re.match(r"(-?\d+\.\d+)\s*([NSEW])", coord_str.strip())
            if decimal_match:
                val, hemi = decimal_match.groups()
                val = float(val)
                if hemi in ("S", "W"):
                    val = -abs(val)
                elif hemi in ("N", "E"):
                    val = abs(val)
                # For this simplified example, return as (lat, lon) with placeholder lon
                return [(val, 0.0)]
            # Extend with full DMS parsing if needed
        except Exception:
            pass
        return []

    def find_study_keywords_near(
        self, keywords: list[str], window_size: int = 100
    ) -> list[str]:
        # Extract sentences/paragraphs around keywords
        pattern = "|".join([re.escape(k.lower()) for k in keywords])
        matches = re.finditer(pattern, self.text.lower())
        snippets = []
        for match in matches:
            start = max(0, match.start() - window_size)
            end = match.end() + window_size
            snippets.append(self.text[start:end])
        return snippets


class StudyLocationValidator:
    def __init__(self, geolocator: Nominatim | None = None):
        self.geolocator = geolocator or Nominatim(user_agent="geo_extractor")

    def geocode_location(self, place_name: str) -> tuple[float, float] | None:
        try:
            location = self.geolocator.geocode(place_name, timeout=10)
            if location:
                return (location.latitude, location.longitude)
        except Exception:
            pass
        return None

    def validate_coords_in_area(
        self,
        coords: list[tuple[float, float]],
        bounding_box: tuple[float, float, float, float],
    ) -> list[tuple[float, float]]:
        # bounding box: min_lat, max_lat, min_lon, max_lon
        validated = []
        min_lat, max_lat, min_lon, max_lon = bounding_box
        for lat, lon in coords:
            if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
                validated.append((lat, lon))
        return validated


def extract_locations_from_text(document: list[str]) -> list[str]:
    nlp = spacy.load("en_core_web_sm")
    doc = nlp(document)
    locations = [ent.text for ent in doc.ents if ent.label_ in ("GPE", "LOC")]
    return locations


def get_study_site_candidates(document: str) -> str:
    study_site_candidates = []
    keywords = [
        "study site",
        "located at",
        "sampling site",
        "latitude",
        "longitude",
        "coordinates",
        "study area",
        "field site",
        "site",
        "location",
        "gps",
    ]

    for line in document.split("\n"):
        line_lc = line.lower()
        if any(kw in line_lc for kw in keywords):
            study_site_candidates.append(line)
    return "\n".join(study_site_candidates) if study_site_candidates else ""


def match_degrees(document: str) -> list[str]:
    pattern = r"""(?x)
    (
        -?\d{1,3}\.\d+\s*[NnSsEeWw]
      |
        \d{1,3}°\s*\d{1,2}'\s*\d{1,2}(?:\.\d+)?\"\s*[NnSsEeWw]
      |
        \d{1,3}°\s*\d{1,2}(?:\.\d+)'\s*[NnSsEeWw]
    )
    """
    # pattern = r"(-?\d{1,3}\.\d+)[,°]?\s*[NnSs]?,?\s*(-?\d{1,3}\.\d+)[,°]?\s*[EeWw]?"
    return re.findall(pattern, document)


def extract_locations_from_tables(tables):
    nlp = spacy.load("en_core_web_sm")
    locations = []
    for table in tables:
        for row in table:
            for cell in row:
                doc = nlp(cell)
                locations.extend(
                    [ent.text for ent in doc.ents if ent.label_ in ("GPE", "LOC")]
                )
    return locations


def get_content(path: Path) -> tuple[str, list[str]]:
    with pdfplumber.open(path) as pdf:
        tables = [
            table
            for page in pdf.pages
            for table in page.extract_tables()
            if page.extract_tables()
        ]
        full_text = [page.extract_text() for page in pdf.pages if page.extract_text()]

    document = "\n".join(full_text)
    return document, tables


def get_content_with_pypdf(path: Path):
    full_text = []

    with path.open("rb") as f:
        reader = PdfReader(f)
        for page in reader.pages:
            text = page.extract_text()
            if text:  # Some pages may not have extractable text
                full_text.append(text)

    return "\n".join(full_text)


def get_tables_with_camelot(path: Path) -> list[dict[str, list[str | int | float]]]:
    # Lattice mode: for tables with lines/borders
    tables = camelot.read_pdf(path, pages="all", flavor="stream")
    table_dicts = []
    for i, t in enumerate(tables):
        # check if the table is empty
        if t.df.empty:
            print("Empty table found, skipping.")
            continue
        print(f"Table {i}:")
        # append as dict
        table_dicts.append(t.df.to_dict(orient="records"))

    return table_dicts
