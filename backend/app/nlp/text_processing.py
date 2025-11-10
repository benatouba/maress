"""Text cleaning for scientific PDFs.

We clean parsed PDFs for further NLP. The focus is on coordinate
preservation.
"""

from __future__ import annotations

import re
import unicodedata
from typing import ClassVar


class GeographicSymbolCleaner:
    """Geographic symbol normalisation with PDF artifact handling."""

    # Comprehensive symbol mapping for PDF extraction issues
    SYMBOL_FIXES: ClassVar[dict[str, str]] = {
        # Degree symbols (most common PDF corruptions)
        "°": "°",
        "\u00b0": "°",
        "\u00ba": "°",  # Masculine ordinal (often confused)
        "\u2103": "°C",
        "Â°": "°",
        "â°": "°",
        "º": "°",
        "&deg;": "°",
        "˚": "°",
        "\u02da": "°",  # Ring above
        " 7 ": "°",  # spaCy-layout corruption of degree symbol
        # Prime symbols (minutes) - EXPANDED
        "′": "'",
        "\u2032": "'",
        "'": "'",  # Straight quote
        "`": "'",  # Backtick
        "´": "'",  # Acute accent
        "&prime;": "'",
        "â€²": "'",  # UTF-8 corruption
        " b ": "'",  # spaCy-layout corruption of minute/apostrophe
        "â": "'",  # Another common corruption
        # Double prime symbols (seconds) - EXPANDED
        "″": '"',
        "\u2033": '"',
        '"': '"',  # Smart quote
        '"': '"',  # Smart quote
        "&Prime;": '"',
        "â€³": '"',  # UTF-8 corruption
        "''": '"',  # Two single quotes
        # Tilde corruptions - NEW
        " F ": " ~ ",  # Common tilde corruption
        "F ": "~",  # At start of approximate numbers
        # Approximately symbol
        "≈": "~",
        "∼": "~",
        # Whitespace issues
        "Â ": " ",
        "\xa0": " ",  # Non-breaking space
        "\u2009": " ",  # Thin space
        "\u200a": " ",  # Hair space
        "\u202f": " ",  # Narrow no-break space
        "\u3000": " ",  # Ideographic space
        # Common PDF ligatures that break text
        "ﬁ": "fi",
        "ﬂ": "fl",
        "ﬀ": "ff",
        "ﬃ": "ffi",
        "ﬄ": "ffl",
        "ﬅ": "st",
        # Dash variations (important for negative coordinates)
        "–": "-",  # En dash
        "—": "-",  # Em dash
        "−": "-",  # Minus sign
        "‐": "-",  # Hyphen
        "‑": "-",  # Non-breaking hyphen
        # Multiplication signs (common in dimensions)
        "×": "x",
        "✕": "x",
        "∗": "*",
        # Common letter corruptions in coordinates
        " I ": " 1 ",  # Capital I confused with 1
        " O ": " 0 ",  # Capital O confused with 0
        " l ": " 1 ",  # Lowercase L confused with 1
        # Quote marks that break text
        """: '"',
        """: '"',
        "'": "'",
        "'": "'",
        "„": '"',
        "‚": "'",
        # Bullet points and list markers
        "•": "-",
        "◦": "-",
        "▪": "-",
        "▫": "-",
        # Ellipsis
        "…": "...",
    }

    # Patterns for common coordinate corruptions
    COORDINATE_CORRUPTIONS: ClassVar[dict[str, str]] = {
        # Handle broken degree-minute-second formats
        r"(\d+)\s*o\s*(\d+)": r"\1°\2",  # "45 o 30" -> "45°30"
        r"(\d+)\.(\d+)\s*[oO]\s*([NSEW])": r"\1.\2°\3",  # "45.5 o N" -> "45.5°N"
        # Fix the specific "7" and "b" corruptions in coordinates
        r"(\d+)\s+7\s+(\d+)\s+b\s+": r"\1°\2'",  # "00 7 01 b " -> "00°01'"
        r"(\d+)\s+7\s+(\d+)\s+b": r"\1°\2'",  # "00 7 01 b" -> "00°01'"
        r"(\d+)\s+7\s+(\d+)": r"\1°\2",  # "77 7 59" -> "77°59"
        # Fix spacing issues around coordinates
        r"([NSEW])\s*,\s*(\d+)": r"\1, \2",  # Normalize comma spacing
        r"(\d+)\s+([°'\"″′])\s*([NSEW])": r"\1\2\3",  # Remove spaces before direction
        # Handle reversed or malformed formats
        r"([NSEW])\s*([°'\"″′])\s*(\d+)": r"\3\2\1",  # "N°45" -> "45°N"
        # Fix broken latitude/longitude labels
        r"Lat(?:itude)?\.?\s*[:=]?\s*": "Latitude: ",
        r"Lon(?:gitude)?\.?\s*[:=]?\s*": "Longitude: ",
        # Fix approximate symbol before numbers (common in dates)
        r"F\s*(\d+)": r"~\1",  # "F 910 years" -> "~910 years"
        r"(\d+)\s*F\s*(\d+)": r"\1~\2",  # "680 F 650" -> "680~650"
    }

    # Additional patterns for scientific notation corrections
    SCIENTIFIC_NOTATION_FIXES: ClassVar[dict[str, str]] = {
        # Fix superscripts that got corrupted
        r"10\s*\^\s*([0-9\-]+)": r"10^\1",  # "10 ^ 3" -> "10^3"
        r"10\s+([0-9\-]+)": r"10^\1",  # "10 3" -> "10^3" (when superscript lost)
        r"km\s*2": "km²",  # "km 2" -> "km²"
        r"km\s*3": "km³",  # "km 3" -> "km³"
        r"m\s*2": "m²",  # "m 2" -> "m²"
        r"m\s*3": "m³",  # "m 3" -> "m³"
        # Fix degree Celsius
        r"(\d+)\s*7\s*C\b": r"\1°C",  # "25 7 C" -> "25°C"
        r"(\d+)\s*o\s*C\b": r"\1°C",  # "25 o C" -> "25°C"
    }

    def clean(self, text: str) -> str:
        """Fix geographic symbols and PDF artifacts for accurate parsing.

        Args:
            text: Raw text string

        Returns:
            Cleaned text string with normalized symbols
        """
        # . Normalize Unicode (NFKC form for compatibility)
        text = unicodedata.normalize("NFKC", text)

        # Fix common symbol corruptions
        for wrong, correct in self.SYMBOL_FIXES.items():
            text = text.replace(wrong, correct)

        # Fix coordinate-specific corruptions
        for pattern, replacement in self.COORDINATE_CORRUPTIONS.items():
            text = re.sub(pattern, replacement, text)

        # Fix scientific notation issues
        for pattern, replacement in self.SCIENTIFIC_NOTATION_FIXES.items():
            text = re.sub(pattern, replacement, text)

        # Normalize whitespace around coordinates
        text = self._normalize_coordinate_spacing(text)

        # Fix remaining minute symbol issues in coordinate context
        return self._fix_minute_symbols_in_coordinates(text)

    def _normalize_coordinate_spacing(self, text: str) -> str:
        """Normalize spacing around coordinate components."""
        # Remove excess whitespace around degree/minute/second symbols
        text = re.sub(r"\s*([°'\"″′])\s*", r"\1", text)  # noqa: RUF001

        # Ensure space after comma in coordinate pairs
        text = re.sub(r",(\S)", r", \1", text)

        # Remove spaces between number and degree symbol
        return re.sub(r"(\d+)\s+°", r"\1°", text)

    def _fix_minute_symbols_in_coordinates(self, text: str) -> str:
        """Fix minute symbols specifically in coordinate contexts."""
        # Pattern: number followed by potential corrupted minute symbol, then decimal or direction
        # Example: "01 .72 N" should become "01'.72N"
        text = re.sub(r"(\d+)\s+\.(\d+)\s+([NSEW])", r"\1'.\2\3", text)

        # Pattern: degree symbol, number, space, number (missing minute symbol)
        # Example: "45°30 15 N" should become "45°30'15\"N"
        return re.sub(
            r"(\d+°\d+)\s+(\d+)\s+([NSEW])",
            r"\1'\2\"\3",
            text,
        )


