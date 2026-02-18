"""NER training infrastructure for study site extraction.

This module provides tools for:
- Creating and managing training data
- Fine-tuning spaCy NER models
- Evaluating model performance
- Annotation helpers for user corrections

This is a Priority 3 improvement that enables continuous model improvement
based on user corrections and new training examples.
"""

from app.nlp.training.data_format import (
    EntityAnnotation,
    TrainingExample,
    TrainingDataset,
    create_spacy_training_data,
    create_from_extraction_result,
)
from app.nlp.training.evaluation import (
    EntityMetrics,
    EvaluationResult,
    evaluate_model,
    evaluate_with_spacy_scorer,
    compare_models,
    create_error_analysis,
)
from app.nlp.training.fine_tuning import (
    TrainingConfig,
    TrainingResult,
    NERFineTuner,
    quick_train,
)
from app.nlp.training.annotation_helper import (
    EntityCorrection,
    AnnotationHelper,
    create_training_dataset_from_results,
)
from app.nlp.location_name_handler import (
    create_compound_location_training_data,
)

__all__ = [
    # Data format
    "EntityAnnotation",
    "TrainingExample",
    "TrainingDataset",
    "create_spacy_training_data",
    "create_from_extraction_result",
    # Evaluation
    "EntityMetrics",
    "EvaluationResult",
    "evaluate_model",
    "evaluate_with_spacy_scorer",
    "compare_models",
    "create_error_analysis",
    # Fine-tuning
    "TrainingConfig",
    "TrainingResult",
    "NERFineTuner",
    "quick_train",
    # Annotation
    "EntityCorrection",
    "AnnotationHelper",
    "create_training_dataset_from_results",
    # Location names
    "create_compound_location_training_data",
]
