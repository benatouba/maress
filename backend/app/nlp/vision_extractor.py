"""Local image-based coordinate extraction from PDF map figures.

Uses Tesseract HOCR output to extract positioned text from map images,
then applies coordinate pattern matching to identify axis labels,
site names, and geographic annotations. Fully local, CPU-only.
"""

from __future__ import annotations

import logging
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar
from xml.etree import ElementTree

import pymupdf

from app.nlp.domain_models import GeoEntity
from app.nlp.text_processing import CoordinateParser, GeographicSymbolCleaner

logger = logging.getLogger(__name__)

# Minimum image dimensions (pixels) to consider as a potential map
_MIN_MAP_WIDTH = 200
_MIN_MAP_HEIGHT = 200
# DPI for rendering PDF image regions
_RENDER_DPI = 300
# Maximum images to process per PDF
_MAX_IMAGES_PER_PDF = 15


@dataclass(frozen=True)
class HocrWord:
    """A word extracted by Tesseract HOCR with bounding box."""

    text: str
    x0: int
    y0: int
    x1: int
    y1: int
    confidence: float


@dataclass(frozen=True)
class MapCoordinate:
    """A coordinate found in a map image."""

    text: str
    lat: float
    lon: float
    confidence: float
    page_number: int
    source: str  # "axis_label", "annotation", "ocr_text"


def _parse_hocr_words(hocr_xml: str) -> list[HocrWord]:
    """Parse Tesseract HOCR XML output into positioned words."""
    words: list[HocrWord] = []
    try:
        root = ElementTree.fromstring(hocr_xml)
    except ElementTree.ParseError:
        return words

    for elem in root.iter():
        if elem.get("class") != "ocrx_word":
            continue

        title = elem.get("title", "")
        text = (elem.text or "").strip()
        if not text:
            # Try to get text from child elements
            text = "".join(elem.itertext()).strip()
        if not text:
            continue

        # Parse bbox from title: "bbox x0 y0 x1 y1; x_wconf 95"
        bbox_match = re.search(r"bbox\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", title)
        conf_match = re.search(r"x_wconf\s+(\d+)", title)

        if not bbox_match:
            continue

        confidence = int(conf_match.group(1)) / 100.0 if conf_match else 0.5

        words.append(
            HocrWord(
                text=text,
                x0=int(bbox_match.group(1)),
                y0=int(bbox_match.group(2)),
                x1=int(bbox_match.group(3)),
                y1=int(bbox_match.group(4)),
                confidence=confidence,
            )
        )

    return words


