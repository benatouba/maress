from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING

from geopy.point import Point

from app.nlp.bounding_box_extractor import BoundingBoxExtractor, get_bounding_box_extractor
from app.nlp.clustering import CoordinateClusterer
from app.nlp.context_extraction import ContextExtractor
from app.nlp.context_filter import ContextFilter, get_context_filter
from app.nlp.domain_models import ExtractionMetadata, ExtractionResult, GeoEntity
from app.nlp.extractors import BaseEntityExtractor
from app.nlp.geocoding import get_geocoder
from app.nlp.model_config import ModelConfig
from app.nlp.nlp_logger import logger
from app.nlp.pdf_parser import PDFParser
from app.nlp.quality_assessment import TextQualityAssessor
from app.nlp.section_classifier import SectionClassifier, get_section_classifier
from app.nlp.spatial_relation_resolver import SpatialRelationResolver, get_spatial_relation_resolver
from app.nlp.table_extractor import TableCoordinateExtractor
from app.nlp.temporal_filter import TemporalContextFilter, TemporalContext, get_temporal_filter
from app.nlp.location_name_handler import LocationNameHandler, get_location_name_handler
from app.nlp.confidence_scorer import apply_enhanced_scoring
from app.nlp.coreference_resolver import (
    LocationCoreferenceResolver,
    AbbreviationExpander,
    get_coreference_resolver,
    get_abbreviation_expander,
)
from app.nlp.uncertainty_detector import UncertaintyDetector, get_uncertainty_detector
from app.nlp.validation import ExtractionValidator, get_validator

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
        enable_context_filtering: bool = True,
        enable_bounding_box_extraction: bool = True,
        enable_ml_section_classifier: bool = True,
        enable_spatial_resolution: bool = True,
        enable_temporal_filtering: bool = True,
        enable_location_name_merging: bool = True,
        enable_coreference_resolution: bool = True,
        enable_abbreviation_expansion: bool = True,
        enable_uncertainty_detection: bool = True,
        enable_validation: bool = True,
        enable_vision_extraction: bool = False,
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
            enable_context_filtering: Enable context-based filtering (Priority 1)
            enable_bounding_box_extraction: Enable bounding box extraction (Priority 2)
            enable_ml_section_classifier: Enable ML-based section classification (Priority 2)
            enable_spatial_resolution: Enable spatial relation resolution (Priority 3)
            enable_temporal_filtering: Enable temporal context filtering (Priority 3)
            enable_location_name_merging: Enable merging compound location names (Priority 3)
            enable_coreference_resolution: Enable coreference resolution (Priority 4)
            enable_abbreviation_expansion: Enable abbreviation expansion (Priority 4)
            enable_uncertainty_detection: Enable uncertainty detection (Priority 4)
            enable_validation: Enable validation and quality assurance (Priority 4)
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
        self.enable_context_filtering = enable_context_filtering
        self.enable_bounding_box_extraction = enable_bounding_box_extraction
        self.enable_ml_section_classifier = enable_ml_section_classifier
        self.enable_spatial_resolution = enable_spatial_resolution
        self.enable_temporal_filtering = enable_temporal_filtering
        self.enable_location_name_merging = enable_location_name_merging
        self.enable_coreference_resolution = enable_coreference_resolution
        self.enable_abbreviation_expansion = enable_abbreviation_expansion
        self.enable_uncertainty_detection = enable_uncertainty_detection
        self.enable_validation = enable_validation
        self.enable_vision_extraction = enable_vision_extraction

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
        if enable_context_filtering:
            self.context_filter = get_context_filter()
        if enable_bounding_box_extraction:
            self.bbox_extractor = get_bounding_box_extractor()
        if enable_ml_section_classifier:
            self.section_classifier = get_section_classifier(use_ml=True)
        if enable_spatial_resolution:
            self.spatial_resolver = get_spatial_relation_resolver()
        if enable_temporal_filtering:
            self.temporal_filter = get_temporal_filter()
        if enable_location_name_merging:
            self.location_handler = get_location_name_handler()
        if enable_coreference_resolution:
            self.coref_resolver = get_coreference_resolver()
        if enable_abbreviation_expansion:
            self.abbr_expander = get_abbreviation_expander()
        if enable_uncertainty_detection:
            self.uncertainty_detector = get_uncertainty_detector()
        if enable_validation:
            self.validator = get_validator()
        if enable_vision_extraction:
            from app.nlp.vision_extractor import VisionMapExtractor

            self.vision_extractor = VisionMapExtractor()

    def extract_from_pdf(self, pdf_path: Path, title: str | None = None) -> ExtractionResult:
        """Complete extraction pipeline for a PDF improvements.

        Pipeline steps:
        - Parse PDF (with improved sentence boundaries)
        - Extract title location for geocoding bias ONLY (not included in results)
        - Extract from text sections (with quality assessment)
        - Extract from tables
        - Geocode location entities
        - Cluster coordinates and retain top geographic clusters
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

        stage_timings_ms: dict[str, float] = {}

        def _record_timing(stage: str, started_at: float) -> None:
            stage_timings_ms[stage] = round((perf_counter() - started_at) * 1000.0, 2)

        # Parse PDF
        stage_start = perf_counter()
        doc = self.pdf_parser.parse(pdf_path)
        _record_timing("parse_pdf", stage_start)
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
        stage_start = perf_counter()
        section_quality_scores = {}
        layout_spans = doc.spans.get("layout", [])
        logger.info(f"Found {len(layout_spans)} layout spans in PDF")

        text_spans = [s for s in layout_spans if s.label_ in {"text", "image"}]
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
        _record_timing("extract_text_sections", stage_start)

        # Extract from tables
        if self.enable_table_extraction:
            stage_start = perf_counter()
            table_spans = [s for s in doc.spans.get("layout", []) if s.label_ == "table"]
            if table_spans:
                logger.info(f"Processing {len(table_spans)} tables")
                table_entities = self.table_extractor.extract_from_spans(table_spans)
                all_entities.extend(table_entities)
                logger.info(f"Extracted {len(table_entities)} entities from tables")
            _record_timing("table_extraction", stage_start)

        # Extract coordinates from map images using local OCR
        if self.enable_vision_extraction:
            stage_start = perf_counter()
            vision_entities = self.vision_extractor.extract_from_pdf(pdf_path)
            if vision_entities:
                all_entities.extend(vision_entities)
                logger.info(f"Extracted {len(vision_entities)} entities from map images")
            _record_timing("vision_extraction", stage_start)

        # Extract bounding boxes (Priority 2 improvement)
        # Looks for coordinate ranges that define study area extent
        if self.enable_bounding_box_extraction:
            stage_start = perf_counter()
            bbox_entities = self._extract_bounding_boxes(text_spans)
            if bbox_entities:
                all_entities.extend(bbox_entities)
                logger.info(f"Extracted {len(bbox_entities)} bounding box entities")
            _record_timing("bounding_box_extraction", stage_start)

        # Context-based filtering (Priority 1 improvement)
        # Remove entities from references, affiliations, captions, etc.
        if self.enable_context_filtering:
            stage_start = perf_counter()
            pre_filter_count = len(all_entities)
            all_entities = self.context_filter.filter_entities(all_entities)
            filtered_count = pre_filter_count - len(all_entities)
            if filtered_count > 0:
                logger.info(
                    f"Context filtering: removed {filtered_count} entities from "
                    f"reference/affiliation/caption contexts"
                )
            _record_timing("context_filtering", stage_start)

        # Merge compound location names (Priority 3 improvement)
        # Ensures "Paradise, United States" is recognized as one entity
        if self.enable_location_name_merging:
            stage_start = perf_counter()
            pre_merge_count = len(all_entities)
            all_entities = self.location_handler.post_process_entities(
                all_entities,
                merge=True,
                prioritize_long=True,
            )
            merged_count = pre_merge_count - len(all_entities)
            if merged_count > 0:
                logger.info(
                    f"Location name merging: merged {merged_count} fragmented location entities"
                )
            _record_timing("location_name_merging", stage_start)

        # Coreference resolution (Priority 4 improvement)
        # Resolve references like "the site" back to actual locations
        if self.enable_coreference_resolution:
            stage_start = perf_counter()
            pre_coref_count = len(all_entities)
            all_entities = self.coref_resolver.expand_entities_with_coreferences(
                doc,
                all_entities,
            )
            added_count = len(all_entities) - pre_coref_count
            if added_count > 0:
                logger.info(
                    f"Coreference resolution: added {added_count} entities from anaphoric references"
                )
            _record_timing("coreference_resolution", stage_start)

        # Abbreviation expansion (Priority 4 improvement)
        # Expand abbreviations in entity text before geocoding
        if self.enable_abbreviation_expansion:
            stage_start = perf_counter()
            all_entities = self._expand_abbreviations(all_entities)
            _record_timing("abbreviation_expansion", stage_start)

        # Geocode location entities (with caching and rate limiting)
        if self.enable_geocoding:
            stage_start = perf_counter()
            logger.info("Geocoding location entities...")
            all_entities = self.geocoder.geocode_entities(all_entities, title_bias_point)
            geocoded_count = sum(1 for e in all_entities if e.coordinates)
            logger.info(f"Geocoded entities: {geocoded_count} now have coordinates")
            _record_timing("geocoding", stage_start)

        # Resolve spatial relations to coordinates (Priority 3 improvement)
        # Converts "10 km north of Paris" to actual coordinates
        if self.enable_spatial_resolution:
            stage_start = perf_counter()
            all_entities = self._resolve_spatial_relations(all_entities)
            _record_timing("spatial_resolution", stage_start)

        # Temporal context filtering (Priority 3 improvement)
        # Remove historical/comparative references, keep current study sites
        if self.enable_temporal_filtering:
            stage_start = perf_counter()
            all_entities = self._filter_by_temporal_context(all_entities)
            _record_timing("temporal_filtering", stage_start)

        # Uncertainty detection (Priority 4 improvement)
        # Adjust confidence based on certainty markers in context
        if self.enable_uncertainty_detection:
            stage_start = perf_counter()
            all_entities = self.uncertainty_detector.adjust_entity_confidence(all_entities)
            _record_timing("uncertainty_detection", stage_start)

        stage_start = perf_counter()
        all_entities = apply_enhanced_scoring(all_entities, doc)
        _record_timing("enhanced_confidence_scoring", stage_start)

        # Cluster coordinates and retain strongest clusters
        cluster_info = {}
        if self.enable_clustering:
            stage_start = perf_counter()
            logger.info("Clustering coordinates...")
            all_entities, cluster_info = self.clusterer.cluster_entities(all_entities)
            logger.info(
                (
                    "Clustering complete: "
                    f"total={cluster_info.get('total_clusters', 0)} "
                    f"retained={cluster_info.get('retained_clusters', 0)}"
                ),
            )
            _record_timing("clustering", stage_start)

        # Deduplicate, filter by confidence, and rank
        stage_start = perf_counter()
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
        _record_timing("deduplicate_filter_rank", stage_start)

        filter_stats = {
            "sections_filtered": sections_filtered,
            "entities_before_confidence_filter": len(unique_entities),
            "entities_after_confidence_filter": len(confident_entities),
            "entities_filtered_by_confidence": filtered_count,
        }

        metadata = ExtractionMetadata(
            total_sections_processed=sections_processed,
            average_text_quality=0.0,  # Updated below after quality aggregation
            section_quality_scores={},  # Updated below after quality aggregation
            total_entities=len(ranked_entities),
            coordinates=sum(1 for e in ranked_entities if e.coordinates),
            clusters=cluster_info.get("total_clusters", 0),
            locations=sum(
                1 for e in ranked_entities if e.entity_type in ["LOC", "GPE"] and e.coordinates
            ),
            stage_timings_ms=stage_timings_ms,
            filter_statistics=filter_stats,
            entity_type_counts=entity_type_counts,
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

        metadata.average_text_quality = avg_quality
        metadata.section_quality_scores = quality_scores_dict

        logger.info(f"Extraction complete: {len(ranked_entities)} total entities")

        result = ExtractionResult(
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

        # Validation (Priority 4 improvement)
        # Perform quality assurance checks on the extraction result
        if self.enable_validation:
            stage_start = perf_counter()
            validation_report = self.validator.validate_result(result)
            if not validation_report.is_valid:
                logger.warning(
                    f"Validation found {len(validation_report.errors)} errors, "
                    f"attempting auto-fix..."
                )
                result = self.validator.auto_fix_issues(result, validation_report)
            if validation_report.warnings:
                logger.warning(
                    f"Validation warnings: {len(validation_report.warnings)} issues found"
                )
            _record_timing("validation", stage_start)
            metadata.stage_timings_ms = stage_timings_ms

        logger.info("Pipeline stage timings (ms): %s", stage_timings_ms)

        return result

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

    def _extract_bounding_boxes(self, text_spans: list) -> list[GeoEntity]:
        """Extract bounding boxes from text sections.

        Priority 2 improvement: Detect coordinate ranges that define
        study area extent (e.g., "45°N-47°N, 122°W-124°W").

        Args:
            text_spans: List of text spans from the document

        Returns:
            List of GeoEntity objects with bounding box information
        """
        entities: list[GeoEntity] = []

        for span in text_spans:
            section_name = self._classify_section(span)
            section_text = span.text.strip()

            if not section_text:
                continue

            # Only process study-site-relevant sections
            if not self._is_study_site_relevant_section(section_name):
                continue

            # Extract bounding boxes
            bboxes = self.bbox_extractor.extract(section_text)

            for bbox in bboxes:
                # Create GeoEntity with bounding box
                entity = GeoEntity(
                    text=bbox.source_text,
                    entity_type="BOUNDING_BOX",
                    context=f"Study area extent in {section_name}",
                    section=section_name,
                    confidence=bbox.confidence,
                    start_char=0,  # Position within section
                    end_char=len(bbox.source_text),
                    coordinates=bbox.center,  # Center point
                    bounding_box=(
                        bbox.min_lat,
                        bbox.max_lat,
                        bbox.min_lon,
                        bbox.max_lon,
                    ),
                )
                entities.append(entity)

                logger.debug(
                    f"Found bounding box in {section_name}: "
                    f"{bbox.min_lat:.2f}-{bbox.max_lat:.2f}°, "
                    f"{bbox.min_lon:.2f}-{bbox.max_lon:.2f}°"
                )

        return entities

    def _resolve_spatial_relations(
        self, entities: list[GeoEntity]
    ) -> list[GeoEntity]:
        """Resolve spatial relations to actual coordinates.

        Priority 3 improvement: Convert phrases like "10 km north of Paris"
        to actual geographic coordinates.

        Args:
            entities: List of entities to process

        Returns:
            List with spatial relations resolved to coordinates
        """
        resolved_entities: list[GeoEntity] = []
        resolved_count = 0

        for entity in entities:
            # Only process SPATIAL_RELATION entities without coordinates
            if entity.entity_type != "SPATIAL_RELATION" or entity.coordinates:
                resolved_entities.append(entity)
                continue

            # Try to resolve the spatial relation
            coords = self.spatial_resolver.resolve_entity(entity)

            if coords:
                # Create new entity with coordinates
                resolved_entity = GeoEntity(
                    text=entity.text,
                    entity_type="SPATIAL_RELATION",
                    context=entity.context,
                    section=entity.section,
                    confidence=entity.confidence,
                    start_char=entity.start_char,
                    end_char=entity.end_char,
                    coordinates=coords,
                )
                resolved_entities.append(resolved_entity)
                resolved_count += 1
                logger.debug(
                    f"Resolved spatial relation '{entity.text[:50]}...' to {coords}"
                )
            else:
                resolved_entities.append(entity)

        if resolved_count > 0:
            logger.info(
                f"Spatial resolution: resolved {resolved_count} spatial relations to coordinates"
            )

        return resolved_entities

    def _filter_by_temporal_context(
        self, entities: list[GeoEntity]
    ) -> list[GeoEntity]:
        """Filter entities based on temporal context.

        Priority 3 improvement: Remove entities that refer to historical studies,
        comparative references, or future/hypothetical locations. Keep only
        entities that refer to the current study's actual research sites.

        Args:
            entities: List of entities to filter

        Returns:
            Filtered list with only current study entities
        """
        pre_filter_count = len(entities)

        # Filter to keep current study and unknown (for low-confidence cases)
        filtered_entities = self.temporal_filter.filter_entities(
            entities,
            keep_contexts={TemporalContext.CURRENT_STUDY, TemporalContext.UNKNOWN},
        )

        removed_count = pre_filter_count - len(filtered_entities)
        if removed_count > 0:
            logger.info(
                f"Temporal filtering: removed {removed_count} historical/comparative references"
            )

        return filtered_entities

    def _expand_abbreviations(
        self, entities: list[GeoEntity]
    ) -> list[GeoEntity]:
        """Expand abbreviations in entity text.

        Priority 4 improvement: Normalizes location names by expanding
        common abbreviations before geocoding, improving match rates.

        Args:
            entities: List of entities

        Returns:
            Entities with expanded abbreviations
        """
        expanded: list[GeoEntity] = []
        expansion_count = 0

        for entity in entities:
            # Expand abbreviations in entity text
            original_text = entity.text
            expanded_text = self.abbr_expander.normalize_location_name(original_text)

            # Create new entity if text changed
            if expanded_text != original_text:
                expanded_entity = GeoEntity(
                    text=expanded_text,
                    entity_type=entity.entity_type,
                    context=entity.context,
                    section=entity.section,
                    confidence=entity.confidence,
                    start_char=entity.start_char,
                    end_char=entity.end_char,
                    coordinates=entity.coordinates,
                    bounding_box=entity.bounding_box,
                )
                expanded.append(expanded_entity)
                expansion_count += 1
                logger.debug(f"Expanded '{original_text}' -> '{expanded_text}'")
            else:
                expanded.append(entity)

        if expansion_count > 0:
            logger.info(
                f"Abbreviation expansion: expanded {expansion_count} entity names"
            )

        return expanded

    def _classify_section(self, span: Span) -> str:
        """Classify document section from span metadata.

        Uses ML classifier (Priority 2) when available, with rule-based fallback.
        Enhanced to better detect study site sections following linguistic patterns
        in earth system papers.
        """
        heading = str(getattr(span._, "heading", "")).lower()
        text_start = span.text.strip()[:200]  # Increased for better ML detection

        # Use ML classifier if available (Priority 2 improvement)
        if self.enable_ml_section_classifier and hasattr(self, "section_classifier"):
            label, confidence = self.section_classifier.classify(heading, text_start)
            if confidence >= 0.6:  # Only use ML prediction if confident
                logger.debug(f"ML classified section as '{label}' (confidence: {confidence:.2f})")
                return label

        # Fallback to rule-based classification
        heading_lower = heading.lower()
        text_lower = text_start[:100].lower()

        # Check for study site sections first (highest priority)
        study_site_keywords = [
            "study area", "study site", "study region", "study location",
            "field site", "field area", "site description", "area description",
            "sampling site", "sampling area", "sampling location",
            "experimental site", "observation site",
        ]
        for keyword in study_site_keywords:
            if keyword in heading_lower or keyword in text_lower[:80]:
                return "study_area"  # Normalize to study_area

        # Check for methods sections (high priority for study site mentions)
        if any(
            word in heading_lower for word in ["method", "material", "experiment", "data", "sampling"]
        ) or text_lower.startswith(("method", "data", "material", "sampling")):
            if "data collection" in heading_lower or "data collection" in text_lower[:50]:
                return "data"
            if "field method" in heading_lower or "field method" in text_lower[:50]:
                return "methods"
            return "methods"

        # Abstract
        elif "abstract" in heading_lower or text_lower.startswith("abstract"):
            return "abstract"

        # Results (lower priority)
        elif any(word in heading_lower for word in ["result", "finding"]) or text_lower.startswith(
            "result",
        ):
            return "results"

        # Discussion (low priority)
        elif "discuss" in heading_lower or text_lower.startswith("discuss"):
            return "discussion"

        # Conclusion (low priority)
        elif any(
            word in heading_lower for word in ["conclusion", "summary", "outlook"]
        ) or text_lower.startswith(("conclusion", "outlook")):
            return "conclusion"

        # Introduction (low priority)
        elif any(word in heading_lower for word in ["intro", "background"]) or text_lower.startswith(
            ("intro", "background"),
        ):
            return "introduction"

        # References (skip)
        elif any(
            word in heading_lower for word in ["reference", "bibliography", "acknowledgment"]
        ) or text_lower.startswith(("reference", "bibliograph", "acknowledgment")):
            return "references"

        return "other"

    def _is_study_site_relevant_section(self, section_name: str) -> bool:
        """Check if a section is relevant for study site extraction.

        Uses a blacklist approach: process all sections except those known
        to be irrelevant (references, acknowledgments). Section classification
        is used for confidence scoring, not filtering.

        Args:
            section_name: Classified section name

        Returns:
            True if section should be processed for study site extraction
        """
        section_normalized = section_name.lower().strip()

        # Only skip known-irrelevant sections
        skip_sections = {"references", "bibliography", "acknowledgments", "acknowledgements"}
        return section_normalized not in skip_sections

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
