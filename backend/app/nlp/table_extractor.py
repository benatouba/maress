"""Table coordinate extraction (Phase 1 improvement).

Extracts coordinates from structured tables in scientific papers.
Tables typically have high confidence due to structured data.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, override

import pandas as pd

from app.nlp.domain_models import GeoEntity
from app.nlp.extractors import BaseEntityExtractor
from app.nlp.nlp_logger import logger
from app.nlp.text_processing import CoordinateParser

if TYPE_CHECKING:
    from spacy.tokens import Span

    from app.nlp.model_config import ModelConfig


class TableCoordinateExtractor(BaseEntityExtractor):
    """Extracts explicit coordinates from table structures.

    Tables in scientific papers often contain structured coordinate data
    with high reliability. This extractor:
    - Identifies lat/lon columns
    - Parses coordinate values
    - Extracts associated site names
    - Assigns high confidence scores
    """

    def __init__(self, config: ModelConfig) -> None:
        """Initialize table extractor."""
        super().__init__(config)
        self.parser = CoordinateParser()

    @override
    def extract(self, text: str, section: str) -> list[GeoEntity]:
        """Extract coordinates from table text.

        Note: This is a simplified version. For full table extraction,
        use extract_from_dataframes() with parsed tables.

        Args:
            text: Table text
            section: Document section

        Returns:
            List of GeoEntity objects
        """
        # Simple text-based extraction for tables
        # Real implementation should use parsed DataFrame
        return []

    def extract_from_spans(
        self,
        table_spans: list[Span],
        section: str = "methods",
    ) -> list[GeoEntity]:
        """Extract coordinates from spaCy table spans.

        Args:
            table_spans: List of table Span objects from spacy-layout
            section: Document section name

        Returns:
            List of GeoEntity objects with coordinates
        """
        all_entities: list[GeoEntity] = []

        for i, table_span in enumerate(table_spans, 1):
            # Parse table to DataFrame
            df = self._parse_table_to_dataframe(table_span)

            if df is not None:
                entities = self.extract_from_dataframe(df, table_idx=i, section=section)
                all_entities.extend(entities)

        return all_entities

    def extract_from_dataframe(
        self,
        df: pd.DataFrame,
        table_idx: int = 1,
        section: str = "methods",
    ) -> list[GeoEntity]:
        """Extract coordinates from parsed DataFrame.

        Args:
            df: pandas DataFrame with table data
            table_idx: Table index for context
            section: Document section

        Returns:
            List of GeoEntity objects
        """
        entities: list[GeoEntity] = []

        # Find coordinate columns
        lat_cols = self._find_coordinate_columns(df, ["lat", "latitude", "y"])
        lon_cols = self._find_coordinate_columns(df, ["lon", "longitude", "long", "x"])

        if not (lat_cols and lon_cols):
            logger.debug(f"Table {table_idx}: No coordinate columns found")
            return entities

        lat_col = lat_cols[0]
        lon_col = lon_cols[0]

        logger.info(f"Table {table_idx}: Found coordinate columns - lat: {lat_col}, lon: {lon_col}")

        # Extract site names if available
        name_cols = self._find_coordinate_columns(
            df,
            ["name", "site", "location", "station", "plot", "id"],
        )
        name_col = name_cols[0] if name_cols else None

        # Process each row
        for idx, row in df.iterrows():
            try:
                # Get and clean coordinate values
                lat_val = str(row[lat_col]).replace("°", "").strip()
                lon_val = str(row[lon_col]).replace("°", "").strip()

                # Skip empty or invalid values
                if not lat_val or not lon_val or lat_val == "nan" or lon_val == "nan":
                    continue

                # Parse coordinates
                lat = float(lat_val)
                lon = float(lon_val)

                # Validate coordinate ranges
                if not self._is_valid_coordinate(lat, lon):
                    logger.debug(f"Invalid coordinates in table row {idx}: {lat}, {lon}")
                    continue

                # Get site name if available
                site_name = None
                if name_col and name_col in row:
                    site_name = str(row[name_col])
                    if site_name == "nan":
                        site_name = None

                if not site_name:
                    site_name = f"Table_{table_idx}_Site_{idx}"

                # Create context from row
                row_str = ", ".join(f"{k}={v}" for k, v in row.items() if v != "nan")
                context = f"Table {table_idx}, Row {idx}: {row_str[:150]}"

                # Create entity
                entity = GeoEntity(
                    text=f"{lat}, {lon}",
                    entity_type="COORDINATE",
                    context=context,
                    section=section,
                    confidence=0.9,  # High confidence for table data
                    start_char=0,  # Not applicable for table extraction
                    end_char=0,
                    coordinates=(lat, lon),
                )

                entities.append(entity)
                logger.debug(f"Extracted from table: {site_name} at {lat}, {lon}")

            except (ValueError, TypeError, KeyError) as e:
                logger.debug(f"Failed to parse table row {idx}: {e}")
                continue

        logger.info(f"Table {table_idx}: Extracted {len(entities)} coordinates")
        return entities

    def _parse_table_to_dataframe(self, table_span: Span) -> pd.DataFrame | None:
        """Parse table span text to DataFrame.

        Args:
            table_span: spaCy Span object containing table

        Returns:
            DataFrame or None if parsing fails
        """
        try:
            table_text = table_span.text.strip()
            lines = [line.strip() for line in table_text.split("\n") if line.strip()]

            if len(lines) < 2:
                return None

            # Split by tabs or multiple spaces
            rows = []
            for line in lines:
                row = re.split(r"\t+|\s{2,}", line)
                row = [cell.strip() for cell in row if cell.strip()]
                if row:
                    rows.append(row)

            if not rows or len(rows) < 2:
                return None

            # Use first row as header
            header = rows[0]
            data_rows = rows[1:]

            # Ensure consistent column count
            max_cols = max(len(header), max(len(row) for row in data_rows))
            header = header + [""] * (max_cols - len(header))
            data_rows = [row + [""] * (max_cols - len(row)) for row in data_rows]

            df = pd.DataFrame(data_rows, columns=header)
            logger.debug(f"Parsed table: {len(df)} rows × {len(df.columns)} columns")

            return df

        except Exception as e:
            logger.warning(f"Failed to parse table: {e}")
            return None

    def _find_coordinate_columns(
        self,
        df: pd.DataFrame,
        keywords: list[str],
    ) -> list[str]:
        """Find columns matching coordinate keywords.

        Args:
            df: DataFrame to search
            keywords: List of column name keywords

        Returns:
            List of matching column names
        """
        matches = []
        for col in df.columns:
            col_lower = str(col).lower()
            if any(keyword in col_lower for keyword in keywords):
                matches.append(col)
        return matches

    def _is_valid_coordinate(self, lat: float, lon: float) -> bool:
        """Validate coordinate ranges.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            True if valid
        """
        return -90 <= lat <= 90 and -180 <= lon <= 180
