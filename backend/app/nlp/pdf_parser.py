from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, override

from spacy_layout.layout import spaCyLayout

if TYPE_CHECKING:
    from spacy.language import Language
    from spacy.tokens import Doc


class TextCleaner(Protocol):
    """Protocol for text cleaning operations."""

    def clean(self, text: str) -> str:
        """Clean and normalise text."""
        ...


class PDFParser(ABC):
    """Abstract interface for PDF parsing (Dependency Inversion)."""

    @abstractmethod
    def parse(self, pdf_path: Path) -> Doc:
        """Parse PDF to spaCy Doc with layout information."""


class SpacyLayoutPDFParser(PDFParser):
    """Concrete implementation using spacy-layout."""

    def __init__(self, nlp: Language) -> None:
        """Initialize with spaCy language model."""
        self.nlp: Language = nlp
        self.layout: spaCyLayout = spaCyLayout(nlp)

    @override
    def parse(self, pdf_path: Path) -> Doc:
        """Parse PDF using spacy-layout."""
        return self.layout(str(pdf_path))
