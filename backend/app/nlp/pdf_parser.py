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
from typing import TYPE_CHECKING, Any, ClassVar, cast, override

import numpy as np
import pymupdf
from docling.datamodel.base_models import InputFormat
from docling.datamodel.base_models import ConversionStatus
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.pipeline_options import (
    EasyOcrOptions,
    PdfPipelineOptions,
    RapidOcrOptions,
    TesseractCliOcrOptions,
    TesseractOcrOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption
from spacy.tokens import Doc as SpaCyDoc
from spacy_layout import spaCyLayout

from app.core.config import settings

if TYPE_CHECKING:
    from spacy.language import Language
    from spacy.tokens import Doc

logger = logging.getLogger(__name__)
logger.setLevel(settings.LOG_LEVEL)

if not SpaCyDoc.has_extension("image_ocr_snippets"):
    SpaCyDoc.set_extension("image_ocr_snippets", default=None)
if not SpaCyDoc.has_extension("image_ocr_backend"):
    SpaCyDoc.set_extension("image_ocr_backend", default=None)


class OCRBackend(str, Enum):
    """OCR backends in order of preference (fastest to slowest)."""

    RAPIDOCR = "rapidocr"  # Fast, good quality (onnxruntime)
    PADDLEOCR = "paddleocr"  # RapidOCR paddle backend (optional)
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


@dataclass(frozen=True)
class ImageOcrSnippet:
    """OCR text extracted from an image region in a PDF page."""

    text: str
    page_number: int
    bbox: tuple[float, float, float, float]
    backend_used: str
    confidence: float | None = None


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
    1. PaddleOCR mode (RapidOCR paddle backend)
    2. RapidOCR (onnxruntime)
    3. Tesseract (Python binding)
    4. EasyOCR (slowest, best for difficult docs)
    5. PyMuPDF (no OCR, last resort - 50x faster)

    Example:
        >>> parser = DoclingPDFParser(nlp, enable_fallback=True)
        >>> doc = parser.parse(Path("paper.pdf"))
    """

    # OCR backends to try in order
    FALLBACK_CHAIN: ClassVar = [
        OCRBackend.RAPIDOCR,
        OCRBackend.TESSERACT,
        OCRBackend.EASYOCR,
        OCRBackend.PADDLEOCR,
    ]
    IMAGE_OCR_BACKENDS: ClassVar[tuple[OCRBackend, OCRBackend]] = (
        OCRBackend.RAPIDOCR,
        OCRBackend.EASYOCR,
    )

    SENTENCE_PIPE_COMPONENTS: ClassVar[tuple[str, ...]] = (
        "sentencizer",
        "senter",
        "scientific_sentencizer",
    )

    def __init__(
        self,
        nlp: Language,
        *,
        enable_ocr_fallback: bool = True,
        enable_pymupdf_fallback: bool = True,
        force_full_page_ocr: bool = False,
        enable_image_ocr: bool = True,
        image_ocr_min_chars: int = 8,
    ) -> None:
        """Initialize parser with spaCy model and fallback options.

        Args:
            nlp: spaCy language model
            enable_ocr_fallback: Try multiple OCR backends (default: True)
            enable_pymupdf_fallback: Use PyMuPDF as last resort (default: True)
            force_full_page_ocr: Force OCR on all pages, not hybrid (default: False)
            enable_image_ocr: Extract OCR text from embedded PDF images (default: True)
            image_ocr_min_chars: Minimum snippet length to keep for image OCR (default: 8)
        """
        self.nlp = nlp
        self.enable_ocr_fallback = enable_ocr_fallback
        self.enable_pymupdf_fallback = enable_pymupdf_fallback
        self.force_full_page_ocr = force_full_page_ocr
        self.enable_image_ocr = enable_image_ocr
        self.image_ocr_min_chars = image_ocr_min_chars
        self._layout: spaCyLayout | None = None

    @staticmethod
    def _is_docling_layout_dtype_error(error: str | None) -> bool:
        """Return True when Docling layout model hits torch dtype mismatch."""
        if not error:
            return False

        dtype_markers = (
            "expected scalar type double but found float",
            "input type (float) and bias type (double) should be the same",
        )
        normalized = error.lower()
        return any(marker in normalized for marker in dtype_markers)

    def _retry_docling_with_backend_text(
        self,
        pdf_path: Path,
        pipeline_options: PdfPipelineOptions,
        backend: OCRBackend,
    ):
        """Retry conversion with backend text mode after layout dtype mismatch."""
        pipeline_options.force_backend_text = True
        pipeline_options.do_table_structure = False

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
            },
        )

        # Avoid hard failure on conversion status so we can inspect returned document.
        result = converter.convert(pdf_path, raises_on_error=False)
        status = getattr(result, "status", None)
        if status not in {ConversionStatus.SUCCESS, ConversionStatus.PARTIAL_SUCCESS}:
            details = "; ".join(
                getattr(err, "error_message", str(err)) for err in getattr(result, "errors", [])
            )
            msg = f"Docling backend-text retry failed for {backend.value}"
            if details:
                msg = f"{msg}: {details}"
            raise RuntimeError(msg)
        if getattr(result, "document", None) is None:
            msg = f"Docling backend-text retry returned no document for {backend.value}"
            raise RuntimeError(msg)

        return result

    def _try_docling_with_pypdfium_backend(self, pdf_path: Path, backend: OCRBackend):
        """Fallback to Docling pipeline with pypdfium backend.

        This avoids layout-model failures in docling-parse backend while keeping
        Docling conversion and layout span generation.
        """
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True
        pipeline_options.do_table_structure = False
        pipeline_options.force_backend_text = True

        ocr_options = self._get_ocr_options(backend)
        if ocr_options:
            pipeline_options.ocr_options = ocr_options

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pipeline_options,
                    backend=PyPdfiumDocumentBackend,
                ),
            },
        )

        result = converter.convert(pdf_path, raises_on_error=False)
        status = getattr(result, "status", None)
        if status not in {ConversionStatus.SUCCESS, ConversionStatus.PARTIAL_SUCCESS}:
            details = "; ".join(
                getattr(err, "error_message", str(err)) for err in getattr(result, "errors", [])
            )
            msg = f"Docling pypdfium fallback failed for {backend.value}"
            if details:
                msg = f"{msg}: {details}"
            raise RuntimeError(msg)
        if getattr(result, "document", None) is None:
            msg = f"Docling pypdfium fallback returned no document for {backend.value}"
            raise RuntimeError(msg)

        return result

    def _build_doc_with_layout_spans(self, text_blocks: list[str]) -> Doc:
        """Build a spaCy Doc and attach pseudo layout text spans."""
        cleaned_blocks = [block.strip() for block in text_blocks if block and block.strip()]
        combined_text = "\n\n".join(cleaned_blocks)
        doc = self.nlp(combined_text) if combined_text else self.nlp("")

        layout_spans = []
        cursor = 0
        for block_text in cleaned_blocks:
            start = cursor
            end = start + len(block_text)
            span = doc.char_span(start, end, label="text", alignment_mode="expand")
            if span is not None:
                layout_spans.append(span)
            cursor = end + 2  # account for separator "\n\n"

        doc.spans["layout"] = layout_spans
        return doc

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
            OCRBackend.RAPIDOCR: RapidOcrOptions(
                force_full_page_ocr=self.force_full_page_ocr,
                backend="onnxruntime",
            ),
            OCRBackend.PADDLEOCR: RapidOcrOptions(
                force_full_page_ocr=self.force_full_page_ocr,
                backend="paddle",
            ),
            OCRBackend.TESSERACT_CLI: TesseractCliOcrOptions(
                force_full_page_ocr=self.force_full_page_ocr,
            ),
            OCRBackend.TESSERACT: TesseractOcrOptions(
                force_full_page_ocr=self.force_full_page_ocr,
            ),
            OCRBackend.EASYOCR: EasyOcrOptions(force_full_page_ocr=self.force_full_page_ocr),
        }
        return ocr_options_map.get(backend)

    def _docling_to_spacy(self, docling_doc: Any) -> Doc:
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

        # spaCy-layout builds the Doc directly from tokens and does not run the
        # NLP pipeline, so sentence boundaries need to be applied explicitly.
        doc = self._apply_sentence_segmentation(doc)

        # Log brief preview
        logger.debug("Converted Doc: %s", doc)
        return doc

    def _apply_sentence_segmentation(self, doc: Doc) -> Doc:
        """Apply sentence segmentation components to an existing Doc.

        spaCy-layout disables pipeline components during conversion for speed,
        which means sentence boundaries may be unset on the resulting Doc.
        Run only sentence-boundary components to avoid unnecessary overhead.
        """
        enabled_components = [
            name for name in self.SENTENCE_PIPE_COMPONENTS if name in self.nlp.pipe_names
        ]

        if not enabled_components:
            return doc

        with self.nlp.select_pipes(enable=enabled_components):
            return self.nlp(doc)

    def _validate_docling_result(
        self,
        docling_doc: Any,
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
            try:
                result = converter.convert(pdf_path)
            except Exception as exc:
                if self._is_docling_layout_dtype_error(str(exc)):
                    logger.warning(
                        "Docling layout dtype mismatch detected for %s; retrying with backend text mode",
                        backend.value,
                    )
                    try:
                        result = self._retry_docling_with_backend_text(
                            pdf_path,
                            pipeline_options,
                            backend,
                        )
                    except Exception as retry_exc:
                        if not self._is_docling_layout_dtype_error(str(retry_exc)):
                            raise
                        logger.warning(
                            "Backend-text retry still hits dtype mismatch for %s; falling back to pypdfium backend",
                            backend.value,
                        )
                        result = self._try_docling_with_pypdfium_backend(pdf_path, backend)
                else:
                    raise
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

    def _extract_image_ocr_snippets(
        self,
        pdf_path: Path,
        backend: OCRBackend,
    ) -> list[ImageOcrSnippet]:
        """Extract OCR text from embedded PDF images only.

        This is a supplemental stage for figure/map panels that may not be
        captured well by the default document OCR flow.
        """
        if not self.enable_image_ocr:
            return []

        rapidocr_reader = None
        easyocr_reader = None

        if backend in {OCRBackend.RAPIDOCR, OCRBackend.PADDLEOCR}:
            try:
                from rapidocr import EngineType, RapidOCR  # type: ignore
            except ImportError:
                logger.warning("RapidOCR not available for image OCR stage")
                return []

            engine_aliases = {
                OCRBackend.RAPIDOCR: EngineType.ONNXRUNTIME,
                OCRBackend.PADDLEOCR: EngineType.PADDLE,
            }
            engine_type = engine_aliases.get(backend)
            if engine_type is None:
                return []

            try:
                rapidocr_reader = RapidOCR(
                    params={
                        "Det.engine_type": engine_type,
                        "Cls.engine_type": engine_type,
                        "Rec.engine_type": engine_type,
                    },
                )
            except Exception:
                logger.warning("Failed to initialize image OCR reader for backend %s", backend.value)
                return []
        elif backend == OCRBackend.EASYOCR:
            try:
                import easyocr  # type: ignore
            except ImportError:
                logger.warning("EasyOCR not available for image OCR stage")
                return []

            try:
                easyocr_reader = easyocr.Reader(["en"], gpu=False, verbose=False)
            except Exception:
                logger.warning("Failed to initialize image OCR reader for backend %s", backend.value)
                return []
        else:
            return []

        snippets: list[ImageOcrSnippet] = []
        try:
            pdf_doc = pymupdf.open(pdf_path)
        except Exception:
            logger.warning("Could not open PDF for image OCR snippets: %s", pdf_path.name)
            return []

        try:
            for page_index in range(pdf_doc.page_count):
                page = pdf_doc[page_index]
                image_infos = cast(list[dict[str, Any]], page.get_image_info(hashes=False))
                for info in image_infos:
                    bbox_raw = info.get("bbox")
                    if not bbox_raw:
                        continue

                    ocr_result: Any | None = None
                    easyocr_result: list[Any] | None = None

                    try:
                        bbox_rect = pymupdf.Rect(bbox_raw)
                        if bbox_rect.width < 8 or bbox_rect.height < 8:
                            continue

                        pix = page.get_pixmap(clip=bbox_rect, dpi=216, alpha=False)
                        image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                            pix.height,
                            pix.width,
                            pix.n,
                        )
                        if rapidocr_reader is not None:
                            ocr_result = rapidocr_reader(image)
                        else:
                            if easyocr_reader is None:
                                continue
                            easyocr_result = cast(
                                list[Any],
                                cast(Any, easyocr_reader).readtext(image, detail=1),
                            )
                    except Exception:
                        continue

                    if rapidocr_reader is not None:
                        if ocr_result is None:
                            continue

                        ocr_texts = cast(list[str] | None, getattr(ocr_result, "txts", None))
                        if ocr_texts is None:
                            continue

                        text = " ".join(t.strip() for t in ocr_texts if t and t.strip()).strip()
                        if len(text) < self.image_ocr_min_chars:
                            continue

                        confidence = None
                        ocr_scores = cast(list[float] | None, getattr(ocr_result, "scores", None))
                        if ocr_scores is not None and len(ocr_scores) > 0:
                            confidence = float(sum(ocr_scores) / len(ocr_scores))
                    else:
                        if not easyocr_result:
                            continue

                        easy_texts: list[str] = []
                        easy_scores: list[float] = []
                        for item_any in easyocr_result:
                            if not isinstance(item_any, (list, tuple)):
                                continue
                            item = cast(tuple[Any, ...], tuple(item_any))
                            if len(item) >= 2:
                                easy_texts.append(str(item[1]).strip())
                            if len(item) >= 3 and isinstance(item[2], (int, float)):
                                easy_scores.append(float(item[2]))

                        text = " ".join(t for t in easy_texts if t).strip()
                        if len(text) < self.image_ocr_min_chars:
                            continue
                        confidence = float(sum(easy_scores) / len(easy_scores)) if easy_scores else None

                    snippets.append(
                        ImageOcrSnippet(
                            text=text,
                            page_number=page_index + 1,
                            bbox=(bbox_rect.x0, bbox_rect.y0, bbox_rect.x1, bbox_rect.y1),
                            backend_used=backend.value,
                            confidence=confidence,
                        ),
                    )
        finally:
            pdf_doc.close()

        return snippets

    def _extract_image_ocr_snippets_with_fallback(
        self,
        pdf_path: Path,
        preferred_backend: OCRBackend,
    ) -> list[ImageOcrSnippet]:
        """Extract image OCR snippets with paddle/onnx fallback."""
        backend_order = [preferred_backend]
        if preferred_backend == OCRBackend.PADDLEOCR:
            backend_order.append(OCRBackend.RAPIDOCR)
        elif preferred_backend == OCRBackend.RAPIDOCR:
            backend_order.append(OCRBackend.PADDLEOCR)

        for configured in self.IMAGE_OCR_BACKENDS:
            if configured not in backend_order:
                backend_order.append(configured)

        for backend in backend_order:
            snippets = self._extract_image_ocr_snippets(pdf_path, backend)
            if snippets:
                logger.info(
                    "Extracted %d image OCR snippets with %s",
                    len(snippets),
                    backend.value,
                )
                return snippets

        return []

    def _append_image_ocr_spans(self, doc: Doc, snippets: list[ImageOcrSnippet]) -> Doc:
        """Append image OCR snippets to layout spans as pseudo-text blocks."""
        if not snippets:
            return doc

        current_length = len(doc.text)
        extras: list[str] = []
        image_spans = []

        for snippet in snippets:
            prefix = f"\n\n[IMAGE_OCR page={snippet.page_number}] "
            segment = f"{prefix}{snippet.text}"
            start_char = current_length + sum(len(x) for x in extras)
            end_char = start_char + len(segment)
            extras.append(segment)
            image_spans.append((start_char, end_char, snippet))

        if not extras:
            return doc

        enriched_text = doc.text + "".join(extras)
        enriched_doc = self.nlp(enriched_text)

        for key, spans in doc.spans.items():
            recreated_spans = []
            for span in spans:
                recreated = enriched_doc.char_span(
                    span.start_char,
                    span.end_char,
                    label=span.label_,
                    alignment_mode="expand",
                )
                if recreated is not None:
                    recreated_spans.append(recreated)
            enriched_doc.spans[key] = recreated_spans

        layout_spans = list(enriched_doc.spans.get("layout", []))
        for start_char, end_char, snippet in image_spans:
            span = enriched_doc.char_span(start_char, end_char, label="image", alignment_mode="expand")
            if span is not None:
                layout_spans.append(span)

        enriched_doc.spans["layout"] = layout_spans
        enriched_doc._.image_ocr_snippets = snippets
        enriched_doc._.image_ocr_backend = snippets[0].backend_used if snippets else None

        return enriched_doc

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

            # Build doc with pseudo layout spans for section extraction compatibility
            doc = self._build_doc_with_layout_spans(blocks)

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
            logger.exception("PyMuPDF parsing failed: ")
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
        1. Docling + PaddleOCR mode
        2. Docling + RapidOCR (if ocr_fallback enabled)
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
                    parsed_doc = result.doc
                    if self.enable_image_ocr:
                        snippets = self._extract_image_ocr_snippets_with_fallback(pdf_path, backend)
                        parsed_doc = self._append_image_ocr_spans(parsed_doc, snippets)
                    logger.info(f"Parsed {pdf_path.name} using {result.backend_used}")
                    return parsed_doc

                # Log reason for trying next backend
                if result.success and result.doc and not result.doc.text.strip():
                    logger.warning(
                        f"{backend.value} returned empty content, retrying with next OCR backend...",
                    )
                else:
                    logger.warning("Retrying with next OCR backend...")

                if self._is_docling_layout_dtype_error(result.error):
                    logger.warning(
                        "Docling layout model dtype mismatch detected; skipping remaining OCR backends",
                    )
                    break
        else:
            # Try only once with first backend
            selected_backend = self.FALLBACK_CHAIN[0]
            result = self._try_docling(pdf_path, selected_backend)

            # Check if result has actual content (not just empty doc)
            if result.success and result.doc and result.doc.text.strip():
                parsed_doc = result.doc
                if self.enable_image_ocr:
                    snippets = self._extract_image_ocr_snippets_with_fallback(
                        pdf_path,
                        selected_backend,
                    )
                    parsed_doc = self._append_image_ocr_spans(parsed_doc, snippets)
                logger.info(f"Parsed {pdf_path.name} using {result.backend_used}")
                return parsed_doc

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
                        blocks.append(block[4])

            pdf_doc.close()

            # Reuse same pseudo-layout behavior as Docling fallback parser
            cleaned_blocks = [block.strip() for block in blocks if block and block.strip()]
            combined_text = "\n\n".join(cleaned_blocks)
            doc = self.nlp(combined_text) if combined_text else self.nlp("")

            layout_spans = []
            cursor = 0
            for block_text in cleaned_blocks:
                start = cursor
                end = start + len(block_text)
                span = doc.char_span(start, end, label="text", alignment_mode="expand")
                if span is not None:
                    layout_spans.append(span)
                cursor = end + 2
            doc.spans["layout"] = layout_spans

        except Exception as e:
            logger.exception("PyMuPDF parsing failed for %s", pdf_path.name)
            msg = f"PyMuPDF parsing failed for {pdf_path.name}: {e!s}"
            raise RuntimeError(msg) from e
        else:
            logger.info("Successfully parsed %s with PyMuPDF", pdf_path.name)
            return doc
