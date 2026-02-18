"""Annotation helper for creating training data.

Provides utilities for:
- Converting extraction results to training format
- Accepting user corrections
- Building training sets incrementally
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.nlp.domain_models import ExtractionResult, GeoEntity
from app.nlp.nlp_logger import logger
from app.nlp.training.data_format import (
    EntityAnnotation,
    TrainingDataset,
    TrainingExample,
)


@dataclass
class EntityCorrection:
    """A correction to an extracted entity."""

    original_text: str
    original_label: str
    corrected_label: str | None  # None means delete
    corrected_text: str | None  # None means keep original
    start: int
    end: int
    reason: str = ""


class AnnotationHelper:
    """Helper class for creating and managing training annotations."""

    def __init__(
        self,
        storage_path: Path = Path("data/training"),
        dataset_name: str = "study_site_annotations",
    ) -> None:
        """Initialize the annotation helper.

        Args:
            storage_path: Directory for storing annotation data
            dataset_path: Name of the dataset
        """
        self.storage_path = storage_path
        self.dataset_name = dataset_name
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self._dataset: TrainingDataset | None = None

    @property
    def dataset(self) -> TrainingDataset:
        """Get or load the dataset."""
        if self._dataset is None:
            self._dataset = self._load_or_create_dataset()
        return self._dataset

    def _load_or_create_dataset(self) -> TrainingDataset:
        """Load existing dataset or create new one."""
        dataset_path = self.storage_path / f"{self.dataset_name}.json"

        if dataset_path.exists():
            return TrainingDataset.load(dataset_path)

        return TrainingDataset(
            name=self.dataset_name,
            description="Study site extraction training data",
            labels=TrainingDataset.DEFAULT_LABELS,
        )

    def save(self) -> None:
        """Save the dataset to disk."""
        dataset_path = self.storage_path / f"{self.dataset_name}.json"
        self.dataset.save(dataset_path)
        logger.info(f"Saved dataset with {len(self.dataset)} examples to {dataset_path}")

    def add_from_extraction(
        self,
        result: ExtractionResult,
        corrections: list[EntityCorrection] | None = None,
        annotator: str = "user",
    ) -> int:
        """Add training examples from extraction result.

        Args:
            result: Extraction result from pipeline
            corrections: Optional list of corrections to apply
            annotator: Who created/verified the annotations

        Returns:
            Number of examples added
        """
        corrections_map = {}
        if corrections:
            for correction in corrections:
                key = (correction.start, correction.end, correction.original_label)
                corrections_map[key] = correction

        # Group entities by context for better training examples
        context_entities: dict[str, list[GeoEntity]] = {}
        for entity in result.entities:
            context = entity.context
            if context not in context_entities:
                context_entities[context] = []
            context_entities[context].append(entity)

        added_count = 0

        for context, entities in context_entities.items():
            # Build entity annotations with corrections applied
            annotations = []

            for entity in entities:
                key = (entity.start_char, entity.end_char, entity.entity_type)

                # Check for correction
                if key in corrections_map:
                    correction = corrections_map[key]
                    if correction.corrected_label is None:
                        # Entity was marked as incorrect, skip it
                        continue
                    label = correction.corrected_label
                else:
                    label = entity.entity_type

                # Find position in context
                start = context.find(entity.text)
                if start >= 0:
                    end = start + len(entity.text)
                    annotations.append(
                        EntityAnnotation(start=start, end=end, label=label)
                    )

            if annotations:
                example = TrainingExample(
                    text=context,
                    entities=annotations,
                    source=str(result.pdf_path),
                    section=entities[0].section if entities else None,
                    annotator=annotator,
                )

                # Validate before adding
                errors = example.validate_annotations()
                if not errors:
                    self.dataset.add_example(example)
                    added_count += 1
                else:
                    logger.warning(f"Skipping invalid example: {errors}")

        if added_count > 0:
            self.save()

        return added_count

    def add_manual_example(
        self,
        text: str,
        entities: list[tuple[int, int, str]],
        source: str | None = None,
        section: str | None = None,
        annotator: str = "manual",
    ) -> bool:
        """Add a manually annotated example.

        Args:
            text: Source text
            entities: List of (start, end, label) tuples
            source: Source document
            section: Document section
            annotator: Annotator identifier

        Returns:
            True if added successfully
        """
        annotations = [
            EntityAnnotation(start=start, end=end, label=label)
            for start, end, label in entities
        ]

        example = TrainingExample(
            text=text,
            entities=annotations,
            source=source,
            section=section,
            annotator=annotator,
        )

        errors = example.validate_annotations()
        if errors:
            logger.error(f"Invalid annotation: {errors}")
            return False

        self.dataset.add_example(example)
        self.save()
        return True

    def add_negative_example(
        self,
        text: str,
        source: str | None = None,
        section: str | None = None,
    ) -> bool:
        """Add a negative example (text with no entities).

        Useful for training model to avoid false positives.

        Args:
            text: Source text with no entities
            source: Source document
            section: Document section

        Returns:
            True if added successfully
        """
        example = TrainingExample(
            text=text,
            entities=[],
            source=source,
            section=section,
            annotator="negative",
        )

        self.dataset.add_example(example)
        self.save()
        return True

    def get_statistics(self) -> dict[str, Any]:
        """Get statistics about the current dataset."""
        report = self.dataset.validate()

        stats = {
            "total_examples": len(self.dataset),
            "total_entities": report["total_entities"],
            "entity_distribution": report["entity_counts"],
            "validation_errors": len(report["errors"]),
            "validation_warnings": len(report["warnings"]),
        }

        # Count by source
        sources: dict[str, int] = {}
        for example in self.dataset:
            source = example.source or "unknown"
            sources[source] = sources.get(source, 0) + 1
        stats["examples_by_source"] = sources

        # Count by annotator
        annotators: dict[str, int] = {}
        for example in self.dataset:
            annotator = example.annotator or "unknown"
            annotators[annotator] = annotators.get(annotator, 0) + 1
        stats["examples_by_annotator"] = annotators

        return stats

    def export_for_review(self, output_path: Path) -> None:
        """Export dataset in human-readable format for review.

        Args:
            output_path: Path for output file
        """
        review_data = []

        for i, example in enumerate(self.dataset):
            # Create annotated text view
            text = example.text
            annotations = []

            for entity in sorted(example.entities, key=lambda e: e.start):
                entity_text = text[entity.start:entity.end]
                annotations.append({
                    "text": entity_text,
                    "label": entity.label,
                    "position": f"[{entity.start}:{entity.end}]",
                })

            review_data.append({
                "id": i,
                "text": text,
                "annotations": annotations,
                "source": example.source,
                "section": example.section,
                "annotator": example.annotator,
            })

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(review_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Exported {len(review_data)} examples to {output_path}")

    def import_corrections(self, corrections_path: Path) -> int:
        """Import corrections from a reviewed file.

        Expects JSON with list of objects containing:
        - id: example index
        - corrections: list of {original_label, corrected_label, start, end}

        Args:
            corrections_path: Path to corrections file

        Returns:
            Number of corrections applied
        """
        with open(corrections_path, encoding="utf-8") as f:
            corrections_data = json.load(f)

        correction_count = 0
        examples = list(self.dataset.examples)

        for item in corrections_data:
            idx = item.get("id")
            if idx is None or idx >= len(examples):
                continue

            example = examples[idx]
            item_corrections = item.get("corrections", [])

            for correction in item_corrections:
                # Find and update the entity
                for entity in example.entities:
                    if (
                        entity.start == correction.get("start")
                        and entity.end == correction.get("end")
                        and entity.label == correction.get("original_label")
                    ):
                        new_label = correction.get("corrected_label")
                        if new_label:
                            # Create new entity with corrected label
                            entity.label = new_label
                            correction_count += 1
                        else:
                            # Mark for deletion
                            example.entities.remove(entity)
                            correction_count += 1
                        break

        if correction_count > 0:
            self.save()

        logger.info(f"Applied {correction_count} corrections")
        return correction_count


def create_training_dataset_from_results(
    results: list[ExtractionResult],
    dataset_name: str = "auto_generated",
    min_confidence: float = 0.8,
) -> TrainingDataset:
    """Create training dataset from multiple extraction results.

    Uses high-confidence extractions as pseudo-labels for training.

    Args:
        results: List of extraction results
        dataset_name: Name for the dataset
        min_confidence: Minimum confidence for including entities

    Returns:
        TrainingDataset
    """
    dataset = TrainingDataset(
        name=dataset_name,
        description="Auto-generated from extraction results",
        labels=TrainingDataset.DEFAULT_LABELS,
    )

    for result in results:
        # Group high-confidence entities by context
        context_entities: dict[str, list[GeoEntity]] = {}

        for entity in result.entities:
            if entity.confidence < min_confidence:
                continue

            context = entity.context
            if context not in context_entities:
                context_entities[context] = []
            context_entities[context].append(entity)

        # Create examples
        for context, entities in context_entities.items():
            annotations = []

            for entity in entities:
                start = context.find(entity.text)
                if start >= 0:
                    end = start + len(entity.text)
                    annotations.append(
                        EntityAnnotation(
                            start=start,
                            end=end,
                            label=entity.entity_type,
                        )
                    )

            if annotations:
                example = TrainingExample(
                    text=context,
                    entities=annotations,
                    source=str(result.pdf_path),
                    section=entities[0].section if entities else None,
                    annotator="auto",
                    quality_score=result.average_text_quality,
                )

                errors = example.validate_annotations()
                if not errors:
                    dataset.add_example(example)

    return dataset