class PDFTextCleaner:
    """Comprehensive PDF text cleaning for scientific documents."""

    def __init__(self) -> None:
        """Initialize cleaner with symbol cleaner."""
        self.symbol_cleaner: GeographicSymbolCleaner = GeographicSymbolCleaner()

    def clean(self, text: str) -> str:
        """Apply comprehensive cleaning pipeline to text string.

        Args:
            text: Raw text string from PDF extraction

        Returns:
            Cleaned text string optimized for NLP processing
        """
        text = self.symbol_cleaner.clean(text)  # Fix geographic symbols
        text = self._remove_pdf_artifacts(text)  # Remove PDF extraction artifacts
        text = self._fix_hyphenation(text)  # Fix hyphenation from line breaks
        text = self._fix_character_confusions(text)  # Fix character confusions
        text = self._normalize_whitespace(text)  # Normalize whitespace
        text = self._fix_common_errors(text)  # Fix common OCR/extraction errors
        text = self._preserve_coordinates(text)  # Preserve coordinate integrity

        return text.strip()

    def _remove_pdf_artifacts(self, text: str) -> str:
        """Remove common PDF extraction artifacts."""
        # Remove page numbers at line starts/ends
        text = re.sub(r"^\d{1,4}\s*$", "", text, flags=re.MULTILINE)

        # Remove isolated numbers that are likely page numbers
        text = re.sub(r"\s+\d{1,3}\s+(?=[A-Z])", " ", text)

        # Remove repeated headers/footers (same line repeated 3+ times)
        text = re.sub(r"(^.{1,80}$)(\n\1){2,}", r"\1", text, flags=re.MULTILINE)

        # Remove excessive newlines but preserve paragraphs
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text

    def _fix_hyphenation(self, text: str) -> str:
        """Fix word hyphenation from PDF line breaks."""
        # Fix hyphenated words at line breaks
        # "geograph-\nical" -> "geographical"
        text = re.sub(r"(\w+)-\s*\n\s*(\w+)", r"\1\2", text)

        # Handle soft hyphens
        text = text.replace("\u00ad", "")  # Soft hyphen

        # Fix broken coordinates (e.g., "45°30-\n15"N" -> "45°30'15"N")
        text = re.sub(r"([°'\"″′]\d+)-\s*\n\s*(\d+[°'\"″′])", r"\1'\2", text)

        return text

    def _normalize_whitespace(self, text: str) -> str:
        """Normalise all whitespace to single spaces except paragraph
        breaks."""
        # Replace multiple spaces with single space
        text = re.sub(r"[ \t]+", " ", text)

        # Normalise line breaks (preserve double breaks for paragraphs)
        text = re.sub(r"\n\s*\n", "\n\n", text)
        text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)

        # Remove spaces before punctuation
        text = re.sub(r"\s+([.,;:!?])", r"\1", text)

        # Ensure space after punctuation
        text = re.sub(r"([.,;:!?])(?=[A-Za-z])", r"\1 ", text)

        return text

    def _remove_pdf_artifacts(self, text: str) -> str:
        """Remove common PDF extraction artifacts."""
        # Remove page numbers at line starts/ends
        text = re.sub(r"^\d{1,4}\s*$", "", text, flags=re.MULTILINE)

        # Remove isolated numbers that are likely page numbers
        text = re.sub(r"\s+\d{1,3}\s+(?=[A-Z])", " ", text)

        # Remove repeated headers/footers (same line repeated 3+ times)
        text = re.sub(r"(^.{1,80}$)(\n\1){2,}", r"\1", text, flags=re.MULTILINE)

        # Remove excessive newlines but preserve paragraphs
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text

    def _fix_hyphenation(self, text: str) -> str:
        """Fix word hyphenation from PDF line breaks."""
        # Fix hyphenated words at line breaks
        # "geograph-\nical" -> "geographical"
        text = re.sub(r"(\w+)-\s*\n\s*(\w+)", r"\1\2", text)

        # Handle soft hyphens
        text = text.replace("\u00ad", "")  # Soft hyphen

        # Fix broken coordinates (e.g., "45°30-\n15"N" -> "45°30'15"N")
        text = re.sub(r"([°'\"″′]\d+)-\s*\n\s*(\d+[°'\"″′])", r"\1'\2", text)

        return text

    def _fix_character_confusions(self, text: str) -> str:
        """Fix common character recognition errors."""
        # Common OCR confusions in scientific text
        confusions = {
            # Only fix when clearly wrong (with word boundaries)
            r"\bO(?=\d)": "0",  # O before digit -> 0
            r"(?<=\d)O\b": "0",  # O after digit -> 0
            r"\bl(?=\d)": "1",  # l before digit -> 1
            r"(?<=\d)l\b": "1",  # l after digit -> 1
            r"\bI(?=\d)": "1",  # I before digit -> 1
            # Fix "rn" that should be "m" in common words
            r"\b([Nn])arn": r"\1am",  # "narne" -> "name"
            # Fix "vv" that should be "w"
            r"\bvv": "w",
            # Fix zero vs O in ORSTOM-like acronyms (institution names)
            r"\b0RSTOM\b": "ORSTOM",
            r"\b0RS\b": "ORS",
        }

        for pattern, replacement in confusions.items():
            text = re.sub(pattern, replacement, text)

        return text

    def _normalize_whitespace(self, text: str) -> str:
        """Normalize all whitespace to single spaces except paragraph
        breaks."""
        # Replace multiple spaces with single space
        text = re.sub(r"[ \t]+", " ", text)

        # Normalize line breaks (preserve double breaks for paragraphs)
        text = re.sub(r"\n\s*\n", "\n\n", text)
        text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)

        # Remove spaces before punctuation
        text = re.sub(r"\s+([.,;:!?])", r"\1", text)

        # Ensure space after punctuation (but not in decimals)
        text = re.sub(r"([.,;:!?])(?=[A-Za-z])", r"\1 ", text)

        return text

    def _fix_common_errors(self, text: str) -> str:
        """Fix common OCR and extraction errors in scientific text."""
        # Fix common issues
        replacements = {
            # Scientific notation
            r"(\d+)\s*x\s*10\s*([−-]?\d+)": r"\1×10^\2",
            # Decimal separator issues in elevations (but not coordinates)
            r"(\d+),(\d{3})\s+m\b": r"\1.\2 m",  # European decimals in measurements
            # Fix "14 C" (carbon-14 dating)
            r"\b14\s*C\b": "¹⁴C",
            # Fix "BP" spacing (Before Present)
            r"(\d+)\s*-\s*(\d+)\s+years\s+BP": r"\1-\2 years BP",
        }

        for pattern, replacement in replacements.items():
            text = re.sub(pattern, replacement, text)

        return text

    def _preserve_coordinates(self, text: str) -> str:
        """Ensure coordinate patterns are preserved and normalized."""
        # Add spaces around coordinate pairs for better tokenization
        # But not within the coordinate itself
        text = re.sub(
            r"([0-9°'\"″′]+[NSEW])\s*,?\s*([0-9°'\"″′]+[NSEW])",
            r"\1, \2",
            text,
        )

        # Ensure direction indicators are uppercase
        text = re.sub(
            r"(\d+[°'\"″′]+)([nsew])\b",
            lambda m: m.group(1) + m.group(2).upper(),
            text,
        )

        return text


