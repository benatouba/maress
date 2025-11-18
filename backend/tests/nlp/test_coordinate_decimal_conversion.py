"""Tests for coordinate decimal conversion.

Tests that all coordinate formats are correctly converted to decimal degrees.
"""

import pytest

from app.nlp.text_processing import CoordinateParser


class TestCoordinateDecimalConversion:
    """Test conversion of various coordinate formats to decimal degrees."""

    @pytest.fixture
    def parser(self) -> CoordinateParser:
        """Create a CoordinateParser instance."""
        return CoordinateParser()

    # === WELL-FORMED FORMATS ===

    def test_simple_decimal_pair(self, parser: CoordinateParser) -> None:
        """Test simple decimal coordinate pairs."""
        result = parser.parse_to_decimal("45.123, -122.456")
        assert result is not None
        lat, lon = result
        assert abs(lat - 45.123) < 0.001
        assert abs(lon - (-122.456)) < 0.001

    def test_dms_format(self, parser: CoordinateParser) -> None:
        """Test Degrees Minutes Seconds format."""
        result = parser.parse_to_decimal('45°12\'30"N, 122°30\'15"W')
        assert result is not None
        lat, lon = result
        # 45°12'30" = 45 + 12/60 + 30/3600 = 45.208333
        assert abs(lat - 45.208333) < 0.001
        # 122°30'15" = 122 + 30/60 + 15/3600 = 122.504167
        assert abs(lon - (-122.504167)) < 0.001

    def test_dm_format(self, parser: CoordinateParser) -> None:
        """Test Degrees Minutes format."""
        result = parser.parse_to_decimal("45°12'N, 122°30'W")
        assert result is not None
        lat, lon = result
        # 45°12' = 45 + 12/60 = 45.2
        assert abs(lat - 45.2) < 0.001
        # 122°30' = 122 + 30/60 = 122.5
        assert abs(lon - (-122.5)) < 0.001

    def test_decimal_degrees_with_symbol(self, parser: CoordinateParser) -> None:
        """Test decimal degrees with degree symbol."""
        result = parser.parse_to_decimal("45.123°N, 122.456°W")
        assert result is not None
        lat, lon = result
        assert abs(lat - 45.123) < 0.001
        assert abs(lon - (-122.456)) < 0.001

    def test_labeled_latlon(self, parser: CoordinateParser) -> None:
        """Test labeled format: Lat: X, Lon: Y."""
        result = parser.parse_to_decimal("Lat: 45.5, Lon: -122.3")
        assert result is not None
        lat, lon = result
        assert abs(lat - 45.5) < 0.001
        assert abs(lon - (-122.3)) < 0.001

    def test_labeled_lonlat_reversed(self, parser: CoordinateParser) -> None:
        """Test labeled format with reversed order: Lon: X, Lat: Y."""
        result = parser.parse_to_decimal("Lon: -122.3, Lat: 45.5")
        assert result is not None
        lat, lon = result
        assert abs(lat - 45.5) < 0.001
        assert abs(lon - (-122.3)) < 0.001

    def test_parentheses_format(self, parser: CoordinateParser) -> None:
        """Test coordinates in parentheses."""
        result = parser.parse_to_decimal("(45.123, -122.456)")
        assert result is not None
        lat, lon = result
        assert abs(lat - 45.123) < 0.001
        assert abs(lon - (-122.456)) < 0.001

    def test_brackets_format(self, parser: CoordinateParser) -> None:
        """Test coordinates in brackets."""
        result = parser.parse_to_decimal("[45.123, -122.456]")
        assert result is not None
        lat, lon = result
        assert abs(lat - 45.123) < 0.001
        assert abs(lon - (-122.456)) < 0.001

    def test_decimal_with_direction(self, parser: CoordinateParser) -> None:
        """Test decimal degrees with direction letters."""
        result = parser.parse_to_decimal("45.5 N, 122.3 W")
        assert result is not None
        lat, lon = result
        assert abs(lat - 45.5) < 0.001
        assert abs(lon - (-122.3)) < 0.001

    def test_signed_format(self, parser: CoordinateParser) -> None:
        """Test explicitly signed coordinates."""
        result = parser.parse_to_decimal("+45.123, -122.456")
        assert result is not None
        lat, lon = result
        assert abs(lat - 45.123) < 0.001
        assert abs(lon - (-122.456)) < 0.001

    # === MALFORMED PATTERNS (PDF Artifacts) ===

    def test_degree_as_7(self, parser: CoordinateParser) -> None:
        """Test degree symbol corrupted as '7' (OCR artifact)."""
        result = parser.parse_to_decimal("45 7 12'N, 122 7 30'W")
        assert result is not None
        lat, lon = result
        # Should parse as 45°12' and 122°30'
        assert abs(lat - 45.2) < 0.001
        assert abs(lon - (-122.5)) < 0.001

    def test_degree_as_7_minute_as_b(self, parser: CoordinateParser) -> None:
        """Test both degree as '7' and minute as 'b'."""
        result = parser.parse_to_decimal("45 7 12 b N, 122 7 30 b W")
        assert result is not None
        lat, lon = result
        assert abs(lat - 45.2) < 0.001
        assert abs(lon - (-122.5)) < 0.001

    def test_degree_as_o(self, parser: CoordinateParser) -> None:
        """Test degree symbol corrupted as 'o' or 'O'."""
        result = parser.parse_to_decimal("45o12'N, 122o30'W")
        assert result is not None
        lat, lon = result
        assert abs(lat - 45.2) < 0.001
        assert abs(lon - (-122.5)) < 0.001

    def test_minute_as_backtick(self, parser: CoordinateParser) -> None:
        """Test minute symbol corrupted as backtick."""
        result = parser.parse_to_decimal("45°12`N, 122°30`W")
        assert result is not None
        lat, lon = result
        assert abs(lat - 45.2) < 0.001
        assert abs(lon - (-122.5)) < 0.001

    def test_minute_as_acute(self, parser: CoordinateParser) -> None:
        """Test minute symbol corrupted as acute accent."""
        result = parser.parse_to_decimal("45°12´N, 122°30´W")
        assert result is not None
        lat, lon = result
        assert abs(lat - 45.2) < 0.001
        assert abs(lon - (-122.5)) < 0.001

    def test_compact_decimal_minute(self, parser: CoordinateParser) -> None:
        """Test compact format with decimal minute: 00°01'.72N."""
        result = parser.parse_to_decimal("00°01'.72N, 77°59'.13E")
        assert result is not None
        lat, lon = result
        # 00°01.72' = 0 + 1.72/60 = 0.0287
        assert abs(lat - 0.0287) < 0.001
        # 77°59.13' = 77 + 59.13/60 = 77.9855
        assert abs(lon - 77.9855) < 0.001

    def test_compact_corrupted_format(self, parser: CoordinateParser) -> None:
        """Test compact format with corrupted symbols: 00 7 01 b .72N."""
        result = parser.parse_to_decimal("00 7 01 b .72N, 77 7 59 b .13E")
        assert result is not None
        lat, lon = result
        assert abs(lat - 0.0287) < 0.001
        assert abs(lon - 77.9855) < 0.001

    # === DIRECTION HANDLING ===

    def test_south_direction(self, parser: CoordinateParser) -> None:
        """Test that South direction makes latitude negative."""
        result = parser.parse_to_decimal("45°12'S, 122°30'E")
        assert result is not None
        lat, lon = result
        assert lat < 0, "South latitude should be negative"
        assert lon > 0, "East longitude should be positive"
        assert abs(lat - (-45.2)) < 0.001

    def test_west_direction(self, parser: CoordinateParser) -> None:
        """Test that West direction makes longitude negative."""
        result = parser.parse_to_decimal("45°12'N, 122°30'W")
        assert result is not None
        lat, lon = result
        assert lat > 0, "North latitude should be positive"
        assert lon < 0, "West longitude should be negative"
        assert abs(lon - (-122.5)) < 0.001

    def test_negative_decimal_without_direction(self, parser: CoordinateParser) -> None:
        """Test negative decimals without explicit direction."""
        result = parser.parse_to_decimal("-45.123, -122.456")
        assert result is not None
        lat, lon = result
        assert lat < 0
        assert lon < 0
        assert abs(lat - (-45.123)) < 0.001
        assert abs(lon - (-122.456)) < 0.001

    # === PRECISION ===

    def test_high_precision_coordinates(self, parser: CoordinateParser) -> None:
        """Test that high-precision coordinates are preserved."""
        result = parser.parse_to_decimal("37.774929, -122.419418")
        assert result is not None
        lat, lon = result
        assert abs(lat - 37.774929) < 0.000001
        assert abs(lon - (-122.419418)) < 0.000001

    def test_dms_with_decimal_seconds(self, parser: CoordinateParser) -> None:
        """Test DMS with decimal seconds."""
        result = parser.parse_to_decimal('45°12\'30.5"N, 122°30\'15.8"W')
        assert result is not None
        lat, lon = result
        # 45°12'30.5" = 45 + 12/60 + 30.5/3600 = 45.20847
        assert abs(lat - 45.20847) < 0.0001
        # 122°30'15.8" = 122 + 30/60 + 15.8/3600 = 122.50439
        assert abs(lon - (-122.50439)) < 0.0001

    def test_decimal_minutes(self, parser: CoordinateParser) -> None:
        """Test format with decimal minutes."""
        result = parser.parse_to_decimal("45°12.5'N, 122°30.8'W")
        assert result is not None
        lat, lon = result
        # 45°12.5' = 45 + 12.5/60 = 45.2083
        assert abs(lat - 45.2083) < 0.001
        # 122°30.8' = 122 + 30.8/60 = 122.5133
        assert abs(lon - (-122.5133)) < 0.001

    # === EDGE CASES ===

    def test_equator_coordinates(self, parser: CoordinateParser) -> None:
        """Test coordinates at the equator."""
        result = parser.parse_to_decimal("0.0, 0.0")
        assert result is not None
        lat, lon = result
        assert abs(lat) < 0.001
        assert abs(lon) < 0.001

    def test_prime_meridian_coordinates(self, parser: CoordinateParser) -> None:
        """Test coordinates at prime meridian."""
        result = parser.parse_to_decimal("45.0, 0.0")
        assert result is not None
        lat, lon = result
        assert abs(lat - 45.0) < 0.001
        assert abs(lon) < 0.001

    def test_pole_coordinates(self, parser: CoordinateParser) -> None:
        """Test coordinates near poles."""
        result = parser.parse_to_decimal("89.9, 0.0")
        assert result is not None
        lat, lon = result
        assert abs(lat - 89.9) < 0.001

    def test_dateline_coordinates(self, parser: CoordinateParser) -> None:
        """Test coordinates near international dateline."""
        result = parser.parse_to_decimal("45.0, 179.9")
        assert result is not None
        lat, lon = result
        assert abs(lon - 179.9) < 0.001

    def test_invalid_format_returns_none(self, parser: CoordinateParser) -> None:
        """Test that invalid format returns None."""
        result = parser.parse_to_decimal("not a coordinate")
        assert result is None

    def test_single_number_returns_none(self, parser: CoordinateParser) -> None:
        """Test that single number without pair returns None."""
        result = parser.parse_to_decimal("45.123")
        assert result is None

    def test_incomplete_dms_returns_none(self, parser: CoordinateParser) -> None:
        """Test that incomplete DMS returns None."""
        result = parser.parse_to_decimal("45°N")
        assert result is None

    # === REAL-WORLD EXAMPLES ===

    def test_san_francisco_coordinates(self, parser: CoordinateParser) -> None:
        """Test real San Francisco coordinates."""
        result = parser.parse_to_decimal("37.7749, -122.4194")
        assert result is not None
        lat, lon = result
        assert 37 <= lat <= 38
        assert -123 <= lon <= -122

    def test_paris_dms_coordinates(self, parser: CoordinateParser) -> None:
        """Test Paris in DMS format."""
        result = parser.parse_to_decimal('48°51\'24"N, 2°21\'03"E')
        assert result is not None
        lat, lon = result
        assert abs(lat - 48.8567) < 0.01
        assert abs(lon - 2.3508) < 0.01

    def test_tokyo_coordinates(self, parser: CoordinateParser) -> None:
        """Test Tokyo coordinates."""
        result = parser.parse_to_decimal("35.6762, 139.6503")
        assert result is not None
        lat, lon = result
        assert 35 <= lat <= 36
        assert 139 <= lon <= 140

    def test_sydney_coordinates(self, parser: CoordinateParser) -> None:
        """Test Sydney coordinates."""
        result = parser.parse_to_decimal("-33.8688, 151.2093")
        assert result is not None
        lat, lon = result
        assert lat < 0, "Sydney is in southern hemisphere"
        assert abs(lat - (-33.8688)) < 0.001
        assert abs(lon - 151.2093) < 0.001


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
