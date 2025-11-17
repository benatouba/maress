from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from geopy.point import Point

from app.nlp.clustering import CoordinateClusterer
from app.nlp.context_extraction import ContextExtractor
from app.nlp.domain_models import ExtractionMetadata, ExtractionResult, GeoEntity
from app.nlp.extractors import BaseEntityExtractor
from app.nlp.geocoding import get_geocoder
from app.nlp.model_config import ModelConfig
from app.nlp.nlp_logger import logger
from app.nlp.pdf_parser import PDFParser
from app.nlp.quality_assessment import TextQualityAssessor
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
        *,
        enable_geocoding: bool = True,
        enable_clustering: bool = True,
        enable_table_extraction: bool = True,
        enable_quality_assessment: bool = True,
        enable_enriched_context: bool = True,
    ) -> None:
        """Initialize pipeline with dependencies.

        Args:
            config: Pipeline configuration
            pdf_parser: PDF parsing strategy
            extractors: List of entity extraction strategies
            enable_geocoding: Enable geocoding of location names
            enable_clustering: Enable coordinate clustering
            enable_table_extraction: Enable table coordinate extraction
            enable_quality_assessment: Enable text quality assessment
            enable_enriched_context: Enable enriched context extraction
        """
        self.config: ModelConfig = config
        self.pdf_parser: PDFParser = pdf_parser
        self.extractors: list[BaseEntityExtractor] = extractors

        # improvements
        self.enable_geocoding = enable_geocoding
        self.enable_clustering = enable_clustering
        self.enable_table_extraction = enable_table_extraction
        self.enable_quality_assessment = enable_quality_assessment
        self.enable_enriched_context = enable_enriched_context

        # Initialize components
        if enable_geocoding:
            self.geocoder = get_geocoder()
        if enable_clustering:
            self.clusterer = CoordinateClusterer(eps_km=50.0, min_samples=1)
        if enable_table_extraction:
            self.table_extractor = TableCoordinateExtractor(config)

        if enable_quality_assessment:
            self.quality_assessor = TextQualityAssessor()
        if enable_enriched_context:
            self.context_extractor = ContextExtractor()

    def extract_from_pdf(self, pdf_path: Path, title: str | None = None) -> ExtractionResult:
        """Complete extraction pipeline for a PDF improvements.

        Pipeline steps:
        - Parse PDF (with improved sentence boundaries)
        - Extract title location for geocoding bias ONLY (not included in results)
        - Extract from text sections (with quality assessment)
        - Extract from tables
        - Geocode location entities
        - Cluster coordinates and keep largest cluster
        - Deduplicate and rank (with enriched context)

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
        logger.debug(f"Parsed PDF doc spans: {doc.spans}")

        # Extract from sections
        all_entities: list[GeoEntity] = []
        sections_processed = 0

        # Extract title location for geocoding bias ONLY
        # Title entities are used as hints for geocoding but NOT included in results
        title_bias_point: Point | None = None
        if title and self.enable_geocoding:
            title_bias_point = self._extract_title_bias_point(title)
            logger.info("Title entities used for geocoding bias only, not included in results")

        # Extract from text sections
        section_quality_scores = {}
        layout_spans = doc.spans.get("layout", [])
        logger.info(f"Found {len(layout_spans)} layout spans in PDF")

        text_spans = [s for s in layout_spans if s.label_ == "text"]
        logger.info(f"Found {len(text_spans)} text spans for extraction")

        for span in text_spans:
            section_name = self._classify_section(span)
            section_text = span.text.strip()

            if not section_text:
                logger.debug(f"Skipping empty section: {section_name}")
                continue

            logger.debug(f"Processing section '{section_name}' with {len(section_text)} characters")

            # Assess text quality
            if self.enable_quality_assessment:
                quality_score = self.quality_assessor.assess_quality(section_text)
                section_quality_scores[section_name] = quality_score

                if quality_score.overall_score < 0.5:
                    logger.warning(
                        f"Low quality text in section '{section_name}': {quality_score}",
                    )

            sections_processed += 1

            # Run all extractors on text
            logger.debug(f"Extracting entities from section '{section_name}'")
            logger.debug(f"Section text preview: {section_text[:50]!r}...")
            for extractor in self.extractors:
                extractor_name = extractor.__class__.__name__
                entities = extractor.extract(text=section_text, section=section_name)
                if entities:
                    logger.debug(
                        f"{extractor_name} found {len(entities)} entities in '{section_name}'"
                    )
                all_entities.extend(entities)

        logger.info(f"Extracted {len(all_entities)} entities from {sections_processed} sections")
        logger.debug(f"First extracted entities: {all_entities[:5]}")

        # Extract from tables
        if self.enable_table_extraction:
            table_spans = [s for s in doc.spans.get("layout", []) if s.label_ == "table"]
            if table_spans:
                logger.info(f"Processing {len(table_spans)} tables")
                table_entities = self.table_extractor.extract_from_spans(table_spans)
                all_entities.extend(table_entities)
                logger.info(f"Extracted {len(table_entities)} entities from tables")

        # Geocode location entities (with caching and rate limiting)
        if self.enable_geocoding:
            logger.info("Geocoding location entities...")
            all_entities = self.geocoder.geocode_entities(all_entities, title_bias_point)
            geocoded_count = sum(1 for e in all_entities if e.coordinates)
            logger.info(f"Geocoded entities: {geocoded_count} now have coordinates")

        # Cluster coordinates and keep largest cluster
        cluster_info = {}
        if self.enable_clustering:
            logger.info("Clustering coordinates...")
            all_entities, cluster_info = self.clusterer.cluster_entities(all_entities)
            logger.info(
                f"Clustering complete: {len(cluster_info)} clusters found, keeping largest cluster",
            )

        # Deduplicate, filter by confidence, and rank
        unique_entities = self._deduplicate_entities(all_entities)

        # Log entity types before filtering
        entity_type_counts = {}
        for e in unique_entities:
            entity_type_counts[e.entity_type] = entity_type_counts.get(e.entity_type, 0) + 1
        logger.info(f"Entity types found: {entity_type_counts}")

        # Filter by minimum confidence threshold
        # NOTE: Coordinates will bypass this later in adapters.py
        confident_entities = [
            e for e in unique_entities if e.confidence >= self.config.MIN_CONFIDENCE
        ]

        if len(confident_entities) < len(unique_entities):
            filtered_count = len(unique_entities) - len(confident_entities)
            logger.info(
                f"Filtered out {filtered_count} entities with confidence < {self.config.MIN_CONFIDENCE}",
            )
        else:
            logger.info(f"All {len(unique_entities)} entities meet confidence threshold")

        ranked_entities = self._rank_entities(confident_entities)

        metadata = ExtractionMetadata(
            total_sections_processed=sections_processed,
            average_text_quality=0.0,  # Updated later
            section_quality_scores={},  # Updated later
            total_entities=len(ranked_entities),
            coordinates=sum(1 for e in ranked_entities if e.coordinates),
            clusters=cluster_info.get("total_clusters", 0),
            locations=sum(
                1 for e in ranked_entities if e.entity_type in ["LOC", "GPE"] and e.coordinates
            ),
        )

        # Add quality assessment to metadata
        avg_quality = 0.0
        quality_scores_dict = {}
        if self.enable_quality_assessment and section_quality_scores:
            avg_quality = sum(q.overall_score for q in section_quality_scores.values()) / len(
                section_quality_scores,
            )
            quality_scores_dict = {
                section: {
                    "overall": round(score.overall_score, 3),
                    "char_ratio": round(score.char_ratio, 3),
                    "word_completeness": round(score.word_completeness, 3),
                    "encoding_health": round(score.encoding_health, 3),
                }
                for section, score in section_quality_scores.items()
            }
            logger.info(f"Average text quality: {avg_quality:.3f}")

        logger.info(f"Extraction complete: {len(ranked_entities)} total entities")

        return ExtractionResult(
            pdf_path=pdf_path,
            entities=ranked_entities,
            total_sections_processed=sections_processed,
            extraction_metadata=metadata,
            doc=doc,
            title=title,
            cluster_info=cluster_info,
            average_text_quality=avg_quality,
            section_quality_scores=quality_scores_dict,
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
                        logger.info(
                            f"Using title location '{entity.text}' as geocoding bias: {coords}",
                        )
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
        """Rank entities by relevance for study site identification.

        - Multi-factor scoring system that strongly prioritizes coordinates.
        - Quick Wins: Context-aware filtering, keyword boosting, caption prioritization.
        """

        def score(e: GeoEntity) -> float:
            # Extraction method quality (0-100 points)
            extraction_quality = {
                "COORDINATE": 100,  # Direct coordinates - highest priority
                "table_coordinate": 100,  # Table coordinates (if we add detection)
                "caption_coordinate": 75,  # From captions
                "SPATIAL_RELATION": 40,  # "10km north of X"
                "GPE": 50,  # Geocoded specific place
                "LOC": 25,  # Geocoded general location
            }

            # Section priority (0-100 points)
            section_priority = {
                "data and methods": 100,
                "materials": 100,
                "study area": 95,
                "study site": 95,
                "results": 70,
                "title": 60,  # Lower: often general location
                "abstract": 70,
                "figure": 85,  # Figures are high-quality sources
                "caption": 80,  # Captions are high-quality sources
                "introduction": 40,
                "discussions": 30,
                "conclusions": 20,
                "references": 5,  # Almost exclude references
                "bibliography": 5,  # Almost exclude bibliography
            }

            # Confidence multiplier (0.7-1.5x)
            if e.confidence >= 0.95:
                multiplier = 1.5
            elif e.confidence >= 0.80:
                multiplier = 1.2
            elif e.confidence >= 0.60:
                multiplier = 1.0
            else:
                multiplier = 0.7

            # Validation bonuses
            validation_bonus = 0

            # Has coordinates (explicit location)
            if e.coordinates:
                validation_bonus += 20

            # Has context (site name or description)
            if e.context and len(e.context) > 20:
                validation_bonus += 10

            # Check if in table (from context)
            if "table" in e.context.lower() or "tab" in e.section.lower():
                validation_bonus += 5
                extraction_quality["COORDINATE"] = 100  # Upgrade to table_coordinate

            # Figure/caption prioritization
            context_lower = e.context.lower()
            if "figure" in context_lower or "fig" in context_lower or "fig." in context_lower:
                validation_bonus += 15  # Figures are high-quality sources

            if "caption" in context_lower:
                validation_bonus += 10

            # Contextual keyword boosting (high-value keywords)
            # Enhanced with stronger emphasis on study site indicators
            # Increased weights for better detection of actual study sites

            # Tier 1: Very high confidence study site indicators (70 points - increased from 50)
            tier1_keywords = [
                "study site",
                "study area",
                "study location",
                "our study site",
                "our study area",
                "study sites were",
                "study area was",
                "sites were located",
                "area was located",
                "data collection site",
                "data collection area",
                "collection site",
                "collection station",
            ]

            # Tier 2: High confidence field work indicators (55 points - increased from 40)
            tier2_keywords = [
                "sampling site",
                "sampling location",
                "sampling station",
                "sample site",
                "sample location",
                "sample collection",
                "samples were collected",
                "field site",
                "field station",
                "research site",
                "research station",
                "research area",
                "experimental site",
                "observation site",
                "monitoring site",
                "monitoring station",
                "data collection",
                "collected at",
                "measurement site",
                "survey site",
                "our site",
                "our sites",
                "our location",
            ]

            # Tier 3: Medium confidence location indicators (40 points - increased from 30)
            tier3_keywords = [
                "plot",
                "transect",
                "quadrat",
                "study region",
                "sites",
                "location",
                "locations",
                "station",
                "stations",
                "site",
            ]

            # Apply tier-based bonuses (only one tier applies)
            for keyword in tier1_keywords:
                if keyword in context_lower:
                    validation_bonus += 70  # Increased from 50
                    break
            else:
                for keyword in tier2_keywords:
                    if keyword in context_lower:
                        validation_bonus += 55  # Increased from 40
                        break
                else:
                    for keyword in tier3_keywords:
                        if keyword in context_lower:
                            validation_bonus += 40  # Increased from 30
                            break

            # Penalty factors
            penalties = 0

            # Low precision check (for coordinates)
            if e.entity_type == "COORDINATE" and e.coordinates:
                lat, lon = e.coordinates
                lat_decimals = len(str(lat).split(".")[-1]) if "." in str(lat) else 0
                lon_decimals = len(str(lon).split(".")[-1]) if "." in str(lon) else 0
                if lat_decimals < 2 or lon_decimals < 2:
                    penalties -= 20

            # No context penalty (but not for table coordinates)
            if not (e.context or len(e.context) < 10) and "table" not in e.section.lower():
                penalties -= 10

            # Generic location penalty
            if e.entity_type in ["LOC", "GPE"] and len(e.text) < 3:
                penalties -= 15

            # Contextual keyword penalties (low-value/citation keywords)
            negative_keywords = [
                "et al",
                "previous study",
                "earlier work",
                "prior study",
                "reported by",
                "described by",
                "according to",
                "compared to",
                "similar to",
                "literature",
                "author",
                "affiliation",
                "department",
                "university",
                "address",
                "correspondence",
                "laboratory",
                "institute",
                "institution",
                "research center",
                "research centre",
                "funded by",
                "supported by",
                "grant",
            ]

            for keyword in negative_keywords:
                if keyword in context_lower:
                    penalties -= 25  # Heavy penalty for citations/affiliations
                    break  # Only apply once

            # Reference section filtering (additional penalty beyond section_priority)
            if e.section.lower() in ["references", "bibliography", "reference"]:
                penalties -= 50  # Almost eliminate references section

            # Calculate final score
            section_score = 0
            for k, v in section_priority.items():
                if e.section.lower() in k:
                    section_score = v
                    break
            base_score = extraction_quality.get(e.entity_type, 20) + section_score
            return (base_score * multiplier) + validation_bonus + penalties

        return sorted(entities, key=score, reverse=True)
