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


# TODO: Combine this with heuristics
# TODO: Switch rules related stuff into spacy pipelines
# TODO: Use this version of PDF parser and pipeline in the API endpoints
# FIXME: Needs some refactoring of the models or parser output
class PipelineFactory:
    """Factory for creating configured extraction pipelines."""

    default_extractors: ClassVar[list[BaseEntityExtractor]] = []

    @staticmethod
    def create_pipeline(
        config: ModelConfig | None = None,
        extractors: list[BaseEntityExtractor] = default_extractors,
    ) -> StudySiteExtractionPipeline:
        """Create a fully configured extraction pipeline."""
        if config is None:
            config = ModelConfig()

        nlp = spacy.blank(config.SPACY_LANGUAGE)
        nlp.add_pipe("sentencizer")

        pdf_parser = SpacyLayoutPDFParser(nlp)

        # Initialize transformer pipeline
        ner_pipeline = pipeline(
            "ner",
            model=config.NER_MODEL_NAME,
            aggregation_strategy="simple",
            device=config.DEVICE,
        )

        if not extractors:
            extractors.extend(
                [
                    CoordinateExtractor(config),
                    SpatialRelationEntityExtractor(config),
                    SpaCyGeoExtractor(config),
                ],
            )

        return StudySiteExtractionPipeline(
            config=config,
            pdf_parser=pdf_parser,
            extractors=extractors,
        )