def _run_tesseract_hocr(image_path: Path) -> str | None:
    """Run Tesseract in HOCR mode on an image file."""
    try:
        result = subprocess.run(
            ["tesseract", str(image_path), "stdout", "--psm", "11", "hocr"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.warning("Tesseract HOCR failed for %s", image_path.name)
    return None


class MapTextAnalyzer:
    """Analyzes positioned text from map images to extract coordinates.

    Uses spatial relationships between text elements to identify:
    - Axis labels (coordinates along image edges)
    - Site name annotations (labeled points on the map)
    - Inline coordinate mentions in captions or legends
    """

    # Patterns that indicate coordinate-like text on map axes
    AXIS_PATTERNS: ClassVar[list[str]] = [
        r"\d+\s*°\s*[NSEW]",          # 22°S, 68°W
        r"\d+°\s*\d+\s*['\u2032]\s*[NSEW]",  # 22°20'S
        r"\d+\.\d+\s*°?\s*[NSEW]?",   # 22.33 or 22.33°S
        r"[NSEW]\s*\d+",               # S22, W68
    ]

    # Edge margin: fraction of image dimension considered "edge"
    EDGE_FRACTION = 0.15

    def __init__(self) -> None:
        self._coord_parser = CoordinateParser()
        self._symbol_cleaner = GeographicSymbolCleaner()

    def extract_from_words(
        self,
        words: list[HocrWord],
        image_width: int,
        image_height: int,
        page_number: int,
    ) -> list[MapCoordinate]:
        """Extract coordinates from positioned HOCR words.

        Strategy:
        1. Reconstruct full text and run coordinate parser on it
        2. Identify axis labels (text near edges containing degree symbols)
        3. Build bounding box from axis extremes
        """
        results: list[MapCoordinate] = []
        if not words:
            return results

        # Strategy 1: Reconstruct lines and run coordinate patterns
        results.extend(self._extract_from_text_lines(words, page_number))

        # Strategy 2: Find axis labels near image edges
        axis_coords = self._extract_from_axis_labels(
            words, image_width, image_height, page_number
        )
        results.extend(axis_coords)

        return results

    def _extract_from_text_lines(
        self, words: list[HocrWord], page_number: int
    ) -> list[MapCoordinate]:
        """Reconstruct text from words and run coordinate extraction."""
        results: list[MapCoordinate] = []

        # Sort words by vertical then horizontal position to form lines
        sorted_words = sorted(words, key=lambda w: (w.y0, w.x0))

        # Group into lines (words within 10px vertical distance)
        lines: list[list[HocrWord]] = []
        current_line: list[HocrWord] = []
        last_y = -100

        for word in sorted_words:
            if abs(word.y0 - last_y) > 10:
                if current_line:
                    lines.append(current_line)
                current_line = [word]
                last_y = word.y0
            else:
                current_line.append(word)

        if current_line:
            lines.append(current_line)

        # Process each line
        for line in lines:
            line_text = " ".join(w.text for w in line)
            line_text = self._symbol_cleaner.clean(line_text)

            coords = self._coord_parser.extract_coordinates(line_text)
            for coord_str, _start, _end, quality in coords:
                parsed = self._coord_parser.parse_to_decimal(coord_str)
                if parsed:
                    avg_conf = sum(w.confidence for w in line) / len(line)
                    results.append(
                        MapCoordinate(
                            text=coord_str,
                            lat=parsed[0],
                            lon=parsed[1],
                            confidence=min(quality, avg_conf) * 0.8,
                            page_number=page_number,
                            source="ocr_text",
                        )
                    )

        # Also try the full text as one block
        full_text = " ".join(w.text for w in sorted_words)
        full_text = self._symbol_cleaner.clean(full_text)
        coords = self._coord_parser.extract_coordinates(full_text)
        seen = {(r.lat, r.lon) for r in results}

        for coord_str, _start, _end, quality in coords:
            parsed = self._coord_parser.parse_to_decimal(coord_str)
            if parsed and (parsed[0], parsed[1]) not in seen:
                results.append(
                    MapCoordinate(
                        text=coord_str,
                        lat=parsed[0],
                        lon=parsed[1],
                        confidence=quality * 0.7,
                        page_number=page_number,
                        source="ocr_text",
                    )
                )
                seen.add((parsed[0], parsed[1]))

        return results

    def _extract_from_axis_labels(
        self,
        words: list[HocrWord],
        image_width: int,
        image_height: int,
        page_number: int,
    ) -> list[MapCoordinate]:
        """Find coordinate labels near image edges (map axes)."""
        results: list[MapCoordinate] = []

        left_margin = image_width * self.EDGE_FRACTION
        right_margin = image_width * (1 - self.EDGE_FRACTION)
        top_margin = image_height * self.EDGE_FRACTION
        bottom_margin = image_height * (1 - self.EDGE_FRACTION)

        # Collect edge words that look like coordinates
        lat_values: list[float] = []
        lon_values: list[float] = []

        for word in words:
            text = self._symbol_cleaner.clean(word.text)
            is_edge = (
                word.x0 < left_margin
                or word.x1 > right_margin
                or word.y0 < top_margin
                or word.y1 > bottom_margin
            )
            if not is_edge:
                continue

            # Check if it looks like a coordinate axis label
            for pattern in self.AXIS_PATTERNS:
                if re.search(pattern, text, re.IGNORECASE):
                    parsed = self._try_parse_single_axis(text)
                    if parsed:
                        val, axis = parsed
                        if axis == "lat":
                            lat_values.append(val)
                        else:
                            lon_values.append(val)
                    break

        # If we found both lat and lon axis labels, compute a center point
        if lat_values and lon_values:
            center_lat = (min(lat_values) + max(lat_values)) / 2
            center_lon = (min(lon_values) + max(lon_values)) / 2

            # Add bounding box as a coordinate
            results.append(
                MapCoordinate(
                    text=f"Map axes: {min(lat_values):.2f}-{max(lat_values):.2f}, "
                    f"{min(lon_values):.2f}-{max(lon_values):.2f}",
                    lat=center_lat,
                    lon=center_lon,
                    confidence=0.75,
                    page_number=page_number,
                    source="axis_label",
                )
            )

        return results

    def _try_parse_single_axis(self, text: str) -> tuple[float, str] | None:
        """Try to parse a single axis label like '22°S' or '68°W'."""
        # DM format: 22°20'S
        m = re.search(
            r"(\d+)\s*°\s*(\d+)\s*['\u2032]?\s*([NSEW])", text, re.IGNORECASE
        )
        if m:
            value = float(m.group(1)) + float(m.group(2)) / 60
            direction = m.group(3).upper()
            if direction in ("S", "W"):
                value = -value
            axis = "lat" if direction in ("N", "S") else "lon"
            return value, axis

        # DD format: 22°S or 22.5°S
        m = re.search(r"(\d+\.?\d*)\s*°?\s*([NSEW])", text, re.IGNORECASE)
        if m:
            value = float(m.group(1))
            direction = m.group(2).upper()
            if direction in ("S", "W"):
                value = -value
            axis = "lat" if direction in ("N", "S") else "lon"
            return value, axis

        return None


class VisionMapExtractor:
    """Extracts coordinates from map images embedded in PDFs.

    Pipeline:
    1. Extract images from PDF pages using PyMuPDF
    2. Filter by size (skip tiny icons/logos)
    3. Run Tesseract HOCR to get positioned text
    4. Pre-screen: skip images without coordinate-like text
    5. Analyze positioned text to find coordinates
    6. Return GeoEntity objects for pipeline integration
    """

    def __init__(
        self,
        *,
        min_width: int = _MIN_MAP_WIDTH,
        min_height: int = _MIN_MAP_HEIGHT,
        render_dpi: int = _RENDER_DPI,
        max_images: int = _MAX_IMAGES_PER_PDF,
    ) -> None:
        self.min_width = min_width
        self.min_height = min_height
        self.render_dpi = render_dpi
        self.max_images = max_images
        self._analyzer = MapTextAnalyzer()
        self._has_tesseract = self._check_tesseract()

    @staticmethod
    def _check_tesseract() -> bool:
        """Check if Tesseract CLI is available."""
        try:
            result = subprocess.run(
                ["tesseract", "--version"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def extract_from_pdf(
        self, pdf_path: Path, *, section: str = "figure"
    ) -> list[GeoEntity]:
        """Extract coordinates from map images in a PDF.

        Args:
            pdf_path: Path to the PDF file
            section: Section label for extracted entities

        Returns:
            List of GeoEntity objects with coordinates from map images
        """
        if not self._has_tesseract:
            logger.warning("Tesseract not available, skipping image extraction")
            return []

        try:
            pdf_doc = pymupdf.open(pdf_path)
        except Exception:
            logger.warning("Could not open PDF for image extraction: %s", pdf_path.name)
            return []

        all_entities: list[GeoEntity] = []
        images_processed = 0

        try:
            for page_idx in range(pdf_doc.page_count):
                if images_processed >= self.max_images:
                    break

                page = pdf_doc[page_idx]
                image_infos = page.get_image_info(hashes=False)

                for info in image_infos:
                    if images_processed >= self.max_images:
                        break

                    bbox_raw = info.get("bbox")
                    if not bbox_raw:
                        continue

                    bbox = pymupdf.Rect(bbox_raw)
                    if bbox.width < self.min_width or bbox.height < self.min_height:
                        continue

                    entities = self._process_image_region(
                        page, bbox, page_idx + 1, section
                    )
                    all_entities.extend(entities)
                    images_processed += 1

        finally:
            pdf_doc.close()

        logger.info(
            "Image extraction: processed %d images, found %d entities from %s",
            images_processed,
            len(all_entities),
            pdf_path.name,
        )
        return all_entities

    def _process_image_region(
        self,
        page: pymupdf.Page,
        bbox: pymupdf.Rect,
        page_number: int,
        section: str,
    ) -> list[GeoEntity]:
        """Process a single image region from a PDF page."""
        # Render the image region at high DPI
        try:
            pix = page.get_pixmap(clip=bbox, dpi=self.render_dpi, alpha=False)
        except Exception:
            return []

        # Save to temp file for Tesseract
        with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as tmp:
            tmp_path = Path(tmp.name)
            pix.save(str(tmp_path))

            # Run Tesseract HOCR
            hocr_xml = _run_tesseract_hocr(tmp_path)

        if not hocr_xml:
            return []

        # Parse HOCR words
        words = _parse_hocr_words(hocr_xml)
        if not words:
            return []

        # Pre-screen: check if any text looks coordinate-related
        all_text = " ".join(w.text for w in words)
        if not self._has_coordinate_indicators(all_text):
            return []

        # Analyze positioned text for coordinates
        map_coords = self._analyzer.extract_from_words(
            words, pix.width, pix.height, page_number
        )

        # Convert to GeoEntity objects
        entities: list[GeoEntity] = []
        for mc in map_coords:
            entities.append(
                GeoEntity(
                    text=mc.text,
                    entity_type="COORDINATE",
                    context=f"[MAP_IMAGE page={mc.page_number} source={mc.source}]",
                    section=section,
                    confidence=mc.confidence,
                    start_char=0,
                    end_char=max(1, len(mc.text)),
                    coordinates=(mc.lat, mc.lon),
                )
            )

        return entities

    @staticmethod
    def _has_coordinate_indicators(text: str) -> bool:
        """Check if text contains any coordinate-like indicators."""
        indicators = [
            r"[°\u00b0\u00ba\u02da]",  # Degree symbols
            r"\d+\s*[NSEW]\b",          # Direction after number
            r"[NSEW]\s*\d+",            # Direction before number
            r"[Ll]at",                   # Latitude label
            r"[Ll]on",                   # Longitude label
            r"UTM",                      # UTM reference
            r"[Kk]m\b",                  # Distance units (common on maps)
        ]
        return any(re.search(p, text) for p in indicators)