class CoordinateParser:
    """Coordinate parser with comprehensive pattern matching and validation.

    Phase 2: Enhanced to detect 15+ coordinate formats with validation.
    """

    # Phase 2: Expanded patterns - prioritizing most common formats first
    PATTERNS: ClassVar[list[str]] = [
        # === HIGH PRIORITY: Most common in scientific papers ===

        # Simple decimal pairs (most common): 45.123, -122.456 or -45.123, -122.456
        r"(-?\d+\.\d{2,})\s*,\s*(-?\d+\.\d{2,})",

        # With labels: Lat: 45.123, Lon: -122.456 or Latitude: 45.123, Longitude: -122.456
        r"(?:Lat|Latitude|lat|latitude)[:\s]*(-?\d+\.\d+)[,\s]*(?:Lon|Longitude|long|longitude)[:\s]*(-?\d+\.\d+)",
        r"(?:Lon|Longitude|long|longitude)[:\s]*(-?\d+\.\d+)[,\s]*(?:Lat|Latitude|lat|latitude)[:\s]*(-?\d+\.\d+)",

        # In parentheses: (45.123, -122.456) or ( 45.123 , -122.456 )
        r"\(\s*(-?\d+\.\d{2,})\s*,\s*(-?\d+\.\d{2,})\s*\)",

        # In brackets: [45.123, -122.456]
        r"\[\s*(-?\d+\.\d{2,})\s*,\s*(-?\d+\.\d{2,})\s*\]",

        # === MEDIUM PRIORITY: Traditional formats with symbols ===

        # Decimal degrees with degree symbol: -45.123°, 122.456° or 45.123° N, 122.456° W
        r"(-?\d+\.\d+)\s*°\s*([NS])?\s*,?\s*(-?\d+\.\d+)\s*°\s*([EW])?",

        # Degrees minutes seconds: 45°12'30"N, 122°30'15"W (with flexible spacing)
        r"(\d+)\s*[°]\s*(\d+)\s*[\'′]\s*(\d+\.?\d*)\s*[\"″]\s*([NS])\s*,?\s*(\d+)\s*[°]\s*(\d+)\s*[\'′]\s*(\d+\.?\d*)\s*[\"″]\s*([EW])",

        # Degrees minutes: 45°12'N, 122°30'W
        r"(\d+)\s*[°]\s*(\d+)\s*[\'′]\s*([NS])\s*,?\s*(\d+)\s*[°]\s*(\d+)\s*[\'′]\s*([EW])",

        # Decimal minutes: 45°12.5'N, 122°30.8'W
        r"(\d+)\s*[°]\s*(\d+\.?\d*)\s*[\'′]\s*([NS])\s*,?\s*(\d+)\s*[°]\s*(\d+\.?\d*)\s*[\'′]\s*([EW])",

        # === LOW PRIORITY: Alternative formats ===

        # Without symbols (requires direction): 45.5 N, 122.3 W
        r"(\d+\.\d+)\s+([NS])\s*,?\s*(\d+\.\d+)\s+([EW])",

        # With explicit signs: +45.123, -122.456
        r"([+-]\d+\.\d{2,})\s*,\s*([+-]\d+\.\d{2,})",

        # Compact format: 00°01'.72N, 77°59'.13E
        r"(\d+)\s*[°]\s*(\d+)\s*[\'′]\.(\d+)\s*([NS])\s*,?\s*(\d+)\s*[°]\s*(\d+)\s*[\'′]\.(\d+)\s*([EW])",

        # With spaces before direction: 00°01'.72 N (corrupted format)
        r"(\d+)\s*[°]\s*(\d+)\s*[\'′]\s*\.?\s*(\d+)\s+([NS])\s*,?\s*(\d+)\s*[°]\s*(\d+)\s*[\'′]\s*\.?\s*(\d+)\s+([EW])",

        # Range format (extract midpoint): 45.1-45.2°N, 122.3-122.5°W
        r"(\d+\.\d+)\s*-\s*(\d+\.\d+)\s*°?\s*([NS])\s*,?\s*(\d+\.\d+)\s*-\s*(\d+\.\d+)\s*°?\s*([EW])",
    ]

    def extract_coordinates(self, text: str) -> list[tuple[str, int, int, float]]:
        """Extract coordinate strings with positions from text.

        Phase 2: Now returns quality score for ranking.

        Args:
            text: Text string to search for coordinates

        Returns:
            List of tuples (coordinate_string, start_pos, end_pos, quality_score)
        """
        matches: list[tuple[str, int, int, float]] = []
        seen_positions: set[tuple[int, int]] = set()

        for pattern in self.PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                position = (match.start(), match.end())
                # Avoid duplicate matches from overlapping patterns
                if position not in seen_positions:
                    coord_str = match.group()
                    # Phase 2: Validate coordinates before adding
                    parsed = self.parse_to_decimal(coord_str)
                    if parsed and self._validate_coordinates(parsed):
                        quality = self._assess_format_quality(coord_str, parsed)
                        seen_positions.add(position)
                        matches.append((coord_str, match.start(), match.end(), quality))

        return matches

    def _validate_coordinates(self, coords: tuple[float, float]) -> bool:
        """Validate that coordinates are within valid ranges.

        Phase 2: Reject invalid coordinates.

        Args:
            coords: Tuple of (latitude, longitude)

        Returns:
            True if valid, False otherwise
        """
        lat, lon = coords

        # Check latitude range
        if lat < -90 or lat > 90:
            return False

        # Check longitude range
        if lon < -180 or lon > 180:
            return False

        # Reject obviously wrong coordinates (e.g., 999.999)
        if abs(lat) > 90 or abs(lon) > 180:
            return False

        # Reject coordinates that are exactly 0,0 (often placeholders)
        if lat == 0.0 and lon == 0.0:
            return False

        return True

    def _assess_format_quality(self, coord_str: str, coords: tuple[float, float]) -> float:
        """Assess the quality/precision of coordinate format.

        Phase 2: Higher scores for more precise formats.

        Args:
            coord_str: Original coordinate string
            coords: Parsed (lat, lon) tuple

        Returns:
            Quality score between 0.0 and 1.0
        """
        lat, lon = coords

        # Check for DMS format (most precise)
        if '"' in coord_str or '″' in coord_str:
            return 1.0

        # Check decimal precision
        lat_decimals = len(str(lat).split('.')[-1]) if '.' in str(lat) else 0
        lon_decimals = len(str(lon).split('.')[-1]) if '.' in str(lon) else 0
        avg_decimals = (lat_decimals + lon_decimals) / 2

        if avg_decimals >= 4:
            return 0.95  # Very high precision
        elif avg_decimals >= 3:
            return 0.90  # High precision
        elif avg_decimals >= 2:
            return 0.80  # Medium precision
        elif avg_decimals >= 1:
            return 0.70  # Low precision
        else:
            return 0.50  # Integer degrees only

        # Check for DM format with decimal minutes
        if "'" in coord_str or '′' in coord_str:
            if '.' in coord_str:
                return 0.90  # Decimal minutes
            return 0.75  # Integer minutes only

        return 0.80  # Default for valid coordinates

    def parse_to_decimal(self, coord_str: str) -> tuple[float, float] | None:
        """Convert coordinate string to decimal degrees (lat, lon).

        Phase 2: Enhanced to handle 15+ coordinate formats.

        Args:
            coord_str: Coordinate string (e.g., "45°12'30\"N, 122°30'15\"W")

        Returns:
            Tuple of (latitude, longitude) in decimal degrees, or None if parsing fails
        """
        try:
            # Phase 2: Try each pattern - ordered by commonality
            patterns = [
                # Simple decimal pairs: 45.123, -122.456
                (
                    r"^(-?\d+\.\d{2,})\s*,\s*(-?\d+\.\d{2,})$",
                    lambda m: (float(m.group(1)), float(m.group(2))),
                ),
                # With labels (lat first): Lat: 45.123, Lon: -122.456
                (
                    r"(?:Lat|Latitude|lat|latitude)[:\s]*(-?\d+\.\d+)[,\s]*(?:Lon|Longitude|long|longitude)[:\s]*(-?\d+\.\d+)",
                    lambda m: (float(m.group(1)), float(m.group(2))),
                ),
                # With labels (lon first): Lon: -122.456, Lat: 45.123
                (
                    r"(?:Lon|Longitude|long|longitude)[:\s]*(-?\d+\.\d+)[,\s]*(?:Lat|Latitude|lat|latitude)[:\s]*(-?\d+\.\d+)",
                    lambda m: (float(m.group(2)), float(m.group(1))),
                ),
                # In parentheses: (45.123, -122.456)
                (
                    r"\(\s*(-?\d+\.\d{2,})\s*,\s*(-?\d+\.\d{2,})\s*\)",
                    lambda m: (float(m.group(1)), float(m.group(2))),
                ),
                # In brackets: [45.123, -122.456]
                (
                    r"\[\s*(-?\d+\.\d{2,})\s*,\s*(-?\d+\.\d{2,})\s*\]",
                    lambda m: (float(m.group(1)), float(m.group(2))),
                ),
                # Degrees + minutes + seconds: 45°12'30"N, 122°30'15"W
                (
                    r"(\d+)\s*[°]\s*(\d+)\s*[\'′]\s*(\d+\.?\d*)\s*[\"″]\s*([NS])\s*,?\s*(\d+)\s*[°]\s*(\d+)\s*[\'′]\s*(\d+\.?\d*)\s*[\"″]\s*([EW])",
                    lambda m: self._calc_decimal(
                        [float(m.group(1)), float(m.group(2)), float(m.group(3))],
                        m.group(4),
                        [float(m.group(5)), float(m.group(6)), float(m.group(7))],
                        m.group(8),
                    ),
                ),
                # Degrees + minutes: 45°12'N, 122°30'W
                (
                    r"(\d+)\s*[°]\s*(\d+)\s*[\'′]\s*([NS])\s*,?\s*(\d+)\s*[°]\s*(\d+)\s*[\'′]\s*([EW])",
                    lambda m: self._calc_decimal(
                        [float(m.group(1)), float(m.group(2))],
                        m.group(3),
                        [float(m.group(4)), float(m.group(5))],
                        m.group(6),
                    ),
                ),
                # Decimal minutes: 45°12.5'N, 122°30.8'W
                (
                    r"(\d+)\s*[°]\s*(\d+\.?\d*)\s*[\'′]\s*([NS])\s*,?\s*(\d+)\s*[°]\s*(\d+\.?\d*)\s*[\'′]\s*([EW])",
                    lambda m: self._calc_decimal(
                        [float(m.group(1)), float(m.group(2))],
                        m.group(3),
                        [float(m.group(4)), float(m.group(5))],
                        m.group(6),
                    ),
                ),
                # Decimal degrees with symbol: 45.123° N, 122.456° W
                (
                    r"(-?\d+\.\d+)\s*°\s*([NS])?\s*,?\s*(-?\d+\.\d+)\s*°\s*([EW])?",
                    lambda m: self._calc_decimal(
                        [float(m.group(1))],
                        m.group(2) or 'N' if float(m.group(1)) >= 0 else 'S',
                        [float(m.group(3))],
                        m.group(4) or 'E' if float(m.group(3)) >= 0 else 'W',
                    ),
                ),
                # Without symbols (requires direction): 45.5 N, 122.3 W
                (
                    r"(\d+\.\d+)\s+([NS])\s*,?\s*(\d+\.\d+)\s+([EW])",
                    lambda m: self._calc_decimal(
                        [float(m.group(1))],
                        m.group(2),
                        [float(m.group(3))],
                        m.group(4),
                    ),
                ),
                # With explicit signs: +45.123, -122.456
                (
                    r"^([+-]\d+\.\d{2,})\s*,\s*([+-]\d+\.\d{2,})$",
                    lambda m: (float(m.group(1)), float(m.group(2))),
                ),
                # Compact format: 00°01'.72N, 77°59'.13E
                (
                    r"(\d+)\s*[°]\s*(\d+)\s*[\'′]\.(\d+)\s*([NS])\s*,?\s*(\d+)\s*[°]\s*(\d+)\s*[\'′]\.(\d+)\s*([EW])",
                    lambda m: self._calc_decimal(
                        [float(m.group(1)), float(f"{m.group(2)}.{m.group(3)}")],
                        m.group(4),
                        [float(m.group(5)), float(f"{m.group(6)}.{m.group(7)}")],
                        m.group(8),
                    ),
                ),
                # Range format (use midpoint): 45.1-45.2°N, 122.3-122.5°W
                (
                    r"(\d+\.\d+)\s*-\s*(\d+\.\d+)\s*°?\s*([NS])\s*,?\s*(\d+\.\d+)\s*-\s*(\d+\.\d+)\s*°?\s*([EW])",
                    lambda m: self._calc_decimal(
                        [(float(m.group(1)) + float(m.group(2))) / 2],
                        m.group(3),
                        [(float(m.group(4)) + float(m.group(5))) / 2],
                        m.group(6),
                    ),
                ),
            ]

            for pattern, calculator in patterns:
                match = re.search(pattern, coord_str, re.IGNORECASE)
                if match:
                    result = calculator(match)
                    # Ensure result is valid tuple
                    if result and isinstance(result, tuple) and len(result) == 2:
                        return result

        except (ValueError, AttributeError, IndexError, ZeroDivisionError):
            return None

        return None

    def _calc_decimal(
        self,
        components: list[float],
        lat_dir: str,
        lon_components: list[float],
        lon_dir: str,
    ) -> tuple[float, float]:
        """Calculate decimal degrees from components."""
        # Latitude
        lat = components[0]
        if len(components) > 1:
            lat += components[1] / 60.0
        if len(components) > 2:
            lat += components[2] / 3600.0

        if lat_dir.upper() == "S":
            lat = -lat

        # Longitude
        lon = lon_components[0]
        if len(lon_components) > 1:
            lon += lon_components[1] / 60.0
        if len(lon_components) > 2:
            lon += lon_components[2] / 3600.0

        if lon_dir.upper() == "W":
            lon = -lon

        return (lat, lon)


class SpatialRelationExtractor:
    """Extracts spatial relation phrases (Single Responsibility)."""

    PATTERNS: ClassVar[list[str]] = [
        r"(\d+\.?\d*)\s*(km|kilometers|kilometres|metres|miles|m|meters)\s*(north|south|east|west|N|S|E|W)\s*(?:of|from)\s+([A-Z][a-zA-Z\s]+)",
        r"(?:near|nearby|close to|adjacent to|in the vicinity of)\s+([A-Z][a-zA-Z\s]+)",
        r"(?:located|situated)\s+(?:in|at|near)\s+([A-Z][a-zA-Z\s]+)",
    ]

    def extract(self, text: str) -> list[tuple[str, int, int]]:
        """Extract spatial relation phrases with positions from text.

        Args:
            text: Text string to search for spatial relations

        Returns:
            List of tuples (relation_string, start_pos, end_pos)
        """
        matches: list[tuple[str, int, int]] = []
        for pattern in self.PATTERNS:
            matches.extend(
                (match.group(), match.start(), match.end())
                for match in re.finditer(pattern, text, re.IGNORECASE)
            )
        return matches
