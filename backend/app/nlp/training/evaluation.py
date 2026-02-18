"""Model evaluation utilities for NER and study site extraction.

Provides metrics and evaluation functions for:
- Entity-level precision, recall, and F1
- Token-level metrics
- Coordinate extraction accuracy
- Per-label performance breakdown
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import spacy
from spacy.scorer import Scorer
from spacy.tokens import Doc
from spacy.training import Example

from app.nlp.nlp_logger import logger
from app.nlp.training.data_format import TrainingDataset, TrainingExample


@dataclass
class EntityMetrics:
    """Metrics for a single entity type."""

    label: str
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0

    @property
    def precision(self) -> float:
        """Calculate precision."""
        if self.true_positives + self.false_positives == 0:
            return 0.0
        return self.true_positives / (self.true_positives + self.false_positives)

    @property
    def recall(self) -> float:
        """Calculate recall."""
        if self.true_positives + self.false_negatives == 0:
            return 0.0
        return self.true_positives / (self.true_positives + self.false_negatives)

    @property
    def f1(self) -> float:
        """Calculate F1 score."""
        if self.precision + self.recall == 0:
            return 0.0
        return 2 * (self.precision * self.recall) / (self.precision + self.recall)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "label": self.label,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
        }


@dataclass
class EvaluationResult:
    """Complete evaluation result for a model."""

    model_name: str
    dataset_name: str
    total_examples: int
    entity_metrics: dict[str, EntityMetrics] = field(default_factory=dict)
    overall_precision: float = 0.0
    overall_recall: float = 0.0
    overall_f1: float = 0.0
    coordinate_accuracy: float = 0.0
    errors: list[dict[str, Any]] = field(default_factory=list)

    def add_entity_metrics(self, metrics: EntityMetrics) -> None:
        """Add metrics for an entity type."""
        self.entity_metrics[metrics.label] = metrics

    def calculate_overall(self) -> None:
        """Calculate overall metrics from per-label metrics."""
        total_tp = sum(m.true_positives for m in self.entity_metrics.values())
        total_fp = sum(m.false_positives for m in self.entity_metrics.values())
        total_fn = sum(m.false_negatives for m in self.entity_metrics.values())

        if total_tp + total_fp > 0:
            self.overall_precision = total_tp / (total_tp + total_fp)
        if total_tp + total_fn > 0:
            self.overall_recall = total_tp / (total_tp + total_fn)
        if self.overall_precision + self.overall_recall > 0:
            self.overall_f1 = (
                2 * self.overall_precision * self.overall_recall
            ) / (self.overall_precision + self.overall_recall)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "model_name": self.model_name,
            "dataset_name": self.dataset_name,
            "total_examples": self.total_examples,
            "overall": {
                "precision": round(self.overall_precision, 4),
                "recall": round(self.overall_recall, 4),
                "f1": round(self.overall_f1, 4),
            },
            "coordinate_accuracy": round(self.coordinate_accuracy, 4),
            "per_label": {
                label: metrics.to_dict()
                for label, metrics in self.entity_metrics.items()
            },
            "error_count": len(self.errors),
        }

    def print_report(self) -> None:
        """Print a formatted evaluation report."""
        print(f"\n{'=' * 60}")
        print(f"Evaluation Report: {self.model_name}")
        print(f"Dataset: {self.dataset_name} ({self.total_examples} examples)")
        print(f"{'=' * 60}")
        print(f"\nOverall Metrics:")
        print(f"  Precision: {self.overall_precision:.4f}")
        print(f"  Recall:    {self.overall_recall:.4f}")
        print(f"  F1 Score:  {self.overall_f1:.4f}")

        if self.coordinate_accuracy > 0:
            print(f"\nCoordinate Extraction Accuracy: {self.coordinate_accuracy:.4f}")

        print(f"\nPer-Label Metrics:")
        print(f"  {'Label':<20} {'Precision':>10} {'Recall':>10} {'F1':>10}")
        print(f"  {'-' * 50}")
        for label in sorted(self.entity_metrics.keys()):
            metrics = self.entity_metrics[label]
            print(
                f"  {label:<20} {metrics.precision:>10.4f} "
                f"{metrics.recall:>10.4f} {metrics.f1:>10.4f}"
            )

        if self.errors:
            print(f"\nErrors ({len(self.errors)} total):")
            for error in self.errors[:5]:
                print(f"  - {error.get('message', 'Unknown error')}")
            if len(self.errors) > 5:
                print(f"  ... and {len(self.errors) - 5} more")

        print(f"\n{'=' * 60}\n")


def evaluate_model(
    model_path: str | Path,
    dataset: TrainingDataset,
    include_coordinate_accuracy: bool = True,
) -> EvaluationResult:
    """Evaluate a spaCy model on a test dataset.

    Args:
        model_path: Path to spaCy model
        dataset: Test dataset
        include_coordinate_accuracy: Whether to evaluate coordinate extraction

    Returns:
        EvaluationResult with metrics
    """
    # Load model
    nlp = spacy.load(model_path)
    model_name = str(model_path)

    result = EvaluationResult(
        model_name=model_name,
        dataset_name=dataset.name,
        total_examples=len(dataset),
    )

    # Track metrics per label
    label_metrics: dict[str, EntityMetrics] = defaultdict(
        lambda: EntityMetrics(label="")
    )

    coordinate_correct = 0
    coordinate_total = 0

    for example in dataset.examples:
        try:
            # Get predictions
            doc = nlp(example.text)
            predicted_ents = {(ent.start_char, ent.end_char, ent.label_) for ent in doc.ents}

            # Get gold entities
            gold_ents = {(e.start, e.end, e.label) for e in example.entities}

            # Calculate true positives, false positives, false negatives
            for ent in predicted_ents:
                label = ent[2]
                if label not in label_metrics:
                    label_metrics[label] = EntityMetrics(label=label)

                if ent in gold_ents:
                    label_metrics[label].true_positives += 1
                else:
                    label_metrics[label].false_positives += 1

            for ent in gold_ents:
                label = ent[2]
                if label not in label_metrics:
                    label_metrics[label] = EntityMetrics(label=label)

                if ent not in predicted_ents:
                    label_metrics[label].false_negatives += 1

            # Evaluate coordinate extraction
            if include_coordinate_accuracy:
                for entity in example.entities:
                    if entity.label == "COORDINATE":
                        coordinate_total += 1
                        # Check if we found a matching coordinate
                        for pred_ent in doc.ents:
                            if (
                                pred_ent.label_ == "COORDINATE"
                                and pred_ent.start_char == entity.start
                                and pred_ent.end_char == entity.end
                            ):
                                coordinate_correct += 1
                                break

        except Exception as e:
            result.errors.append({
                "message": str(e),
                "text": example.text[:100],
            })

    # Add metrics to result
    for label, metrics in label_metrics.items():
        metrics.label = label
        result.add_entity_metrics(metrics)

    # Calculate overall metrics
    result.calculate_overall()

    # Coordinate accuracy
    if coordinate_total > 0:
        result.coordinate_accuracy = coordinate_correct / coordinate_total

    return result


def evaluate_with_spacy_scorer(
    model_path: str | Path,
    dataset: TrainingDataset,
) -> dict[str, Any]:
    """Evaluate using spaCy's built-in Scorer.

    This provides additional metrics like token-level accuracy
    and uses spaCy's official evaluation methodology.

    Args:
        model_path: Path to spaCy model
        dataset: Test dataset

    Returns:
        Dictionary of spaCy scorer metrics
    """
    nlp = spacy.load(model_path)
    scorer = Scorer()

    examples = []
    for train_example in dataset.examples:
        # Create reference doc with gold annotations
        ref_doc = nlp.make_doc(train_example.text)
        ents = []
        for entity in train_example.entities:
            span = ref_doc.char_span(
                entity.start,
                entity.end,
                label=entity.label,
                alignment_mode="expand",
            )
            if span:
                ents.append(span)

        from spacy.util import filter_spans
        ref_doc.ents = filter_spans(ents)

        # Create predicted doc
        pred_doc = nlp(train_example.text)

        # Create Example
        example = Example(pred_doc, ref_doc)
        examples.append(example)

    # Get scores
    scores = scorer.score(examples)

    return {
        "ents_p": scores.get("ents_p", 0),
        "ents_r": scores.get("ents_r", 0),
        "ents_f": scores.get("ents_f", 0),
        "ents_per_type": scores.get("ents_per_type", {}),
    }


def compare_models(
    model_paths: list[str | Path],
    dataset: TrainingDataset,
) -> list[EvaluationResult]:
    """Compare multiple models on the same dataset.

    Args:
        model_paths: List of paths to spaCy models
        dataset: Test dataset

    Returns:
        List of EvaluationResult objects
    """
    results = []
    for path in model_paths:
        logger.info(f"Evaluating model: {path}")
        result = evaluate_model(path, dataset)
        results.append(result)

    # Print comparison
    print(f"\n{'=' * 70}")
    print("Model Comparison")
    print(f"{'=' * 70}")
    print(f"  {'Model':<30} {'Precision':>12} {'Recall':>12} {'F1':>12}")
    print(f"  {'-' * 66}")

    for result in sorted(results, key=lambda r: r.overall_f1, reverse=True):
        model_name = Path(result.model_name).name[:28]
        print(
            f"  {model_name:<30} {result.overall_precision:>12.4f} "
            f"{result.overall_recall:>12.4f} {result.overall_f1:>12.4f}"
        )

    print(f"{'=' * 70}\n")

    return results


def create_error_analysis(
    model_path: str | Path,
    dataset: TrainingDataset,
    output_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Generate detailed error analysis.

    Args:
        model_path: Path to spaCy model
        dataset: Test dataset
        output_path: Optional path to save analysis

    Returns:
        List of error cases with details
    """
    nlp = spacy.load(model_path)
    errors = []

    for i, example in enumerate(dataset.examples):
        doc = nlp(example.text)

        predicted_ents = {
            (ent.start_char, ent.end_char, ent.label_): ent.text
            for ent in doc.ents
        }
        gold_ents = {
            (e.start, e.end, e.label): example.text[e.start:e.end]
            for e in example.entities
        }

        # Find false positives
        for key, text in predicted_ents.items():
            if key not in gold_ents:
                errors.append({
                    "type": "false_positive",
                    "example_idx": i,
                    "text": text,
                    "label": key[2],
                    "start": key[0],
                    "end": key[1],
                    "context": example.text[max(0, key[0]-30):key[1]+30],
                    "source": example.source,
                })

        # Find false negatives
        for key, text in gold_ents.items():
            if key not in predicted_ents:
                errors.append({
                    "type": "false_negative",
                    "example_idx": i,
                    "text": text,
                    "label": key[2],
                    "start": key[0],
                    "end": key[1],
                    "context": example.text[max(0, key[0]-30):key[1]+30],
                    "source": example.source,
                })

    # Save if path provided
    if output_path:
        import json
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(errors, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved error analysis to {output_path}")

    return errors
