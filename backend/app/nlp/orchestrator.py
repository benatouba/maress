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

        # Section filtering statistics
        sections_filtered = 0

        for span in text_spans:
            section_name = self._classify_section(span)
            section_text = span.text.strip()

            if not section_text:
                logger.debug(f"Skipping empty section: {section_name}")
                continue

            # NLP best practice: Filter to study-site-relevant sections only
            if not self._is_study_site_relevant_section(section_name):
                logger.debug(
                    f"Skipping section '{section_name}' - not relevant for study site extraction"
                )
                sections_filtered += 1
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

        logger.info(
            f"Extracted {len(all_entities)} entities from {sections_processed} sections "
            f"({sections_filtered} sections filtered out)"
        )
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
        # IMPORTANT: COORDINATE entities always pass through regardless of confidence
        # Other entities must meet the confidence threshold
        confident_entities = [
            e for e in unique_entities
            if e.entity_type == "COORDINATE" or e.confidence >= self.config.MIN_CONFIDENCE
        ]

        # Log filtering results
        coordinate_count = sum(1 for e in confident_entities if e.entity_type == "COORDINATE")
        other_count = len(confident_entities) - coordinate_count
        filtered_count = len(unique_entities) - len(confident_entities)

        logger.info(
            f"Confidence filtering: {coordinate_count} coordinates (always included), "
            f"{other_count} other entities passed threshold, "
            f"{filtered_count} filtered out"
        )

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
        """Classify document section from span metadata.

        Enhanced to better detect study site sections following linguistic patterns
        in earth system papers.
        """
        heading = str(getattr(span._, "heading", "")).lower()
        text_start = span.text.strip()[:100].lower()  # Increased for better detection

        # Check for study site sections first (highest priority)
        study_site_keywords = [
            "study area", "study site", "study region", "study location",
            "field site", "field area", "site description", "area description",
            "sampling site", "sampling area", "sampling location",
            "experimental site", "observation site",
        ]
        for keyword in study_site_keywords:
            if keyword in heading or keyword in text_start[:80]:
                return "study_area"  # Normalize to study_area

        # Check for methods sections (high priority for study site mentions)
        if any(
            word in heading for word in ["method", "material", "experiment", "data", "sampling"]
        ) or text_start.startswith(("method", "data", "material", "sampling")):
            if "data collection" in heading or "data collection" in text_start[:50]:
                return "data collection"
            if "field method" in heading or "field method" in text_start[:50]:
                return "field methods"
            return "methods"

        # Abstract
        elif "abstract" in heading or text_start.startswith("abstract"):
            return "abstract"

        # Results (lower priority)
        elif any(word in heading for word in ["result", "finding"]) or text_start.startswith(
            "result",
        ):
            return "results"

        # Discussion (low priority)
        elif "discuss" in heading or text_start.startswith("discuss"):
            return "discussion"

        # Conclusion (low priority)
        elif any(
            word in heading for word in ["conclusion", "summary", "outlook"]
        ) or text_start.startswith(("conclusion", "outlook")):
            return "conclusion"

        # Introduction (low priority)
        elif any(word in heading for word in ["intro", "background"]) or text_start.startswith(
            ("intro", "background"),
        ):
            return "introduction"

        # References (skip)
        elif any(
            word in heading for word in ["reference", "bibliography", "acknowledgment"]
        ) or text_start.startswith(("reference", "bibliograph", "acknowledgment")):
            return "references"

        return "other"

    def _is_study_site_relevant_section(self, section_name: str) -> bool:
        """Check if a section is relevant for study site extraction.

        Implements NLP best practice of focusing on sections where study sites
        are typically described in earth system papers.

        Args:
            section_name: Classified section name

        Returns:
            True if section should be processed for study site extraction
        """
        # Normalize section name
        section_normalized = section_name.lower().strip()

        # Check against study site sections list
        for relevant_section in self.config.STUDY_SITE_SECTIONS:
            if relevant_section.lower() in section_normalized:
                return True

        # Always skip references and acknowledgments
        if section_normalized in ["references", "bibliography", "acknowledgments", "acknowledgements"]:
            return False

        return False

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
        """Rank entities using model confidence scores.

        NLP best practice: Use confidence scores directly from models/extractors
        instead of complex heuristics. Linguistic patterns (DependencyMatcher) and
        spaCy NER already provide well-calibrated confidence scores.

        Priority order:
        1. COORDINATE entities (highest - explicit coordinates)
        2. STUDY_SITE entities (high - from linguistic patterns)
        3. Other entities (by model confidence)

        Args:
            entities: List of extracted entities

        Returns:
            Entities sorted by model confidence and entity type priority
        """

        def score(e: GeoEntity) -> tuple[int, float, bool]:
            """Return (priority, confidence, has_coordinates) for sorting.

            Priority levels (higher is better):
            - 3: COORDINATE (explicit coordinates are always most reliable)
            - 2: STUDY_SITE (from dependency patterns - high linguistic evidence)
            - 1: Everything else (NER, spatial relations, etc.)
            """
            # Entity type priority
            if e.entity_type == "COORDINATE":
                priority = 3
            elif e.entity_type == "STUDY_SITE":
                priority = 2
            else:
                priority = 1

            # Use model confidence directly (no heuristic modifications)
            confidence = e.confidence

            # Prefer entities with coordinates as tiebreaker
            has_coords = e.coordinates is not None

            return (priority, confidence, has_coords)

        # Sort by priority (desc), then confidence (desc), then has coordinates (desc)
        return sorted(entities, key=score, reverse=True)
