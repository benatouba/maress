"""Training data format and utilities for NER fine-tuning.

Provides a standardized format for training data that can be:
- Exported to spaCy's training format
- Used for model evaluation
- Stored in JSON for version control
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from pydantic import BaseModel, Field


class EntityAnnotation(BaseModel):
    """Single entity annotation in text."""

    start: int = Field(..., ge=0, description="Start character offset")
    end: int = Field(..., ge=0, description="End character offset")
    label: str = Field(..., min_length=1, description="Entity label")


class TrainingExample(BaseModel):
    """Single training example with text and entity annotations."""

    text: str = Field(..., min_length=1, description="Source text")
    entities: list[EntityAnnotation] = Field(
        default_factory=list, description="Entity annotations"
    )
    source: str | None = Field(
        default=None, description="Source document (PDF filename, DOI, etc.)"
    )
    section: str | None = Field(
        default=None, description="Document section (study_area, methods, etc.)"
    )
    annotator: str | None = Field(
        default=None, description="Who created this annotation"
    )
    quality_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Text quality score"
    )

    def to_spacy_format(self) -> tuple[str, dict[str, list[tuple[int, int, str]]]]:
        """Convert to spaCy training format.

        Returns:
            Tuple of (text, {"entities": [(start, end, label), ...]})
        """
        entities = [(e.start, e.end, e.label) for e in self.entities]
        return (self.text, {"entities": entities})

    def validate_annotations(self) -> list[str]:
        """Validate entity annotations.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        for i, entity in enumerate(self.entities):
            # Check bounds
            if entity.start >= len(self.text):
                errors.append(f"Entity {i}: start ({entity.start}) exceeds text length")
            if entity.end > len(self.text):
                errors.append(f"Entity {i}: end ({entity.end}) exceeds text length")
            if entity.start >= entity.end:
                errors.append(f"Entity {i}: start ({entity.start}) >= end ({entity.end})")

        # Check for overlapping entities
        sorted_entities = sorted(self.entities, key=lambda e: (e.start, e.end))
        for i in range(len(sorted_entities) - 1):
            current = sorted_entities[i]
            next_entity = sorted_entities[i + 1]
            if current.end > next_entity.start:
                errors.append(
                    f"Overlapping entities: '{self.text[current.start:current.end]}' "
                    f"and '{self.text[next_entity.start:next_entity.end]}'"
                )

        return errors


class TrainingDataset(BaseModel):
    """Collection of training examples for NER fine-tuning."""

    name: str = Field(..., description="Dataset name")
    version: str = Field(default="1.0.0", description="Dataset version")
    description: str = Field(default="", description="Dataset description")
    labels: list[str] = Field(
        default_factory=list, description="Valid entity labels"
    )
    examples: list[TrainingExample] = Field(
        default_factory=list, description="Training examples"
    )

    # Default labels for study site extraction
    DEFAULT_LABELS = [
        "LOC",  # Generic location
        "GPE",  # Geopolitical entity (country, city)
        "FAC",  # Facility (research station)
        "COORDINATE",  # Explicit coordinates
        "SPATIAL_RELATION",  # Relative location ("10 km north of...")
        "STUDY_SITE",  # Explicit study site mention
        "WATER_BODY",  # Ocean, sea, river, lake
        "GEO_FEATURE",  # Mountain, valley, canyon
        "BOUNDING_BOX",  # Coordinate range
    ]

    def add_example(self, example: TrainingExample) -> None:
        """Add a training example."""
        self.examples.append(example)

    def add_from_text(
        self,
        text: str,
        entities: list[tuple[int, int, str]],
        source: str | None = None,
        section: str | None = None,
    ) -> None:
        """Add example from text and entity tuples.

        Args:
            text: Source text
            entities: List of (start, end, label) tuples
            source: Source document
            section: Document section
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
        )
        self.add_example(example)

    def to_spacy_format(self) -> list[tuple[str, dict[str, list[tuple[int, int, str]]]]]:
        """Convert entire dataset to spaCy training format.

        Returns:
            List of (text, {"entities": [(start, end, label), ...]}) tuples
        """
        return [example.to_spacy_format() for example in self.examples]

    def validate(self) -> dict[str, Any]:
        """Validate the entire dataset.

        Returns:
            Validation report with errors and statistics
        """
        report = {
            "total_examples": len(self.examples),
            "total_entities": 0,
            "entity_counts": {},
            "errors": [],
            "warnings": [],
        }

        for i, example in enumerate(self.examples):
            # Validate individual example
            example_errors = example.validate_annotations()
            for error in example_errors:
                report["errors"].append(f"Example {i}: {error}")

            # Count entities
            for entity in example.entities:
                report["total_entities"] += 1
                label = entity.label
                report["entity_counts"][label] = report["entity_counts"].get(label, 0) + 1

                # Check label validity
                if self.labels and label not in self.labels:
                    report["warnings"].append(
                        f"Example {i}: Unknown label '{label}' (not in labels list)"
                    )

        # Check for label imbalance
        if report["entity_counts"]:
            counts = list(report["entity_counts"].values())
            max_count = max(counts)
            min_count = min(counts)
            if max_count > 10 * min_count:
                report["warnings"].append(
                    f"Label imbalance detected: ratio {max_count}/{min_count} > 10"
                )

        report["is_valid"] = len(report["errors"]) == 0

        return report

    def split(
        self,
        train_ratio: float = 0.8,
        seed: int = 42,
    ) -> tuple[TrainingDataset, TrainingDataset]:
        """Split dataset into train and test sets.

        Args:
            train_ratio: Proportion for training set
            seed: Random seed for reproducibility

        Returns:
            Tuple of (train_dataset, test_dataset)
        """
        import random

        random.seed(seed)
        examples = list(self.examples)
        random.shuffle(examples)

        split_idx = int(len(examples) * train_ratio)
        train_examples = examples[:split_idx]
        test_examples = examples[split_idx:]

        train_dataset = TrainingDataset(
            name=f"{self.name}_train",
            version=self.version,
            description=f"Training split of {self.name}",
            labels=self.labels,
            examples=train_examples,
        )

        test_dataset = TrainingDataset(
            name=f"{self.name}_test",
            version=self.version,
            description=f"Test split of {self.name}",
            labels=self.labels,
            examples=test_examples,
        )

        return train_dataset, test_dataset

    def save(self, path: Path) -> None:
        """Save dataset to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: Path) -> TrainingDataset:
        """Load dataset from JSON file."""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls.model_validate(data)

    def __iter__(self) -> Iterator[TrainingExample]:
        """Iterate over examples."""
        return iter(self.examples)

    def __len__(self) -> int:
        """Get number of examples."""
        return len(self.examples)


