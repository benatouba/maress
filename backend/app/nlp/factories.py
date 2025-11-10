from typing import ClassVar

import spacy
from transformers import pipeline

from app.nlp.extractors import (
    BaseEntityExtractor,
    CoordinateExtractor,
    SpaCyGeoExtractor,
    SpatialRelationEntityExtractor,
)
from app.nlp.model_config import ModelConfig
from app.nlp.orchestrator import StudySiteExtractionPipeline
from app.nlp.pdf_parser import SpacyLayoutPDFParser


class PipelineFactory:
    """Factory for creating configured extraction pipelines.

    Creates pipelines with Phase 1 improvements enabled by default:
    - Geocoding with caching and rate limiting
    - Multi-cluster preservation
    - Table coordinate extraction
    """

    default_extractors: ClassVar[list[BaseEntityExtractor]] = []

    @staticmethod
    def create_pipeline(
        config: ModelConfig | None = None,
        extractors: list[BaseEntityExtractor] | None = None,
        enable_geocoding: bool = True,
        enable_clustering: bool = True,
        enable_table_extraction: bool = True,
    ) -> StudySiteExtractionPipeline:
        """Create a fully configured extraction pipeline.

        Args:
            config: Model configuration
            extractors: List of extractors (creates defaults if None)
            enable_geocoding: Enable geocoding with caching (Phase 1)
            enable_clustering: Enable multi-cluster preservation (Phase 1)
            enable_table_extraction: Enable table extraction (Phase 1)

        Returns:
            Configured extraction pipeline
        """
        if config is None:
            config = ModelConfig()

        nlp = spacy.blank(config.SPACY_LANGUAGE)
        nlp.add_pipe("sentencizer")

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
            extractors = [
                CoordinateExtractor(config),
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
        )

    @staticmethod
    def create_pipeline_for_api(
        config: ModelConfig | None = None,
    ) -> StudySiteExtractionPipeline:
        """Create pipeline optimized for API use.

        This configuration:
        - Enables all Phase 1 improvements
        - Uses fast extractors (no transformer models)
        - Optimized for production use

        Args:
            config: Model configuration

        Returns:
            API-optimized pipeline
        """
        if config is None:
            config = ModelConfig()
            # Override some settings for API
            config.MIN_CONFIDENCE = 0.6  # Higher threshold for API
            config.CONTEXT_WINDOW = 100

        # Use only fast extractors
        extractors = [
            CoordinateExtractor(config),
            SpatialRelationEntityExtractor(config),
            SpaCyGeoExtractor(config),  # Uses spaCy NER (fast)
        ]

        return PipelineFactory.create_pipeline(
            config=config,
            extractors=extractors,
            enable_geocoding=True,  # Phase 1
            enable_clustering=True,  # Phase 1
            enable_table_extraction=True,  # Phase 1
        )
