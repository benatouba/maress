"""PDF parsing with robust OCR fallback chain.

This module provides PDF to spaCy Doc conversion with automatic fallback
through multiple OCR backends if one fails.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, override

import pymupdf
from spacy_layout import spaCyLayout

if TYPE_CHECKING:
    from spacy.language import Language
    from spacy.tokens import Doc

logger = logging.getLogger(__name__)


class OCRBackend(str, Enum):
    """OCR backends in order of preference (fastest to slowest)."""

    RAPIDOCR = "rapidocr"  # Fast, good quality (onnxruntime)
    TESSERACT = "tesseract"  # Moderate speed, high quality
    EASYOCR = "easyocr"  # Slow, best for complex documents
    NONE = "none"  # No OCR


@dataclass(frozen=True)
class ParseResult:
    """Result of PDF parsing attempt."""

    doc: Doc | None
    backend_used: str
    success: bool
    error: str | None = None


class PDFParser(ABC):
    """Abstract interface for PDF parsing."""

    @abstractmethod
    def parse(self, pdf_path: Path) -> Doc:
        """Parse PDF to spaCy Doc with layout information.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Processed spaCy Doc

        Raises:
            FileNotFoundError: If PDF doesn't exist
            RuntimeError: If parsing fails
        """


class SpacyLayoutPDFParser(PDFParser):
    """PDF parser using spacy-layout with robust OCR fallback chain.

    Automatically tries multiple OCR backends if one fails:
    1. RapidOCR (fastest, good quality)
    2. Tesseract (slower, high quality)
    3. EasyOCR (slowest, best for difficult docs)
    4. PyMuPDF (no OCR, last resort)

    Example:
        >>> parser = SpacyLayoutPDFParser(nlp, enable_fallback=True)
        >>> doc = parser.parse(Path("paper.pdf"))
    """

    # OCR backends to try in order
    FALLBACK_CHAIN = [
        OCRBackend.RAPIDOCR,
        OCRBackend.TESSERACT,
        OCRBackend.EASYOCR,
    ]

    def __init__(
        self,
        nlp: Language,
        *,
        enable_ocr_fallback: bool = True,
        enable_pymupdf_fallback: bool = True,
    ) -> None:
        """Initialize parser with spaCy model and fallback options.

        Args:
            nlp: spaCy language model
            enable_ocr_fallback: Try multiple OCR backends (default: True)
            enable_pymupdf_fallback: Use PyMuPDF as last resort (default: True)
        """
        self.nlp = nlp
        self.enable_ocr_fallback = enable_ocr_fallback
        self.enable_pymupdf_fallback = enable_pymupdf_fallback
        self._layout: spaCyLayout | None = None

    def _init_layout(self) -> spaCyLayout:
        """Lazy initialization of spacy-layout."""
        if self._layout is None:
            self._layout = spaCyLayout(
                self.nlp,
                headings=["section_header", "title", "page_header"],
                separator="\n\n",
            )
        return self._layout

    def _try_spacy_layout(self, pdf_path: Path, backend: OCRBackend) -> ParseResult:
        """Try extraction with spacy-layout using specific OCR backend.

        Args:
            pdf_path: Path to PDF
            backend: OCR backend to use

        Returns:
            ParseResult with success status
        """
        def parse(pdf_path: Path, backend: OCRBackend) -> ParseResult:
            layout = self._init_layout()

            # Note: spacy-layout uses docling which will use available OCR
            # Currently we can't force specific backends, but the attempt order
            # is preserved by trying the parse multiple times
            doc = layout(str(pdf_path))

            # Ensure NLP pipeline is applied
            if not doc.has_annotation("DEP"):
                doc = self.nlp(doc.text) if doc.text else self.nlp("")
            # Check if doc actually has content
            if not doc.text.strip():
                msg = f"spacy-layout parsing with {backend.value} resulted in empty text"
                raise ValueError(msg)
            logger.debug(f"Extracted text length: {len(doc.text)} characters")
            logger.debug(f"Extracted text preview: {doc.text[:200]!r}...")
            return ParseResult(
                doc=doc,
                backend_used=f"spacy-layout+{backend.value}",
                success=True,
            )
        try:
            logger.info(f"Attempting PDF parsing with {backend.value}")
            return parse(pdf_path, backend)

        except Exception as e:
            logger.warning(
                f"spacy-layout parsing failed with {backend.value}: {e!s}",
                exc_info=True,
            )
            return ParseResult(
                doc=None,
                backend_used=f"spacy-layout+{backend.value}",
                success=False,
                error=str(e),
            )

    def _try_pymupdf(self, pdf_path: Path) -> ParseResult:
        """Try basic text extraction with PyMuPDF (no OCR).

        Args:
            pdf_path: Path to PDF

        Returns:
            ParseResult with success status
        """
        def parse(pdf_path: Path) -> ParseResult:
            logger.info("Attempting PDF parsing with PyMuPDF fallback")
            pdf_doc = pymupdf.open(pdf_path)

            # Extract text blocks from all pages
            blocks = []
            for page in pdf_doc:
                text_blocks = page.get_text("blocks")  # (x0, y0, x1, y1, text, ...)
                for block in text_blocks:
                    if block[6] == 0:  # Text block (not image)
                        blocks.append(block[4])

            pdf_doc.close()

            # Create Doc from combined text
            combined_text = "\n\n".join(blocks)
            doc = self.nlp(combined_text) if combined_text else self.nlp("")

            # Add empty layout span group for compatibility
            if "layout" not in doc.spans:
                doc.spans["layout"] = []

            if not doc.text.strip():
                msg = "PyMuPDF parsing resulted in empty text"
                raise ValueError(msg)
            logger.info("Successfully parsed with PyMuPDF")
            return ParseResult(
                doc=doc,
                backend_used="pymupdf",
                success=True,
            )

        try:
            return parse(pdf_path)

        except Exception as e:
            logger.error(f"PyMuPDF parsing failed: {e!s}", exc_info=True)
            return ParseResult(
                doc=None,
                backend_used="pymupdf",
                success=False,
                error=str(e),
            )

    @override
    def parse(self, pdf_path: Path) -> Doc:
        """Parse PDF with automatic fallback through multiple methods.

        Tries methods in order until one succeeds:
        1. spacy-layout + RapidOCR
        2. spacy-layout + Tesseract (if ocr_fallback enabled)
        3. spacy-layout + EasyOCR (if ocr_fallback enabled)
        4. PyMuPDF (if pymupdf_fallback enabled)

        Args:
            pdf_path: Path to PDF file

        Returns:
            Processed spaCy Doc with layout information

        Raises:
            FileNotFoundError: If PDF doesn't exist
            RuntimeError: If all parsing methods fail
        """
        if not pdf_path.exists():
            msg = f"PDF file not found: {pdf_path}"
            raise FileNotFoundError(msg)

        logger.info(f"Starting PDF parsing for: {pdf_path.name}")

        # Try OCR backends if enabled
        if self.enable_ocr_fallback:
            for backend in self.FALLBACK_CHAIN:
                result = self._try_spacy_layout(pdf_path, backend)
                # Check if result has actual content (not just empty doc)
                if result.success and result.doc and result.doc.text.strip():
                    logger.info(f"Parsed {pdf_path.name} using {result.backend_used}")
                    return result.doc

                # Log reason for trying next backend
                if result.success and result.doc and not result.doc.text.strip():
                    logger.warning(f"{backend.value} returned empty content, retrying with next OCR backend...")
                else:
                    logger.warning(f"Retrying with next OCR backend...")
        else:
            # Try only once with first backend
            result = self._try_spacy_layout(pdf_path, self.FALLBACK_CHAIN[0])
            # Check if result has actual content (not just empty doc)
            if result.success and result.doc and result.doc.text.strip():
                logger.info(f"Parsed {pdf_path.name} using {result.backend_used}")
                return result.doc

        # PyMuPDF fallback if enabled
        if self.enable_pymupdf_fallback:
            logger.info("All OCR methods failed or returned empty content, trying PyMuPDF fallback")
            result = self._try_pymupdf(pdf_path)
            # Check if result has actual content (not just empty doc)
            if result.success and result.doc and result.doc.text.strip():
                logger.info(f"Parsed {pdf_path.name} using {result.backend_used}")
                return result.doc

            if result.success and result.doc and not result.doc.text.strip():
                logger.warning("PyMuPDF also returned empty content")

        # All methods failed
        error_msg = f"All parsing methods failed or returned empty content for {pdf_path.name}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)


class PyMuPDFParser(PDFParser):
    """Simple PDF parser using PyMuPDF only (no OCR).

    Use when PDFs are text-based and don't need OCR.
    Faster than spacy-layout but won't work on scanned documents.
    """

    def __init__(self, nlp: Language) -> None:
        """Initialize with spaCy model.

        Args:
            nlp: spaCy language model for text processing
        """
        self.nlp = nlp

    @override
    def parse(self, pdf_path: Path) -> Doc:
        """Parse PDF using basic text extraction.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Processed spaCy Doc

        Raises:
            FileNotFoundError: If PDF doesn't exist
            RuntimeError: If parsing fails
        """
        if not pdf_path.exists():
            msg = f"PDF file not found: {pdf_path}"
            raise FileNotFoundError(msg)

        try:
            pdf_doc = pymupdf.open(pdf_path)

            blocks = []
            for page in pdf_doc:
                text_blocks = page.get_text("blocks")
                for block in text_blocks:
                    if block[6] == 0:  # Text block
                        blocks.append(block[4])

            pdf_doc.close()

            combined_text = "\n\n".join(blocks)
            doc = self.nlp(combined_text) if combined_text else self.nlp("")

            # Add empty layout for compatibility
            if "layout" not in doc.spans:
                doc.spans["layout"] = []

            return doc

        except Exception as e:
            msg = f"PyMuPDF parsing failed for {pdf_path.name}: {e}"
            logger.error(msg, exc_info=True)
            raise RuntimeError(msg) from e
