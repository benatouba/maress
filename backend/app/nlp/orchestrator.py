from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from geopy.point import Point

from app.nlp.clustering import CoordinateClusterer, add_cluster_labels_to_entities
from app.nlp.domain_models import ExtractionResult, GeoEntity
from app.nlp.extractors import BaseEntityExtractor
from app.nlp.geocoding import get_geocoder
from app.nlp.model_config import ModelConfig
from app.nlp.nlp_logger import logger
from app.nlp.pdf_parser import PDFParser
from app.nlp.table_extractor import TableCoordinateExtractor

if TYPE_CHECKING:
    from spacy.tokens import Span


class StudySiteExtractionPipeline:
    """Main pipeline orchestrator following SOLID principles.

    Uses dependency injection for testability and maintainability.
    """

    def __init__(
        self,
        config: ModelConfig,
        pdf_parser: PDFParser,
        extractors: list[BaseEntityExtractor],
        enable_geocoding: bool = True,
        enable_clustering: bool = True,
        enable_table_extraction: bool = True,
    ) -> None:
        """Initialize pipeline with dependencies.

        Args:
            config: Pipeline configuration
            pdf_parser: PDF parsing strategy
            extractors: List of entity extraction strategies
            enable_geocoding: Enable geocoding of location names
            enable_clustering: Enable coordinate clustering
            enable_table_extraction: Enable table coordinate extraction
        """
        self.config: ModelConfig = config
        self.pdf_parser: PDFParser = pdf_parser
        self.extractors: list[BaseEntityExtractor] = extractors

        # Phase 1 improvements
        self.enable_geocoding = enable_geocoding
        self.enable_clustering = enable_clustering
        self.enable_table_extraction = enable_table_extraction

        # Initialize components
        if enable_geocoding:
            self.geocoder = get_geocoder()
        if enable_clustering:
            self.clusterer = CoordinateClusterer(eps_km=50.0, min_samples=1)
        if enable_table_extraction:
            self.table_extractor = TableCoordinateExtractor(config)

    def extract_from_pdf(self, pdf_path: Path, title: str | None = None) -> ExtractionResult:
        """Complete extraction pipeline for a PDF with Phase 1 improvements.

        Pipeline steps:
        1. Parse PDF
        2. Extract from text sections
        3. Extract from tables (Phase 1)
        4. Extract title location for geocoding bias
        5. Geocode location entities (Phase 1 - with caching)
        6. Cluster coordinates (Phase 1 - preserve all clusters)
        7. Deduplicate and rank

        Args:
            pdf_path: Path to scientific PDF
            title: Optional paper title

        Returns:
            ExtractionResult with all geo-referenced entities
        """
        if not pdf_path.exists():
            msg = f"PDF not found: {pdf_path}"
            raise FileNotFoundError(msg)

        logger.info(f"Starting extraction for {pdf_path.name}")

        # Parse PDF
        doc = self.pdf_parser.parse(pdf_path)

        # Extract from sections
        all_entities: list[GeoEntity] = []
        sections_processed = 0

        # 1. Extract title location for geocoding bias
        title_bias_point: Point | None = None
        if title and self.enable_geocoding:
            title_bias_point = self._extract_title_bias_point(title)

        # 2. Extract from title
        if title:
            title_entities: list[GeoEntity] = []
            for extractor in self.extractors:
                entities = extractor.extract(text=title, section="title")
                title_entities.extend(entities)
            all_entities.extend(title_entities)
            sections_processed += 1
            logger.info(f"Extracted {len(title_entities)} entities from title")

        # 3. Extract from text sections
        for span in doc.spans.get("layout", []):
            if span.label_ != "text":
                continue

            section_name = self._classify_section(span)
            section_text = span.text.strip()

            if not section_text:
                continue

            sections_processed += 1

            # Run all extractors on text
            for extractor in self.extractors:
                entities = extractor.extract(text=section_text, section=section_name)
                all_entities.extend(entities)

        logger.info(f"Extracted {len(all_entities)} entities from {sections_processed} sections")

        # 4. Extract from tables (Phase 1 improvement)
        if self.enable_table_extraction:
            table_spans = [s for s in doc.spans.get("layout", []) if s.label_ == "table"]
            if table_spans:
                logger.info(f"Processing {len(table_spans)} tables")
                table_entities = self.table_extractor.extract_from_spans(table_spans)
                all_entities.extend(table_entities)
                logger.info(f"Extracted {len(table_entities)} entities from tables")

        # 5. Geocode location entities (Phase 1 improvement - with caching and rate limiting)
        if self.enable_geocoding:
            logger.info("Geocoding location entities...")
            all_entities = self.geocoder.geocode_entities(all_entities, title_bias_point)
            geocoded_count = sum(1 for e in all_entities if e.coordinates)
            logger.info(f"Geocoded entities: {geocoded_count} now have coordinates")

        # 6. Cluster coordinates (Phase 1 improvement - preserve all clusters)
        cluster_info = {}
        if self.enable_clustering:
            logger.info("Clustering coordinates...")
            all_entities, cluster_info = self.clusterer.cluster_entities(all_entities)
            logger.info(f"Clustering complete: {len(cluster_info)} clusters found")

        # 7. Deduplicate and rank
        unique_entities = self._deduplicate_entities(all_entities)
        ranked_entities = self._rank_entities(unique_entities)

        # Build metadata
        metadata = {
            "total_entities": len(ranked_entities),
            "coordinates": sum(1 for e in ranked_entities if e.coordinates),
            "spatial_relations": sum(
                1 for e in ranked_entities if e.entity_type == "SPATIAL_RELATION"
            ),
            "locations": sum(1 for e in ranked_entities if e.entity_type in ["LOC", "GPE"]),
            "clusters": len(cluster_info),
            "cluster_info": cluster_info,
        }

        logger.info(f"Extraction complete: {len(ranked_entities)} total entities")

        return ExtractionResult(
            pdf_path=pdf_path,
            entities=ranked_entities,
            total_sections_processed=sections_processed,
            extraction_metadata=metadata,
            doc=doc,
            title=title,
        )

    def _extract_title_bias_point(self, title: str) -> Point | None:
        """Extract location from title for geocoding bias.

        Args:
            title: Paper title

        Returns:
            Geographic point or None
        """
        try:
            # Extract locations from title
            title_entities = []
            for extractor in self.extractors:
                entities = extractor.extract(title, section="title")
                title_entities.extend(entities)

            # Find first location entity
            for entity in title_entities:
                if entity.entity_type in ["LOC", "GPE"]:
                    # Geocode it
                    coords = self.geocoder.geocode(entity.text)
                    if coords:
                        logger.info(f"Using title location '{entity.text}' as geocoding bias: {coords}")
                        return Point(latitude=coords[0], longitude=coords[1])

        except Exception as e:
            logger.warning(f"Failed to extract title bias point: {e}")

        return None

    def _classify_section(self, span: Span) -> str:
        """Classify document section from span metadata."""
        heading = str(getattr(span._, "heading", "")).lower()
        text_start = span.text.strip()[:50].lower()

        current_section: str = "other"
        if any(
            word in heading for word in ["method", "material", "experiment", "data"]
        ) or text_start.startswith(("method", "data", "material")):
            current_section = "methods"
        elif "abstract" in heading or text_start.startswith("abstract"):
            current_section = "abstract"
        elif any(word in heading for word in ["result", "finding"]) or text_start.startswith(
            "result",
        ):
            current_section = "results"
        elif "discuss" in heading or text_start.startswith("discuss"):
            current_section = "discussion"
        elif any(
            word in heading for word in ["conclusion", "summary", "outlook"]
        ) or text_start.startswith(("conclusion", "outlook")):
            current_section = "conclusion"
        elif any(word in heading for word in ["intro", "background"]) or text_start.startswith(
            ("intro", "background"),
        ):
            current_section = "introduction"
        elif any(
            word in heading for word in ["reference", "bibliography"]
        ) or text_start.startswith(("reference", "bibliograph")):
            current_section = "references"

        for priority_section in self.config.PRIORITY_SECTIONS:
            if priority_section in heading or text_start.startswith(priority_section):
                return priority_section

        return current_section

    def _deduplicate_entities(self, entities: list[GeoEntity]) -> list[GeoEntity]:
        """Remove duplicate entities based on text and position."""
        seen = set()
        unique: list[GeoEntity] = []

        for entity in entities:
            key = (entity.text.lower(), entity.section, entity.entity_type)
            if key not in seen:
                seen.add(key)
                unique.append(entity)

        return unique

    def _rank_entities(self, entities: list[GeoEntity]) -> list[GeoEntity]:
        """Rank entities by relevance for study site identification."""

        def score(e: GeoEntity) -> float:
            section_scores = {
                "title": 100,
                "methods": 100,
                "study_area": 95,
                "study site": 95,
                "data": 80,
                "materials": 75,
            }
            type_scores = {
                "COORDINATE": 50,
                "SPATIAL_RELATION": 40,
                "GPE": 30,
                "LOC": 25,
            }

            return (
                section_scores.get(e.section, 50)
                + type_scores.get(e.entity_type, 0)
                + e.confidence * 10
            )

        return sorted(entities, key=score, reverse=True)
