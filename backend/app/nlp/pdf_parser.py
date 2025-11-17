"""PDF parsing with robust OCR fallback chain using Docling.

This module provides PDF to spaCy Doc conversion with automatic fallback
through multiple OCR backends if one fails.
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, override

import pymupdf
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    EasyOcrOptions,
    PdfPipelineOptions,
    RapidOcrOptions,
    TesseractCliOcrOptions,
    TesseractOcrOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption
from spacy_layout import spaCyLayout

if TYPE_CHECKING:
    from docling_core.types import DoclingDocument
    from spacy.language import Language
    from spacy.tokens import Doc

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class OCRBackend(str, Enum):
    """OCR backends in order of preference (fastest to slowest)."""

    RAPIDOCR = "rapidocr"  # Fast, good quality (onnxruntime)
    TESSERACT = "tesseract"  # Moderate speed, high quality
    TESSERACT_CLI = "tesseract_cli"  # CLI-based Tesseract
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


class DoclingPDFParser(PDFParser):
    """PDF parser using Docling with robust OCR fallback chain.

    Automatically tries multiple OCR backends if one fails:
    1. RapidOCR (fastest, good quality)
    2. Tesseract (Python binding)
    3. EasyOCR (slowest, best for difficult docs)
    4. PyMuPDF (no OCR, last resort - 50x faster)

    Example:
        >>> parser = DoclingPDFParser(nlp, enable_fallback=True)
        >>> doc = parser.parse(Path("paper.pdf"))
    """

    # OCR backends to try in order
    FALLBACK_CHAIN: ClassVar = [
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
        force_full_page_ocr: bool = False,
    ) -> None:
        """Initialize parser with spaCy model and fallback options.

        Args:
            nlp: spaCy language model
            enable_ocr_fallback: Try multiple OCR backends (default: True)
            enable_pymupdf_fallback: Use PyMuPDF as last resort (default: True)
            force_full_page_ocr: Force OCR on all pages, not hybrid (default: False)
        """
        self.nlp = nlp
        self.enable_ocr_fallback = enable_ocr_fallback
        self.enable_pymupdf_fallback = enable_pymupdf_fallback
        self.force_full_page_ocr = force_full_page_ocr
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

    def _get_ocr_options(self, backend: OCRBackend):
        """Get OCR options for specified backend.

        Args:
            backend: OCR backend to use

        Returns:
            OCR options instance or None
        """
        ocr_options_map = {
            OCRBackend.RAPIDOCR: RapidOcrOptions(force_full_page_ocr=self.force_full_page_ocr),
            OCRBackend.TESSERACT_CLI: TesseractCliOcrOptions(
                force_full_page_ocr=self.force_full_page_ocr,
            ),
            OCRBackend.TESSERACT: TesseractOcrOptions(
                force_full_page_ocr=self.force_full_page_ocr,
            ),
            OCRBackend.EASYOCR: EasyOcrOptions(force_full_page_ocr=self.force_full_page_ocr),
        }
        return ocr_options_map.get(backend)

    def _docling_to_spacy(self, docling_doc: DoclingDocument) -> Doc:
        """Convert Docling document to spaCy Doc.

        Args:
            docling_doc: Docling document

        Returns:
            spaCy Doc with layout information
        """
        # Export to markdown or text
        # text = docling_doc.export_to_markdown()
        layout = self._init_layout()
        # Remove pictures for cleaner output
        logger.debug("DoclingDocument: %s", docling_doc)
        doc = layout(docling_doc)
        # Log brief preview
        logger.debug("Converted Doc: %s", doc)
        return doc

    def _validate_docling_result(
        self,
        docling_doc: DoclingDocument,
        backend: OCRBackend,
    ) -> tuple[bool, str | None]:
        """Validate that Docling parsing produced meaningful content.

        Args:
            docling_doc: Docling document to validate
            backend: OCR backend used

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check document structure exists
        if not hasattr(docling_doc, "texts"):
            return False, "Document has no 'texts' attribute"

        # Check for text content
        texts = getattr(docling_doc, "texts", [])
        if not texts or len(texts) == 0:
            return False, "Document contains no text items"

        # Export to markdown and check meaningful content
        try:
            markdown = docling_doc.export_to_markdown()
        except Exception as e:
            return False, f"Failed to export to markdown: {e!s}"

        if not markdown or not markdown.strip():
            return False, "Markdown export is empty"

        # Check minimum content threshold (avoid single-character junk)
        if len(markdown.strip()) < 10:
            return False, f"Content too short ({len(markdown.strip())} chars)"

        # Check for actual words (not just whitespace/symbols)
        words = re.findall(r"\b[a-zA-Z]{2,}\b", markdown)
        if len(words) < 5:
            return False, f"Too few recognisable words ({len(words)})"

        # Optional: Check document metadata
        pages = getattr(docling_doc, "pages", {})
        if not pages:
            logger.warning(f"{backend.value} produced content but no page metadata")

        return True, None

    def _try_docling(self, pdf_path: Path, backend: OCRBackend) -> ParseResult:
        """Try extraction with Docling using specific OCR backend."""
        try:
            logger.info(f"Attempting PDF parsing with Docling + {backend.value}")

            # Configure pipeline options
            pipeline_options = PdfPipelineOptions()
            pipeline_options.do_ocr = True
            pipeline_options.do_table_structure = True
            pipeline_options.table_structure_options.do_cell_matching = True

            # Set OCR options
            ocr_options = self._get_ocr_options(backend)
            if ocr_options:
                pipeline_options.ocr_options = ocr_options

            # Create converter with options
            converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
                },
            )

            # Convert document
            result = converter.convert(pdf_path)
            docling_doc = result.document

            # Validate the result BEFORE converting to spaCy
            is_valid, error_msg = self._validate_docling_result(docling_doc, backend)
            if not is_valid:
                msg = f"Docling parsing failed with {backend.value}: {error_msg}"
                raise ValueError(msg)

            # Convert to spaCy Doc
            doc = self._docling_to_spacy(docling_doc)

            # Double-check spaCy doc as well
            if not doc.text.strip():
                raise ValueError("spaCy Doc conversion resulted in empty text")

            if len(doc.text.strip()) < 10:
                raise ValueError(f"spaCy Doc too short: {len(doc.text.strip())} chars")

            logger.debug(f"Extracted text length: {len(doc.text)} characters")
            logger.debug(f"Extracted text preview: {doc.text[:100]!r}...")
            logger.info(f"Successfully parsed with Docling + {backend.value}")

            return ParseResult(
                doc=doc,
                backend_used=f"docling+{backend.value}",
                success=True,
            )

        except Exception as e:
            logger.warning(
                f"Docling parsing failed with {backend.value}: {e!s}",
                exc_info=True,
            )
            return ParseResult(
                doc=None,
                backend_used=f"docling+{backend.value}",
                success=False,
                error=str(e),
            )

    def _try_pymupdf(self, pdf_path: Path) -> ParseResult:
        """Try basic text extraction with PyMuPDF (no OCR, 50x faster).

        Args:
            pdf_path: Path to PDF

        Returns:
            ParseResult with success status
        """
        try:
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
        1. Docling + RapidOCR
        3. Docling + Tesseract (if ocr_fallback enabled)
        4. Docling + EasyOCR (if ocr_fallback enabled)
        5. PyMuPDF (if pymupdf_fallback enabled)

        Afterwards, spacy-layout is applied to add layout info.

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
                result = self._try_docling(pdf_path, backend)
                # Check if result has actual content (not just empty doc)
                if result.success and result.doc and result.doc.text.strip():
                    logger.info(f"Parsed {pdf_path.name} using {result.backend_used}")
                    return result.doc

                # Log reason for trying next backend
                if result.success and result.doc and not result.doc.text.strip():
                    logger.warning(
                        f"{backend.value} returned empty content, retrying with next OCR backend...",
                    )
                else:
                    logger.warning("Retrying with next OCR backend...")
        else:
            # Try only once with first backend
            result = self._try_docling(pdf_path, self.FALLBACK_CHAIN[0])
            # Check if result has actual content (not just empty doc)
            if result.success and result.doc and result.doc.text.strip():
                logger.info(f"Parsed {pdf_path.name} using {result.backend_used}")
                return result.doc

        # PyMuPDF fallback if enabled (50x faster for text-based PDFs)
        if self.enable_pymupdf_fallback:
            logger.info(
                "All OCR methods failed or returned empty content, trying PyMuPDF fallback",
            )
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

    Use when PDFs are text-based and don't need OCR. Approximately 50x
    faster than Docling but won't work on scanned documents.
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
                        blocks.extend(block[4])

            pdf_doc.close()

            combined_text = "\n\n".join(blocks)
            doc = self.nlp(combined_text) if combined_text else self.nlp("")

            # Add empty layout for compatibility
            if "layout" not in doc.spans:
                doc.spans["layout"] = []

        except Exception as e:
            logger.exception("PyMuPDF parsing failed for %s", pdf_path.name)
            msg = f"PyMuPDF parsing failed for {pdf_path.name}: {e!s}"
            raise RuntimeError(msg) from e
        else:
            logger.info("Successfully parsed %s with PyMuPDF", pdf_path.name)
            return doc
