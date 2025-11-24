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
from app.nlp.pdf_parser import DoclingPDFParser
from app.nlp.quality_assessment import TextQualityAssessor
from app.nlp.sentence_boundaries import improve_sentence_boundaries


class PipelineFactory:
    """Factory for creating configured extraction pipelines.

    Creates pipelines with improvements enabled by default:

    Phase 1 (Infrastructure):
    - Geocoding with caching and rate limiting
    - Largest cluster selection
    - Table coordinate extraction
    - Component initialization at factory level (no runtime additions)

    Phase 2 (NLP Enhancements - Quick Wins):
    - Improved sentence boundary detection
    - Text quality assessment
    - Enriched coordinate context extraction
    """

    default_extractors: ClassVar[list[BaseEntityExtractor]] = []

    @staticmethod
    def _configure_spacy_components(nlp: spacy.language.Language, config: ModelConfig) -> spacy.language.Language:
        """Configure spaCy pipeline with custom components.

        Phase 1 Best Practice: All components are added at initialization time,
        not at runtime. This ensures:
        - Predictable pipeline configuration
        - No runtime mutations
        - Easy testing and debugging
        - Clear component ordering

        Component order (critical for correctness):
        1. abbreviation_detector (scispacy, if en_core_sci model) - Detects scientific abbreviations
        2. multiword_location_matcher (before="ner") - Prevents splitting multi-word locations
        3. ner (built-in) - Standard NER
        4. coordinate_matcher (after="ner") - Adds coordinate entities
        5. spatial_relation_matcher (after="ner") - Adds spatial relation entities
        6. study_site_dependency_matcher (last=True) - Uses all previous entities

        Args:
            nlp: spaCy Language object
            config: Model configuration

        Returns:
            Configured spaCy Language object
        """
        # Import component modules to register factories
        # These imports register the @Language.factory decorators
        from app.nlp.spacy_coordinate_matcher import CoordinateMatcher  # noqa: F401
        from app.nlp.spacy_multiword_location_matcher import MultiWordLocationMatcher  # noqa: F401
        from app.nlp.spacy_spatial_relation_matcher import SpatialRelationMatcher  # noqa: F401
        from app.nlp.spacy_study_site_dependency_matcher import StudySiteDependencyMatcher  # noqa: F401

        # ScispaCy Best Practice: Add AbbreviationDetector for scientific text models
        # This should be added early in the pipeline to resolve abbreviations before other components
        if config.SPACY_MODEL.startswith("en_core_sci"):
            try:
                from scispacy.abbreviation import AbbreviationDetector  # noqa: F401

                if "abbreviation_detector" not in nlp.pipe_names:
                    # Add abbreviation detector early, before NER
                    # This allows other components to benefit from abbreviation resolution
                    nlp.add_pipe("abbreviation_detector", first=True)
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.info("Added scispacy AbbreviationDetector to pipeline for model %s", config.SPACY_MODEL)
            except ImportError:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    "scispacy model detected (%s) but scispacy package not installed. "
                    "Install with: pip install scispacy",
                    config.SPACY_MODEL
                )

        # Add multiword location matcher BEFORE NER
        # This prevents NER from splitting multi-word location names
        if "multiword_location_matcher" not in nlp.pipe_names:
            nlp.add_pipe("multiword_location_matcher", before="ner")

        # Add coordinate matcher AFTER NER
        # This allows it to use NER entities for context
        if "coordinate_matcher" not in nlp.pipe_names:
            nlp.add_pipe("coordinate_matcher", after="ner")

        # Add spatial relation matcher AFTER NER
        # Detects patterns like "10 km north of X"
        if "spatial_relation_matcher" not in nlp.pipe_names:
            nlp.add_pipe("spatial_relation_matcher", after="ner")

        # Add study site dependency matcher LAST
        # Uses dependency parsing and all previous entities
        if "study_site_dependency_matcher" not in nlp.pipe_names:
            nlp.add_pipe("study_site_dependency_matcher", last=True)

        return nlp

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

        # Create lightweight blank model for PDF parsing (sentencizer only)
        pdf_nlp = spacy.blank(config.SPACY_LANGUAGE)
        pdf_nlp.add_pipe("sentencizer")

        # Phase 2: Improve sentence boundaries for scientific text
        if enable_improved_sentences:
            pdf_nlp = improve_sentence_boundaries(pdf_nlp)

        pdf_parser = DoclingPDFParser(pdf_nlp)

        # Load full spaCy model for entity extraction (shared across all extractors)
        # Keep NER, parser, tagger, and lemmatizer (needed for entity recognition, dependencies, POS, and LEMMA)
        # Only disable textcat for performance
        # NOTE: Tagger is required for custom matchers using POS/TAG attributes
        # NOTE: Lemmatizer is required for custom matchers using LEMMA attributes (Phase 1 patterns)
        shared_nlp = spacy.load(
            config.SPACY_MODEL,
            disable=["textcat"]
        )

        # Phase 1 Best Practice: Add all custom components upfront (no runtime additions)
        # This creates a predictable pipeline configuration that's easy to test and debug
        shared_nlp = PipelineFactory._configure_spacy_components(shared_nlp, config)

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

        # Inject shared spaCy instance into all extractors to reduce memory usage
        # This prevents each extractor from loading its own copy of the model
        for extractor in extractors:
            extractor.set_nlp(shared_nlp)

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
        config: ModelConfig,  # Required - no default
        use_spacy_coordinate_matcher: bool = True,
    ) -> StudySiteExtractionPipeline:
        """Create pipeline optimized for API use.

        This configuration:
        - Enables all Phase 1 improvements (geocoding, clustering, tables)
        - Enables all Phase 2 improvements (quality, sentences, context)
        - Enables Phase 3 spaCy coordinate matcher (handles malformed coordinates)
        - Uses fast extractors (no transformer models)
        - Optimized for production use

        Args:
            config: Model configuration (required, must be provided by caller)
            use_spacy_coordinate_matcher: Use spaCy-integrated coordinate matching

        Returns:
            API-optimized pipeline
        """

        # Choose coordinate extractor
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
            enable_geocoding=True,
            enable_clustering=True,
            enable_table_extraction=True,
            use_spacy_coordinate_matcher=use_spacy_coordinate_matcher,
        )