def create_spacy_training_data(
    dataset: TrainingDataset,
    output_path: Path,
) -> Path:
    """Create spaCy training data file.

    Converts dataset to spaCy's DocBin format for efficient training.

    Args:
        dataset: Training dataset
        output_path: Path for output .spacy file

    Returns:
        Path to created file
    """
    import spacy
    from spacy.tokens import DocBin

    # Use blank English model for tokenization
    nlp = spacy.blank("en")
    doc_bin = DocBin()

    for example in dataset.examples:
        doc = nlp.make_doc(example.text)

        # Add entity spans
        ents = []
        for entity in example.entities:
            span = doc.char_span(
                entity.start,
                entity.end,
                label=entity.label,
                alignment_mode="expand",
            )
            if span is not None:
                ents.append(span)

        # Handle overlapping spans
        try:
            doc.ents = ents
        except ValueError:
            # Overlapping entities - use filter_spans
            from spacy.util import filter_spans
            doc.ents = filter_spans(ents)

        doc_bin.add(doc)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc_bin.to_disk(output_path)

    return output_path


def create_from_extraction_result(
    result: Any,  # ExtractionResult - avoid circular import
    annotator: str = "auto",
) -> TrainingDataset:
    """Create training dataset from extraction results.

    This allows using extraction results (possibly corrected by users)
    as training data for model improvement.

    Args:
        result: ExtractionResult from pipeline
        annotator: Annotator identifier

    Returns:
        TrainingDataset with examples from extraction
    """
    from app.nlp.domain_models import ExtractionResult

    if not isinstance(result, ExtractionResult):
        raise TypeError("Expected ExtractionResult")

    dataset = TrainingDataset(
        name=f"extraction_{result.pdf_path.stem}",
        description=f"Auto-generated from {result.pdf_path.name}",
        labels=TrainingDataset.DEFAULT_LABELS,
    )

    # Group entities by section/context
    section_texts: dict[str, str] = {}
    section_entities: dict[str, list[tuple[int, int, str]]] = {}

    for entity in result.entities:
        section = entity.section
        if section not in section_texts:
            section_texts[section] = entity.context
            section_entities[section] = []

        # Find entity position in context
        context = entity.context
        start = context.find(entity.text)
        if start >= 0:
            end = start + len(entity.text)
            section_entities[section].append((start, end, entity.entity_type))

    # Create examples
    for section, text in section_texts.items():
        entities = section_entities.get(section, [])
        if entities:
            dataset.add_from_text(
                text=text,
                entities=entities,
                source=str(result.pdf_path),
                section=section,
            )

    return dataset
