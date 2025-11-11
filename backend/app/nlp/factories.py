from typing import ClassVar

import spacy
from transformers import pipeline

from app.nlp.context_extraction import ContextExtractor
from app.nlp.extractors import (
    BaseEntityExtractor,
    CoordinateExtractor,
    SpaCyCoordinateExtractor,
    SpaCyGeoExtractor,
    SpatialRelationEntityExtractor,
)
from app.nlp.model_config import ModelConfig
from app.nlp.orchestrator import StudySiteExtractionPipeline
from app.nlp.pdf_parser import SpacyLayoutPDFParser
from app.nlp.quality_assessment import TextQualityAssessor
from app.nlp.sentence_boundaries import improve_sentence_boundaries


class PipelineFactory:
    """Factory for creating configured extraction pipelines.

    Creates pipelines with improvements enabled by default:

    Phase 1 (Infrastructure):
    - Geocoding with caching and rate limiting
    - Largest cluster selection
    - Table coordinate extraction

    Phase 2 (NLP Enhancements - Quick Wins):
    - Improved sentence boundary detection
    - Text quality assessment
    - Enriched coordinate context extraction
    """

    default_extractors: ClassVar[list[BaseEntityExtractor]] = []

    @staticmethod
    def create_pipeline(
        config: ModelConfig | None = None,
        extractors: list[BaseEntityExtractor] | None = None,
        enable_geocoding: bool = True,
        enable_clustering: bool = True,
        enable_table_extraction: bool = True,
        enable_improved_sentences: bool = True,
        enable_quality_assessment: bool = True,
        enable_enriched_context: bool = True,
        use_spacy_coordinate_matcher: bool = True,  # Phase 3: New option
    ) -> StudySiteExtractionPipeline:
        """Create a fully configured extraction pipeline.

        Args:
            config: Model configuration
            extractors: List of extractors (creates defaults if None)
            enable_geocoding: Enable geocoding with caching (Phase 1)
            enable_clustering: Enable largest cluster selection (Phase 1)
            enable_table_extraction: Enable table extraction (Phase 1)
            enable_improved_sentences: Enable improved sentence boundaries (Phase 2)
            enable_quality_assessment: Enable text quality assessment (Phase 2)
            enable_enriched_context: Enable enriched context extraction (Phase 2)
            use_spacy_coordinate_matcher: Enable spaCy-integrated coordinate matching (Phase 3)
                This handles malformed coordinates better than regex-only extraction.

        Returns:
            Configured extraction pipeline
        """
        if config is None:
            config = ModelConfig()

        nlp = spacy.blank(config.SPACY_LANGUAGE)
        nlp.add_pipe("sentencizer")

        # Phase 2: Improve sentence boundaries for scientific text
        if enable_improved_sentences:
            nlp = improve_sentence_boundaries(nlp)

        pdf_parser = SpacyLayoutPDFParser(nlp)

        # Initialize transformer pipeline (optional - can be disabled for speed)
        # ner_pipeline = pipeline(
        #     "ner",
        #     model=config.NER_MODEL_NAME,
        #     aggregation_strategy="simple",
        #     device=config.DEVICE,
        # )

        # Create default extractors if none provided
        if extractors is None:
            # Phase 3: Choose coordinate extractor based on flag
            if use_spacy_coordinate_matcher:
                coord_extractor = SpaCyCoordinateExtractor(config)
            else:
                coord_extractor = CoordinateExtractor(config)

            extractors = [
                coord_extractor,
                SpatialRelationEntityExtractor(config),
                SpaCyGeoExtractor(config),
            ]

        return StudySiteExtractionPipeline(
            config=config,
            pdf_parser=pdf_parser,
            extractors=extractors,
            enable_geocoding=enable_geocoding,
            enable_clustering=enable_clustering,
            enable_table_extraction=enable_table_extraction,
            enable_quality_assessment=enable_quality_assessment,
            enable_enriched_context=enable_enriched_context,
        )

    @staticmethod
    def create_pipeline_for_api(
        config: ModelConfig | None = None,
        use_spacy_coordinate_matcher: bool = True,  # Phase 3: Enabled by default
    ) -> StudySiteExtractionPipeline:
        """Create pipeline optimized for API use.

        This configuration:
        - Enables all Phase 1 improvements (geocoding, clustering, tables)
        - Enables all Phase 2 improvements (quality, sentences, context)
        - Enables Phase 3 spaCy coordinate matcher (handles malformed coordinates)
        - Uses fast extractors (no transformer models)
        - Optimized for production use

        Args:
            config: Model configuration
            use_spacy_coordinate_matcher: Use spaCy-integrated coordinate matching

        Returns:
            API-optimized pipeline
        """
        if config is None:
            config = ModelConfig()
            # Override some settings for API
            config.MIN_CONFIDENCE = 0.6  # Higher threshold for API
            config.CONTEXT_WINDOW = 100

        # Phase 3: Choose coordinate extractor
        if use_spacy_coordinate_matcher:
            coord_extractor = SpaCyCoordinateExtractor(config)
        else:
            coord_extractor = CoordinateExtractor(config)

        # Use only fast extractors
        extractors = [
            coord_extractor,
            SpatialRelationEntityExtractor(config),
            SpaCyGeoExtractor(config),  # Uses spaCy NER (fast)
        ]

        return PipelineFactory.create_pipeline(
            config=config,
            extractors=extractors,
            enable_geocoding=True,  # Phase 1
            enable_clustering=True,  # Phase 1
            enable_table_extraction=True,  # Phase 1
            use_spacy_coordinate_matcher=use_spacy_coordinate_matcher,  # Phase 3
        )
