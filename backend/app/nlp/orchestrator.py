from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from app.nlp.domain_models import ExtractionResult, GeoEntity
from app.nlp.extractors import BaseEntityExtractor
from app.nlp.model_config import ModelConfig
from app.nlp.pdf_parser import PDFParser

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
    ) -> None:
        """Initialize pipeline with dependencies.

        Args:
            config: Pipeline configuration
            pdf_parser: PDF parsing strategy
            extractors: List of entity extraction strategies
        """
        self.config: ModelConfig = config
        self.pdf_parser: PDFParser = pdf_parser
        self.extractors: list[BaseEntityExtractor] = extractors

    def extract_from_pdf(self, pdf_path: Path, title: str | None = None) -> ExtractionResult:
        """Complete extraction pipeline for a PDF.

        Args:
            pdf_path: Path to scientific PDF

        Returns:
            ExtractionResult with all geo-referenced entities
        """
        if not pdf_path.exists():
            msg = f"PDF not found: {pdf_path}"
            raise FileNotFoundError(msg)

        # Parse PDF
        doc = self.pdf_parser.parse(pdf_path)

        # Extract from sections
        all_entities: list[GeoEntity] = []
        sections_processed = 0

        if title:
            # Add title as a special section
            title_entities: list[GeoEntity] = []
            for extractor in self.extractors:
                entities = extractor.extract(text=title, section="title")
                title_entities.extend(entities)
            all_entities.extend(title_entities)
            sections_processed += 1

        for span in doc.spans.get("layout", []):
            if span.label_ != "text":
                continue

            # Classify section
            section_name = self._classify_section(span)
            section_text = span.text.strip()

            if not section_text:
                continue

            sections_processed += 1

            # Run all extractors
            for extractor in self.extractors:
                entities = extractor.extract(text=section_text, section=section_name)
                all_entities.extend(entities)

        # Deduplicate and rank
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
        }

        return ExtractionResult(
            pdf_path=pdf_path,
            entities=ranked_entities,
            total_sections_processed=sections_processed,
            extraction_metadata=metadata,
            doc=doc,
            title=title,
        )

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
