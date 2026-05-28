"""PDF parsing with robust OCR fallback chain using Docling.

This module provides PDF to spaCy Doc conversion with automatic fallback
through multiple OCR backends if one fails.
"""

from __future__ import annotations

import contextlib
import logging
import os
import re
import shutil
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
from app.nlp.torch_utils import torch_float32_default

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
    """Available OCR backends."""

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


@dataclass(frozen=True)
class EmbeddedTextAssessment:
    """Embedded-text coverage assessment captured before OCR stages."""

    page_texts: list[str]
    low_text_pages: list[int]
    pages_with_embedded_text: int
    total_pages: int

    @property
    def has_embedded_text(self) -> bool:
        return self.pages_with_embedded_text > 0


@dataclass(frozen=True)
class OcrRuntimeResources:
    """Initialized OCR runtime objects for page-level OCR calls."""

    rapidocr_reader: Any | None = None
    easyocr_reader: Any | None = None
    tesseract_module: Any | None = None
    tessdata_path: str | None = None


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

    Ingestion stage order:
    1. Embedded-text assessment (first gate)
    2. Embedded text only (if all pages have enough text)
    3. Selective page OCR for low-text pages only
    4. Docling OCR fallback chain (tesseract/easyocr/rapidocr)
    5. Direct full-page OCR fallback chain
    6. PyMuPDF (no OCR, last resort)

    Example:
        >>> parser = DoclingPDFParser(nlp, enable_fallback=True)
        >>> doc = parser.parse(Path("paper.pdf"))
    """

    # OCR backends to try in order (quality-first)
    FALLBACK_CHAIN: ClassVar = [
        OCRBackend.TESSERACT,
        OCRBackend.PADDLEOCR,
        OCRBackend.EASYOCR,
        OCRBackend.RAPIDOCR,
    ]
    IMAGE_OCR_BACKENDS: ClassVar[tuple[OCRBackend, ...]] = (
        OCRBackend.TESSERACT,
        OCRBackend.PADDLEOCR,
        OCRBackend.EASYOCR,
        OCRBackend.RAPIDOCR,
    )
    FULL_PAGE_OCR_DPI: ClassVar[int] = 300
    EMBEDDED_TEXT_MIN_CHARS_PER_PAGE: ClassVar[int] = 120
    EMBEDDED_TEXT_MIN_WORDS_PER_PAGE: ClassVar[int] = 20

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

    _torch_float32_default = staticmethod(torch_float32_default)

    @staticmethod
    def _resolve_tessdata_path() -> str | None:
        """Resolve a usable tessdata directory for tesseract bindings."""
        candidates: list[Path] = []

        env_path = os.environ.get("TESSDATA_PREFIX")
        if env_path:
            candidates.append(Path(env_path))

        tesseract_binary = shutil.which("tesseract")
        if tesseract_binary:
            candidates.append(Path(tesseract_binary).resolve().parent.parent / "share" / "tessdata")

        candidates.extend(
            [
                Path("/usr/share/tessdata"),
                Path("/usr/share/tesseract-ocr/5/tessdata"),
                Path("/usr/share/tesseract-ocr/4.00/tessdata"),
            ]
        )

        for candidate in candidates:
            normalized = candidate
            if normalized.name != "tessdata" and (normalized / "tessdata").is_dir():
                normalized = normalized / "tessdata"

            if (normalized / "eng.traineddata").is_file():
                return normalized.as_posix().rstrip("/") + "/"

        return None

    @staticmethod
    def _supports_paddle_backend() -> bool:
        """Return True when RapidOCR's paddle runtime is actually available."""
        try:
            from paddle import inference  # type: ignore
        except Exception:
            return False

        return inference is not None

    def _supports_backend(self, backend: OCRBackend) -> tuple[bool, str | None]:
        """Return whether an OCR backend is usable in the current environment."""
        if backend == OCRBackend.PADDLEOCR and not self._supports_paddle_backend():
            return False, "installed paddle package does not provide paddle.inference"

        if backend in {OCRBackend.TESSERACT, OCRBackend.TESSERACT_CLI}:
            tessdata_path = self._resolve_tessdata_path()
            if tessdata_path is None:
                return False, "no usable tessdata path found"

        return True, None

    @contextlib.contextmanager
    def _docling_backend_environment(self, backend: OCRBackend) -> Iterator[None]:
        """Temporarily export backend-specific env vars needed by Docling.

        Docling's Tesseract OCR model calls `tesserocr.get_languages()` before it
        applies `options.path`, so the worker still needs `TESSDATA_PREFIX` set
        while the Docling pipeline is initialized.
        """
        if backend not in {OCRBackend.TESSERACT, OCRBackend.TESSERACT_CLI}:
            yield
            return

        tessdata_path = self._resolve_tessdata_path()
        if tessdata_path is None:
            yield
            return

        original_tessdata_prefix = os.environ.get("TESSDATA_PREFIX")
        try:
            os.environ["TESSDATA_PREFIX"] = tessdata_path
            yield
        finally:
            if original_tessdata_prefix is None:
                os.environ.pop("TESSDATA_PREFIX", None)
            else:
                os.environ["TESSDATA_PREFIX"] = original_tessdata_prefix

    def _configured_ocr_backends(self) -> list[OCRBackend]:
        """Return the OCR backends that are both configured and usable."""
        requested = list(self.FALLBACK_CHAIN if self.enable_ocr_fallback else [self.FALLBACK_CHAIN[0]])
        configured: list[OCRBackend] = []

        for backend in requested:
            supported, reason = self._supports_backend(backend)
            if supported:
                configured.append(backend)
            else:
                logger.warning("Skipping OCR backend %s: %s", backend.value, reason)

        return configured

    @staticmethod
    def _create_easyocr_reader() -> Any:
        """Create an EasyOCR reader with float32 torch modules.

        Some worker processes end up with `torch.float64` as the global default
        dtype, which makes EasyOCR initialize detector/recognizer weights as
        doubles and then fail at inference with float32 inputs. Build the
        reader under a float32 default and coerce the loaded modules back to
        float32 explicitly.
        """
        try:
            import easyocr  # type: ignore
            import torch
        except ImportError as exc:
            msg = "EasyOCR not available"
            raise RuntimeError(msg) from exc

        with DoclingPDFParser._torch_float32_default():
            reader = easyocr.Reader(["en"], gpu=False, verbose=False)

        for module_name in ("detector", "recognizer"):
            module = getattr(reader, module_name, None)
            if module is not None and hasattr(module, "float"):
                cast(Any, module).float()

        return reader

    def _retry_docling_with_backend_text(
        self,
        pdf_path: Path,
        pipeline_options: PdfPipelineOptions,
        backend: OCRBackend,
    ):
        """Retry conversion with backend text mode after layout dtype mismatch."""
        pipeline_options.force_backend_text = True
        pipeline_options.do_table_structure = False

        with self._torch_float32_default(), self._docling_backend_environment(backend):
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

        with self._torch_float32_default(), self._docling_backend_environment(backend):
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

    @staticmethod
    def _validate_extracted_text(text: str) -> tuple[bool, str | None]:
        """Validate extracted text from direct OCR or plain-text fallbacks."""
        stripped = text.strip()
        if not stripped:
            return False, "Extracted text is empty"

        if len(stripped) < 20:
            return False, f"Extracted text too short ({len(stripped)} chars)"

        words = re.findall(r"\b[a-zA-Z]{2,}\b", stripped)
        if len(words) < 5:
            return False, f"Too few recognisable words ({len(words)})"

        return True, None

    @staticmethod
    def _pixmap_to_array(pix: pymupdf.Pixmap) -> np.ndarray:
        """Convert a PyMuPDF pixmap to an image array."""
        return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)

    @staticmethod
    def _pixmap_to_pil_image(pix: pymupdf.Pixmap) -> Any:
        """Convert a PyMuPDF pixmap to a PIL image."""
        from PIL import Image

        mode = {1: "L", 3: "RGB", 4: "RGBA"}.get(pix.n, "RGB")
        return Image.frombytes(mode, (pix.width, pix.height), pix.samples)

    def _ocr_page_pixmap(
        self,
        pix: pymupdf.Pixmap,
        backend: OCRBackend,
        *,
        rapidocr_reader: Any | None = None,
        easyocr_reader: Any | None = None,
        tesseract_module: Any | None = None,
        tessdata_path: str | None = None,
    ) -> str:
        """Extract OCR text from a rendered PDF page."""
        if backend in {OCRBackend.RAPIDOCR, OCRBackend.PADDLEOCR}:
            if rapidocr_reader is None:
                return ""

            ocr_result = rapidocr_reader(self._pixmap_to_array(pix))
            if ocr_result is None:
                return ""

            ocr_texts = cast(list[str] | None, getattr(ocr_result, "txts", None))
            if ocr_texts is None:
                return ""

            return "\n".join(text.strip() for text in ocr_texts if text and text.strip()).strip()

        if backend == OCRBackend.EASYOCR:
            if easyocr_reader is None:
                return ""

            ocr_result = cast(
                list[Any],
                cast(Any, easyocr_reader).readtext(
                    self._pixmap_to_array(pix),
                    detail=0,
                    paragraph=True,
                ),
            )
            return "\n".join(str(item).strip() for item in ocr_result if str(item).strip()).strip()

        if backend == OCRBackend.TESSERACT:
            if tesseract_module is None:
                return ""

            image = self._pixmap_to_pil_image(pix)
            kwargs = {"path": tessdata_path} if tessdata_path else {}
            return str(tesseract_module.image_to_text(image, **kwargs)).strip()

        return ""

    def _initialize_page_ocr_resources(self, backend: OCRBackend) -> OcrRuntimeResources:
        """Prepare OCR runtime resources for page-level OCR operations."""
        if backend in {OCRBackend.RAPIDOCR, OCRBackend.PADDLEOCR}:
            try:
                from rapidocr import EngineType, RapidOCR  # type: ignore
            except ImportError as exc:
                msg = f"RapidOCR not available for {backend.value}"
                raise RuntimeError(msg) from exc

            engine_aliases = {
                OCRBackend.RAPIDOCR: EngineType.ONNXRUNTIME,
                OCRBackend.PADDLEOCR: EngineType.PADDLE,
            }
            engine_type = engine_aliases.get(backend)
            if engine_type is None:
                msg = f"Unsupported RapidOCR backend: {backend.value}"
                raise RuntimeError(msg)

            rapidocr_reader = RapidOCR(
                params={
                    "Det.engine_type": engine_type,
                    "Cls.engine_type": engine_type,
                    "Rec.engine_type": engine_type,
                },
            )
            return OcrRuntimeResources(rapidocr_reader=rapidocr_reader)

        if backend == OCRBackend.EASYOCR:
            return OcrRuntimeResources(easyocr_reader=self._create_easyocr_reader())

        if backend == OCRBackend.TESSERACT:
            try:
                import tesserocr  # type: ignore
            except ImportError as exc:
                msg = "Tesseract Python bindings not available for direct full-page OCR"
                raise RuntimeError(msg) from exc

            tessdata_path = self._resolve_tessdata_path()
            if tessdata_path is None:
                msg = "No valid tessdata path found for direct full-page OCR"
                raise RuntimeError(msg)

            return OcrRuntimeResources(
                tesseract_module=tesserocr,
                tessdata_path=tessdata_path,
            )

        msg = f"Direct full-page OCR is not supported for {backend.value}"
        raise RuntimeError(msg)

    @staticmethod
    def _is_page_text_sufficient(page_text: str) -> bool:
        """Return True when a page has enough embedded text to avoid OCR."""
        stripped = page_text.strip()
        if not stripped:
            return False

        chars = len(stripped)
        words = len(re.findall(r"\b[a-zA-Z]{2,}\b", stripped))
        return (
            chars >= DoclingPDFParser.EMBEDDED_TEXT_MIN_CHARS_PER_PAGE
            or words >= DoclingPDFParser.EMBEDDED_TEXT_MIN_WORDS_PER_PAGE
        )

    def _assess_embedded_text(self, pdf_path: Path) -> EmbeddedTextAssessment:
        """Assess embedded text coverage before OCR stages begin."""
        pdf_doc = pymupdf.open(pdf_path)
        page_texts: list[str] = []
        low_text_pages: list[int] = []
        pages_with_embedded_text = 0

        try:
            for page_index in range(pdf_doc.page_count):
                page_text = pdf_doc[page_index].get_text("text").strip()
                page_texts.append(page_text)
                if self._is_page_text_sufficient(page_text):
                    pages_with_embedded_text += 1
                else:
                    low_text_pages.append(page_index)
        finally:
            pdf_doc.close()

        return EmbeddedTextAssessment(
            page_texts=page_texts,
            low_text_pages=low_text_pages,
            pages_with_embedded_text=pages_with_embedded_text,
            total_pages=len(page_texts),
        )

    def _try_selective_page_ocr(
        self,
        pdf_path: Path,
        *,
        backend: OCRBackend,
        assessment: EmbeddedTextAssessment,
    ) -> ParseResult:
        """OCR only low-text pages and keep embedded text for the rest."""
        if not assessment.low_text_pages:
            msg = "Selective OCR requested without low-text pages"
            return ParseResult(
                doc=None,
                backend_used=f"embedded+{backend.value}",
                success=False,
                error=msg,
            )

        try:
            logger.info(
                "Attempting selective page OCR with %s on %d/%d low-text pages",
                backend.value,
                len(assessment.low_text_pages),
                assessment.total_pages,
            )

            resources = self._initialize_page_ocr_resources(backend)
            combined_page_texts = list(assessment.page_texts)
            low_page_set = set(assessment.low_text_pages)

            pdf_doc = pymupdf.open(pdf_path)
            try:
                for page_index in range(pdf_doc.page_count):
                    if page_index not in low_page_set:
                        continue

                    page = pdf_doc[page_index]
                    pix = page.get_pixmap(dpi=self.FULL_PAGE_OCR_DPI, alpha=False)
                    ocr_text = self._ocr_page_pixmap(
                        pix,
                        backend,
                        rapidocr_reader=resources.rapidocr_reader,
                        easyocr_reader=resources.easyocr_reader,
                        tesseract_module=resources.tesseract_module,
                        tessdata_path=resources.tessdata_path,
                    ).strip()

                    if not ocr_text:
                        msg = f"Selective OCR returned no text for page {page_index + 1}"
                        raise ValueError(msg)

                    combined_page_texts[page_index] = ocr_text
            finally:
                pdf_doc.close()

            combined_text = "\n\n".join(text for text in combined_page_texts if text)
            is_valid, error_msg = self._validate_extracted_text(combined_text)
            if not is_valid:
                msg = f"Selective OCR output invalid with {backend.value}: {error_msg}"
                raise ValueError(msg)

            doc = self._build_doc_with_layout_spans(combined_page_texts)
            logger.info(
                "Successfully parsed with embedded-text + selective OCR (%s)",
                backend.value,
            )
            return ParseResult(
                doc=doc,
                backend_used=f"embedded+{backend.value}",
                success=True,
            )

        except Exception as e:
            logger.warning(
                "Selective page OCR failed with %s: %s",
                backend.value,
                str(e),
                exc_info=True,
            )
            return ParseResult(
                doc=None,
                backend_used=f"embedded+{backend.value}",
                success=False,
                error=str(e),
            )

    def _try_embedded_text_first(self, pdf_path: Path, ocr_backends: list[OCRBackend]) -> ParseResult:
        """First ingestion stage: use embedded text before any OCR-heavy pipeline."""
        try:
            assessment = self._assess_embedded_text(pdf_path)
        except Exception as e:
            return ParseResult(
                doc=None,
                backend_used="embedded_text",
                success=False,
                error=f"Embedded-text assessment failed: {e}",
            )

        if assessment.total_pages == 0 or not assessment.has_embedded_text:
            return ParseResult(
                doc=None,
                backend_used="embedded_text",
                success=False,
                error="No usable embedded text detected",
            )

        if not assessment.low_text_pages:
            combined_text = "\n\n".join(text for text in assessment.page_texts if text)
            is_valid, error_msg = self._validate_extracted_text(combined_text)
            if not is_valid:
                return ParseResult(
                    doc=None,
                    backend_used="embedded_text",
                    success=False,
                    error=error_msg,
                )

            doc = self._build_doc_with_layout_spans(assessment.page_texts)
            logger.info(
                "Embedded text fully covers PDF (%d/%d pages); skipping OCR stage",
                assessment.pages_with_embedded_text,
                assessment.total_pages,
            )
            return ParseResult(doc=doc, backend_used="embedded_text", success=True)

        logger.info(
            "Embedded text covers %d/%d pages; running selective OCR on low-text pages first",
            assessment.pages_with_embedded_text,
            assessment.total_pages,
        )

        for backend in ocr_backends:
            result = self._try_selective_page_ocr(
                pdf_path,
                backend=backend,
                assessment=assessment,
            )
            if result.success and result.doc and result.doc.text.strip():
                return result

        return ParseResult(
            doc=None,
            backend_used="embedded_text",
            success=False,
            error="Selective OCR failed for low-text pages",
        )

    def _try_full_page_ocr(self, pdf_path: Path, backend: OCRBackend) -> ParseResult:
        """Try direct OCR on rendered PDF pages before giving up to plain text extraction."""
        try:
            logger.info("Attempting direct full-page OCR with %s", backend.value)
            resources = self._initialize_page_ocr_resources(backend)

            page_texts: list[str] = []
            pdf_doc = pymupdf.open(pdf_path)
            try:
                for page_index in range(pdf_doc.page_count):
                    page = pdf_doc[page_index]
                    pix = page.get_pixmap(dpi=self.FULL_PAGE_OCR_DPI, alpha=False)
                    page_text = self._ocr_page_pixmap(
                        pix,
                        backend,
                        rapidocr_reader=resources.rapidocr_reader,
                        easyocr_reader=resources.easyocr_reader,
                        tesseract_module=resources.tesseract_module,
                        tessdata_path=resources.tessdata_path,
                    ).strip()
                    if page_text:
                        page_texts.append(page_text)
                    else:
                        logger.debug(
                            "Direct full-page OCR with %s returned no text for page %d",
                            backend.value,
                            page_index + 1,
                        )
            finally:
                pdf_doc.close()

            combined_text = "\n\n".join(page_texts)
            is_valid, error_msg = self._validate_extracted_text(combined_text)
            if not is_valid:
                msg = f"Direct full-page OCR failed with {backend.value}: {error_msg}"
                raise ValueError(msg)

            doc = self._build_doc_with_layout_spans(page_texts)
            logger.info("Successfully parsed with direct full-page OCR + %s", backend.value)
            return ParseResult(
                doc=doc,
                backend_used=f"fullpage+{backend.value}",
                success=True,
            )

        except Exception as e:
            error_msg = str(e)
            if self._is_docling_layout_dtype_error(error_msg):
                logger.warning(
                    "Direct full-page OCR hit a torch dtype mismatch for %s; skipping backend: %s",
                    backend.value,
                    error_msg,
                )
            else:
                logger.warning(
                    "Direct full-page OCR failed with %s: %s",
                    backend.value,
                    error_msg,
                    exc_info=True,
                )
            return ParseResult(
                doc=None,
                backend_used=f"fullpage+{backend.value}",
                success=False,
                error=error_msg,
            )

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
        tessdata_path = self._resolve_tessdata_path()
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
                path=tessdata_path,
            ),
            OCRBackend.TESSERACT: TesseractOcrOptions(
                force_full_page_ocr=self.force_full_page_ocr,
                path=tessdata_path,
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
            with self._torch_float32_default(), self._docling_backend_environment(backend):
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
            error_msg = str(e)
            if self._is_docling_layout_dtype_error(error_msg):
                logger.warning(
                    "Docling parsing hit a torch dtype mismatch for %s; skipping backend: %s",
                    backend.value,
                    error_msg,
                )
            else:
                logger.warning(
                    f"Docling parsing failed with {backend.value}: {error_msg}",
                    exc_info=True,
                )
            return ParseResult(
                doc=None,
                backend_used=f"docling+{backend.value}",
                success=False,
                error=error_msg,
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
        tesseract_module = None
        tessdata_path = None

        if backend == OCRBackend.TESSERACT:
            try:
                import tesserocr  # type: ignore
            except ImportError:
                logger.warning("Tesseract not available for image OCR stage")
                return []

            tessdata_path = self._resolve_tessdata_path()
            if tessdata_path is None:
                logger.warning("Skipping Tesseract image OCR stage: no usable tessdata path found")
                return []
            tesseract_module = tesserocr
        elif backend in {OCRBackend.RAPIDOCR, OCRBackend.PADDLEOCR}:
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
                easyocr_reader = self._create_easyocr_reader()
            except RuntimeError:
                logger.warning("EasyOCR not available for image OCR stage")
                return []
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
                    tesseract_text: str | None = None

                    try:
                        bbox_rect = pymupdf.Rect(bbox_raw)
                        if bbox_rect.width < 8 or bbox_rect.height < 8:
                            continue

                        pix = page.get_pixmap(clip=bbox_rect, dpi=216, alpha=False)
                        if rapidocr_reader is not None:
                            ocr_result = rapidocr_reader(self._pixmap_to_array(pix))
                        elif easyocr_reader is not None:
                            easyocr_result = cast(
                                list[Any],
                                cast(Any, easyocr_reader).readtext(
                                    self._pixmap_to_array(pix),
                                    detail=1,
                                ),
                            )
                        elif tesseract_module is not None:
                            tesseract_text = self._ocr_page_pixmap(
                                pix,
                                OCRBackend.TESSERACT,
                                tesseract_module=tesseract_module,
                                tessdata_path=tessdata_path,
                            )
                        else:
                            continue
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
                    elif tesseract_text is not None:
                        text = tesseract_text
                        if len(text) < self.image_ocr_min_chars:
                            continue
                        confidence = None
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
            supported, reason = self._supports_backend(backend)
            if not supported:
                logger.warning("Skipping image OCR backend %s: %s", backend.value, reason)
                continue

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
        1. Embedded-text-first ingestion gate (full or selective OCR per page)
        2. Docling + Tesseract/PaddleOCR/EasyOCR/RapidOCR
        3. Direct full-page OCR with the same backend order
        4. PyMuPDF (if pymupdf_fallback enabled)

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

        ocr_backends = self._configured_ocr_backends()

        embedded_result = self._try_embedded_text_first(pdf_path, ocr_backends)
        if embedded_result.success and embedded_result.doc and embedded_result.doc.text.strip():
            logger.info(f"Parsed {pdf_path.name} using {embedded_result.backend_used}")
            return embedded_result.doc

        if not ocr_backends:
            logger.warning("No usable OCR backends available; skipping directly to PyMuPDF fallback")

        for index, backend in enumerate(ocr_backends):
            result = self._try_docling(pdf_path, backend)
            if result.success and result.doc and result.doc.text.strip():
                parsed_doc = result.doc
                if self.enable_image_ocr:
                    snippets = self._extract_image_ocr_snippets_with_fallback(pdf_path, backend)
                    parsed_doc = self._append_image_ocr_spans(parsed_doc, snippets)
                logger.info(f"Parsed {pdf_path.name} using {result.backend_used}")
                return parsed_doc

            if index == len(ocr_backends) - 1:
                continue

            if result.success and result.doc and not result.doc.text.strip():
                logger.warning(
                    "%s returned empty content, retrying with next OCR backend...",
                    backend.value,
                )
            elif self._is_docling_layout_dtype_error(result.error):
                logger.warning(
                    "Docling layout model dtype mismatch detected for %s; continuing to next OCR backend",
                    backend.value,
                )
            else:
                logger.warning("Retrying with next OCR backend...")

        logger.info("Docling OCR methods exhausted, trying direct full-page OCR fallback")
        for index, backend in enumerate(ocr_backends):
            result = self._try_full_page_ocr(pdf_path, backend)
            if result.success and result.doc and result.doc.text.strip():
                logger.info(f"Parsed {pdf_path.name} using {result.backend_used}")
                return result.doc

            if index < len(ocr_backends) - 1:
                logger.warning("Retrying with next direct OCR backend...")

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
