"""Fine-tuning utilities for spaCy NER models.

Provides infrastructure for:
- Preparing training configuration
- Running training with proper hyperparameters
- Saving and versioning trained models
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import spacy
from spacy.training import Example
from spacy.util import minibatch, compounding

from app.nlp.nlp_logger import logger
from app.nlp.training.data_format import TrainingDataset, create_spacy_training_data
from app.nlp.training.evaluation import evaluate_model


@dataclass
class TrainingConfig:
    """Configuration for model fine-tuning."""

    # Base model to fine-tune
    base_model: str = "en_core_web_lg"

    # Training hyperparameters
    n_iter: int = 30
    batch_size: int = 8
    dropout: float = 0.3
    learn_rate: float = 0.001

    # Early stopping
    patience: int = 5
    min_delta: float = 0.001

    # Components to train
    train_ner: bool = True
    freeze_vectors: bool = True

    # Output
    output_dir: Path = Path("models/trained")
    model_name: str = "study_site_ner"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "base_model": self.base_model,
            "n_iter": self.n_iter,
            "batch_size": self.batch_size,
            "dropout": self.dropout,
            "learn_rate": self.learn_rate,
            "patience": self.patience,
            "min_delta": self.min_delta,
            "train_ner": self.train_ner,
            "freeze_vectors": self.freeze_vectors,
            "output_dir": str(self.output_dir),
            "model_name": self.model_name,
        }


@dataclass
class TrainingResult:
    """Result of model training."""

    model_path: Path
    config: TrainingConfig
    training_time: float
    final_loss: float
    best_f1: float
    training_history: list[dict[str, float]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "model_path": str(self.model_path),
            "config": self.config.to_dict(),
            "training_time": round(self.training_time, 2),
            "final_loss": round(self.final_loss, 4),
            "best_f1": round(self.best_f1, 4),
            "history_length": len(self.training_history),
        }


class NERFineTuner:
    """Fine-tuner for spaCy NER models on study site extraction."""

    def __init__(self, config: TrainingConfig | None = None) -> None:
        """Initialize the fine-tuner.

        Args:
            config: Training configuration
        """
        self.config = config or TrainingConfig()

    def prepare_training_data(
        self,
        train_dataset: TrainingDataset,
        val_dataset: TrainingDataset | None = None,
    ) -> tuple[list[Example], list[Example] | None]:
        """Prepare training examples from datasets.

        Args:
            train_dataset: Training dataset
            val_dataset: Optional validation dataset

        Returns:
            Tuple of (train_examples, val_examples)
        """
        # Load base model for tokenization
        nlp = spacy.load(self.config.base_model)

        def dataset_to_examples(dataset: TrainingDataset) -> list[Example]:
            examples = []
            for item in dataset.examples:
                doc = nlp.make_doc(item.text)

                # Create entity spans
                ents = []
                for entity in item.entities:
                    span = doc.char_span(
                        entity.start,
                        entity.end,
                        label=entity.label,
                        alignment_mode="expand",
                    )
                    if span:
                        ents.append(span)

                # Handle overlapping spans
                from spacy.util import filter_spans
                doc.ents = filter_spans(ents)

                # Create Example with reference
                ref_doc = doc.copy()
                example = Example(doc, ref_doc)
                examples.append(example)

            return examples

        train_examples = dataset_to_examples(train_dataset)
        val_examples = None
        if val_dataset:
            val_examples = dataset_to_examples(val_dataset)

        return train_examples, val_examples

    def train(
        self,
        train_dataset: TrainingDataset,
        val_dataset: TrainingDataset | None = None,
    ) -> TrainingResult:
        """Train the NER model.

        Args:
            train_dataset: Training dataset
            val_dataset: Optional validation dataset for early stopping

        Returns:
            TrainingResult with trained model path and metrics
        """
        import time
        start_time = time.time()

        # Prepare examples
        logger.info(f"Preparing {len(train_dataset)} training examples...")
        train_examples, val_examples = self.prepare_training_data(
            train_dataset, val_dataset
        )

        # Load base model
        logger.info(f"Loading base model: {self.config.base_model}")
        nlp = spacy.load(self.config.base_model)

        # Get or create NER component
        if "ner" not in nlp.pipe_names:
            ner = nlp.add_pipe("ner")
        else:
            ner = nlp.get_pipe("ner")

        # Add labels from training data
        labels = set()
        for item in train_dataset.examples:
            for entity in item.entities:
                labels.add(entity.label)

        for label in labels:
            ner.add_label(label)

        logger.info(f"Training with labels: {labels}")

        # Freeze word vectors to prevent overfitting
        if self.config.freeze_vectors:
            for name, component in nlp.pipeline:
                if hasattr(component, "model"):
                    component.model.attrs["trainable"] = False

        # Setup optimizer
        optimizer = nlp.resume_training()
        if hasattr(optimizer, "learn_rate"):
            optimizer.learn_rate = self.config.learn_rate

        # Training loop
        training_history = []
        best_f1 = 0.0
        best_model_state = None
        patience_counter = 0
        final_loss = 0.0

        logger.info(f"Starting training for {self.config.n_iter} iterations...")

        for iteration in range(self.config.n_iter):
            losses = {}
            batches = minibatch(
                train_examples,
                size=compounding(4.0, self.config.batch_size, 1.001),
            )

            for batch in batches:
                nlp.update(
                    batch,
                    drop=self.config.dropout,
                    losses=losses,
                    sgd=optimizer,
                )

            final_loss = losses.get("ner", 0)

            # Evaluate on validation set if available
            val_f1 = 0.0
            if val_examples and val_dataset:
                result = evaluate_model(nlp, val_dataset)
                val_f1 = result.overall_f1

                # Early stopping check
                if val_f1 > best_f1 + self.config.min_delta:
                    best_f1 = val_f1
                    patience_counter = 0
                    # Save best model state
                    best_model_state = nlp.to_bytes()
                else:
                    patience_counter += 1

                if patience_counter >= self.config.patience:
                    logger.info(
                        f"Early stopping at iteration {iteration + 1} "
                        f"(no improvement for {self.config.patience} iterations)"
                    )
                    break

            training_history.append({
                "iteration": iteration + 1,
                "loss": final_loss,
                "val_f1": val_f1,
            })

            if (iteration + 1) % 5 == 0:
                logger.info(
                    f"Iteration {iteration + 1}: loss={final_loss:.4f}, "
                    f"val_f1={val_f1:.4f}"
                )

        # Restore best model if we did early stopping
        if best_model_state:
            nlp = spacy.blank("en")
            nlp.from_bytes(best_model_state)

        # Save model
        output_path = self._save_model(nlp, train_dataset, training_history)

        training_time = time.time() - start_time
        logger.info(f"Training complete in {training_time:.2f}s")

        return TrainingResult(
            model_path=output_path,
            config=self.config,
            training_time=training_time,
            final_loss=final_loss,
            best_f1=best_f1,
            training_history=training_history,
        )

    def _save_model(
        self,
        nlp: spacy.Language,
        dataset: TrainingDataset,
        history: list[dict[str, float]],
    ) -> Path:
        """Save trained model with metadata.

        Args:
            nlp: Trained spaCy model
            dataset: Training dataset (for metadata)
            history: Training history

        Returns:
            Path to saved model
        """
        # Create timestamped output directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_dir = self.config.output_dir / f"{self.config.model_name}_{timestamp}"
        model_dir.mkdir(parents=True, exist_ok=True)

        # Save model
        nlp.to_disk(model_dir)
        logger.info(f"Saved model to {model_dir}")

        # Save metadata
        metadata = {
            "model_name": self.config.model_name,
            "base_model": self.config.base_model,
            "created_at": timestamp,
            "training_dataset": dataset.name,
            "training_examples": len(dataset),
            "config": self.config.to_dict(),
            "training_history": history,
        }

        metadata_path = model_dir / "training_metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        # Create symlink to latest
        latest_link = self.config.output_dir / f"{self.config.model_name}_latest"
        if latest_link.exists():
            latest_link.unlink()
        latest_link.symlink_to(model_dir.name)

        return model_dir

    def continue_training(
        self,
        model_path: Path,
        additional_data: TrainingDataset,
        n_iter: int = 10,
    ) -> TrainingResult:
        """Continue training an existing model with additional data.

        Args:
            model_path: Path to existing model
            additional_data: New training examples
            n_iter: Number of additional iterations

        Returns:
            TrainingResult with updated model
        """
        # Update config
        original_n_iter = self.config.n_iter
        self.config.n_iter = n_iter
        self.config.base_model = str(model_path)

        try:
            result = self.train(additional_data)
            return result
        finally:
            self.config.n_iter = original_n_iter


def quick_train(
    train_dataset: TrainingDataset,
    val_dataset: TrainingDataset | None = None,
    base_model: str = "en_core_web_lg",
    n_iter: int = 30,
    output_dir: Path = Path("models/trained"),
) -> TrainingResult:
    """Quick function to train a model with sensible defaults.

    Args:
        train_dataset: Training dataset
        val_dataset: Optional validation dataset
        base_model: Base spaCy model
        n_iter: Number of training iterations
        output_dir: Output directory for trained model

    Returns:
        TrainingResult
    """
    config = TrainingConfig(
        base_model=base_model,
        n_iter=n_iter,
        output_dir=output_dir,
    )

    trainer = NERFineTuner(config)
    return trainer.train(train_dataset, val_dataset)
