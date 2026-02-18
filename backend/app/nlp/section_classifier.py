"""ML-based section classification for scientific papers.

This module provides a machine learning classifier for detecting
document section types. It improves on rule-based classification by:
- Handling non-standard section naming
- Learning from text content patterns
- Supporting multiple languages (future)

The classifier uses a simple but effective approach:
1. TF-IDF vectorization of section text
2. Naive Bayes or SVM classification
3. Fallback to rule-based for edge cases
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import ClassVar

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline

from app.nlp.nlp_logger import logger


class SectionClassifier:
    """ML-based section classifier for scientific papers.

    Classifies document sections into categories relevant for
    study site extraction in earth science papers.
    """

    # Section labels ordered by relevance for study site extraction
    LABELS: ClassVar[list[str]] = [
        "study_area",      # Highest relevance
        "methods",         # High relevance
        "data",            # Medium relevance
        "results",         # Medium relevance
        "abstract",        # Lower relevance
        "introduction",    # Lower relevance
        "discussion",      # Low relevance
        "conclusion",      # Low relevance
        "references",      # Skip
        "acknowledgments", # Skip
        "other",           # Unknown
    ]

    # Training data for bootstrapping (can be extended)
    BOOTSTRAP_DATA: ClassVar[dict[str, list[str]]] = {
        "study_area": [
            "study area description site location",
            "the study was conducted in the region",
            "our field sites are located in",
            "the sampling area covers",
            "study site characteristics",
            "geographic setting of the study area",
            "the experimental site is situated",
            "field measurements were taken at",
            "the research area encompasses",
            "site description and location",
            "study region overview",
            "sampling locations were selected",
            "the study domain covers",
            "field station coordinates",
        ],
        "methods": [
            "methods and materials experimental design",
            "data collection procedures",
            "sampling methodology",
            "analytical methods used",
            "statistical analysis performed",
            "experimental setup and procedures",
            "measurement techniques",
            "data processing methods",
            "laboratory analysis",
            "field sampling protocol",
            "model configuration",
            "simulation setup",
            "calibration and validation",
        ],
        "data": [
            "data sources and availability",
            "dataset description",
            "input data used in this study",
            "observational data from",
            "satellite data products",
            "reanalysis data",
            "ground truth measurements",
            "in situ observations",
            "data quality control",
            "data preprocessing steps",
        ],
        "results": [
            "results show that",
            "our findings indicate",
            "analysis reveals",
            "we observed significant",
            "the measurements show",
            "model results demonstrate",
            "statistical results",
            "spatial patterns observed",
            "temporal trends identified",
            "comparison of results",
        ],
        "abstract": [
            "abstract summary",
            "this study investigates",
            "we present results from",
            "our research examines",
            "this paper describes",
            "key findings include",
            "the main objective",
            "we analyzed data from",
        ],
        "introduction": [
            "introduction background",
            "previous studies have shown",
            "the importance of understanding",
            "climate change impacts on",
            "research questions addressed",
            "objectives of this study",
            "literature review",
            "theoretical framework",
        ],
        "discussion": [
            "discussion of results",
            "our findings suggest",
            "compared to previous studies",
            "implications of these results",
            "limitations of this study",
            "interpretation of patterns",
            "possible explanations include",
            "future research directions",
        ],
        "conclusion": [
            "conclusion summary",
            "in summary we found",
            "this study demonstrates",
            "key conclusions include",
            "main findings of this research",
            "recommendations for future",
            "outlook and perspectives",
        ],
        "references": [
            "references bibliography cited",
            "author year journal volume",
            "doi https",
            "et al publication",
            "academic press springer",
            "isbn issn",
        ],
        "acknowledgments": [
            "acknowledgments funding",
            "we thank the reviewers",
            "this research was supported by",
            "grant number funding agency",
            "the authors acknowledge",
            "data provided by",
        ],
        "other": [
            "appendix supplementary",
            "table of contents",
            "list of figures",
            "author contributions",
            "competing interests",
            "data availability statement",
        ],
    }

    # Rule-based keywords for fallback
    KEYWORD_RULES: ClassVar[dict[str, list[str]]] = {
        "study_area": [
            "study area", "study site", "study region", "field site",
            "sampling site", "sampling area", "site description",
        ],
        "methods": [
            "method", "material", "procedure", "protocol", "experimental",
        ],
        "data": [
            "data", "dataset", "observation", "measurement",
        ],
        "results": [
            "result", "finding", "outcome",
        ],
        "abstract": [
            "abstract", "summary",
        ],
        "introduction": [
            "introduction", "background",
        ],
        "discussion": [
            "discussion", "interpretation",
        ],
        "conclusion": [
            "conclusion", "summary", "outlook",
        ],
        "references": [
            "reference", "bibliography", "citation", "literature",
        ],
        "acknowledgments": [
            "acknowledgment", "acknowledgement", "funding",
        ],
    }

    DATA_DIR: ClassVar[Path] = Path(__file__).parent / "data"
    MODEL_FILE: ClassVar[str] = "section_classifier.pkl"

    def __init__(self, use_ml: bool = True) -> None:
        """Initialize the section classifier.

        Args:
            use_ml: Whether to use ML classification (True) or rule-based only
        """
        self.use_ml = use_ml
        self.pipeline: Pipeline | None = None

        if use_ml:
            self._load_or_train_model()

    def _load_or_train_model(self) -> None:
        """Load existing model or train new one from bootstrap data."""
        model_path = self.DATA_DIR / self.MODEL_FILE

        if model_path.exists():
            try:
                with open(model_path, "rb") as f:
                    self.pipeline = pickle.load(f)
                logger.info("Loaded section classifier model from disk")
                return
            except Exception as e:
                logger.warning(f"Failed to load model: {e}, retraining...")

        # Train from bootstrap data
        self._train_from_bootstrap()

    def _train_from_bootstrap(self) -> None:
        """Train classifier from bootstrap data."""
        texts = []
        labels = []

        for label, examples in self.BOOTSTRAP_DATA.items():
            for example in examples:
                texts.append(example)
                labels.append(label)

        # Create pipeline
        self.pipeline = Pipeline([
            ("tfidf", TfidfVectorizer(
                ngram_range=(1, 2),
                max_features=1000,
                stop_words="english",
                lowercase=True,
            )),
            ("classifier", MultinomialNB(alpha=0.1)),
        ])

        # Train
        self.pipeline.fit(texts, labels)
        logger.info(f"Trained section classifier on {len(texts)} examples")

        # Save model
        try:
            model_path = self.DATA_DIR / self.MODEL_FILE
            model_path.parent.mkdir(parents=True, exist_ok=True)
            with open(model_path, "wb") as f:
                pickle.dump(self.pipeline, f)
            logger.info(f"Saved section classifier model to {model_path}")
        except Exception as e:
            logger.warning(f"Failed to save model: {e}")

    def classify(
        self,
        heading: str,
        text_start: str,
        min_confidence: float = 0.3,
    ) -> tuple[str, float]:
        """Classify a document section.

        Args:
            heading: Section heading text
            text_start: First ~100 characters of section text
            min_confidence: Minimum confidence for ML prediction

        Returns:
            Tuple of (section_label, confidence)
        """
        # Normalize inputs
        heading_lower = heading.lower().strip()
        text_lower = text_start.lower().strip()[:200]

        # Try rule-based first (high precision)
        rule_result = self._classify_by_rules(heading_lower, text_lower)
        if rule_result:
            return rule_result

        # Use ML if available
        if self.use_ml and self.pipeline:
            combined_text = f"{heading_lower} {text_lower}"
            try:
                prediction = self.pipeline.predict([combined_text])[0]
                probabilities = self.pipeline.predict_proba([combined_text])[0]
                confidence = float(max(probabilities))

                if confidence >= min_confidence:
                    return (prediction, confidence)
            except Exception as e:
                logger.debug(f"ML classification failed: {e}")

        # Fallback to "other"
        return ("other", 0.5)

    def _classify_by_rules(
        self, heading: str, text_start: str
    ) -> tuple[str, float] | None:
        """Classify using keyword rules.

        Returns:
            (label, confidence) or None if no rule matches
        """
        combined = f"{heading} {text_start}"

        for label, keywords in self.KEYWORD_RULES.items():
            for keyword in keywords:
                if keyword in combined:
                    # Higher confidence for heading matches
                    confidence = 0.95 if keyword in heading else 0.85
                    return (label, confidence)

        return None

    def add_training_example(self, text: str, label: str) -> None:
        """Add a new training example (for online learning).

        Args:
            text: Section text
            label: Correct label
        """
        if label not in self.LABELS:
            logger.warning(f"Unknown label: {label}")
            return

        # Add to bootstrap data
        if label not in self.BOOTSTRAP_DATA:
            self.BOOTSTRAP_DATA[label] = []
        self.BOOTSTRAP_DATA[label].append(text[:200].lower())

        # Retrain if we have enough new examples
        # (In production, you'd want a more sophisticated approach)
        logger.debug(f"Added training example for {label}")

    def retrain(self) -> None:
        """Retrain the model from current bootstrap data."""
        self._train_from_bootstrap()

    def get_study_site_relevance(self, label: str) -> float:
        """Get the relevance score for study site extraction.

        Args:
            label: Section label

        Returns:
            Relevance score (0.0 to 1.0)
        """
        relevance_scores = {
            "study_area": 1.0,
            "methods": 0.9,
            "data": 0.7,
            "results": 0.5,
            "abstract": 0.4,
            "introduction": 0.3,
            "discussion": 0.2,
            "conclusion": 0.2,
            "references": 0.0,
            "acknowledgments": 0.0,
            "other": 0.1,
        }
        return relevance_scores.get(label, 0.1)


# Singleton instance
_classifier: SectionClassifier | None = None


def get_section_classifier(use_ml: bool = True) -> SectionClassifier:
    """Get the section classifier instance.

    Args:
        use_ml: Whether to use ML classification

    Returns:
        SectionClassifier instance
    """
    global _classifier
    if _classifier is None:
        _classifier = SectionClassifier(use_ml=use_ml)
    return _classifier
