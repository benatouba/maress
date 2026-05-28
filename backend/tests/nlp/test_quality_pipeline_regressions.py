from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
import spacy

from app.nlp.adapters import StudySiteResultAdapter, get_primary_study_site
from app.nlp.domain_models import ExtractionMetadata, ExtractionResult, GeoEntity
from app.nlp.extractors import BaseEntityExtractor
from app.nlp.factories import PipelineFactory
from app.nlp.model_config import ModelConfig
from app.nlp.pdf_parser import (
    DoclingPDFParser,
    EmbeddedTextAssessment,
    OCRBackend,
    ParseResult,
)
from docling.datamodel.base_models import ConversionStatus
from docling.datamodel.pipeline_options import PdfPipelineOptions
from app.nlp.validation import ExtractionValidator
from maress_types import CoordinateExtractionMethod, PaperSections


def make_extraction_metadata(
    total_entities: int = 0,
    coordinates: int = 0,
    clusters: int = 0,
    locations: int = 0,
) -> ExtractionMetadata:
    return ExtractionMetadata(
        total_sections_processed=1,
        average_text_quality=0.9,
        section_quality_scores={},
        total_entities=total_entities,
        coordinates=coordinates,
        clusters=clusters,
        locations=locations,
        stage_timings_ms={},
        filter_statistics={},
        entity_type_counts={},
    )


def test_docling_dtype_mismatch_keeps_trying_backends(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "placeholder.pdf"
    pdf_path.write_text("placeholder")

    nlp = spacy.blank("en")
    nlp.add_pipe("sentencizer")
    parser = DoclingPDFParser(nlp, enable_image_ocr=False)

    successful_doc = nlp("Study site coordinates 45.5, -122.3")
    attempted_backends: list[OCRBackend] = []

    def fake_try_docling(_pdf_path: Path, backend: OCRBackend) -> ParseResult:
        attempted_backends.append(backend)
        if backend == OCRBackend.TESSERACT:
            return ParseResult(
                doc=None,
                backend_used=f"docling+{backend.value}",
                success=False,
                error="expected scalar type Double but found Float",
            )

        return ParseResult(
            doc=successful_doc,
            backend_used=f"docling+{backend.value}",
            success=True,
        )

    monkeypatch.setattr(parser, "_try_docling", fake_try_docling)

    def fail_full_page_ocr(_pdf_path: Path, _backend: OCRBackend) -> ParseResult:
        raise AssertionError("Direct full-page OCR should not run when a later Docling backend succeeds")

    monkeypatch.setattr(parser, "_try_full_page_ocr", fail_full_page_ocr)

    doc = parser.parse(pdf_path)

    assert doc.text == successful_doc.text
    assert attempted_backends[:2] == [OCRBackend.TESSERACT, OCRBackend.EASYOCR]


def test_direct_full_page_ocr_runs_before_pymupdf(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "placeholder.pdf"
    pdf_path.write_text("placeholder")

    nlp = spacy.blank("en")
    nlp.add_pipe("sentencizer")
    parser = DoclingPDFParser(nlp, enable_image_ocr=False)

    docling_attempts: list[OCRBackend] = []
    full_page_attempts: list[OCRBackend] = []
    direct_ocr_doc = nlp("OCR recovered study site text from a scanned PDF")

    def fake_try_docling(_pdf_path: Path, backend: OCRBackend) -> ParseResult:
        docling_attempts.append(backend)
        return ParseResult(
            doc=None,
            backend_used=f"docling+{backend.value}",
            success=False,
            error="Docling failed",
        )

    def fake_try_full_page_ocr(_pdf_path: Path, backend: OCRBackend) -> ParseResult:
        full_page_attempts.append(backend)
        if backend == OCRBackend.TESSERACT:
            return ParseResult(
                doc=direct_ocr_doc,
                backend_used=f"fullpage+{backend.value}",
                success=True,
            )

        return ParseResult(
            doc=None,
            backend_used=f"fullpage+{backend.value}",
            success=False,
            error="no text",
        )

    monkeypatch.setattr(parser, "_try_docling", fake_try_docling)
    monkeypatch.setattr(parser, "_try_full_page_ocr", fake_try_full_page_ocr)

    def fail_pymupdf(_pdf_path: Path) -> ParseResult:
        raise AssertionError("PyMuPDF should not run when direct full-page OCR succeeds")

    monkeypatch.setattr(parser, "_try_pymupdf", fail_pymupdf)

    doc = parser.parse(pdf_path)

    assert doc.text == direct_ocr_doc.text
    assert docling_attempts == parser._configured_ocr_backends()
    assert full_page_attempts == [OCRBackend.TESSERACT]


def test_easyocr_reader_forces_float32_under_bad_default_dtype() -> None:
    torch = pytest.importorskip("torch")

    original_dtype = torch.get_default_dtype()
    try:
        torch.set_default_dtype(torch.float64)
        reader = DoclingPDFParser._create_easyocr_reader()

        assert next(reader.detector.parameters()).dtype == torch.float32

        recognizer = getattr(reader, "recognizer", None)
        assert recognizer is not None
        assert next(recognizer.parameters()).dtype == torch.float32
    finally:
        torch.set_default_dtype(original_dtype)


def test_configured_ocr_backends_skips_unusable_paddle(monkeypatch: pytest.MonkeyPatch) -> None:
    nlp = spacy.blank("en")
    parser = DoclingPDFParser(nlp, enable_image_ocr=False)

    monkeypatch.setattr(parser, "_resolve_tessdata_path", lambda: "/tmp/tessdata/")
    monkeypatch.setattr(parser, "_supports_paddle_backend", lambda: False)

    assert parser._configured_ocr_backends() == [
        OCRBackend.TESSERACT,
        OCRBackend.EASYOCR,
        OCRBackend.RAPIDOCR,
    ]


def test_parse_uses_filtered_backend_list(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "placeholder.pdf"
    pdf_path.write_text("placeholder")

    nlp = spacy.blank("en")
    nlp.add_pipe("sentencizer")
    parser = DoclingPDFParser(nlp, enable_image_ocr=False)

    attempted_backends: list[OCRBackend] = []
    successful_doc = nlp("Study site recovered after backend filtering")

    monkeypatch.setattr(
        parser,
        "_configured_ocr_backends",
        lambda: [OCRBackend.TESSERACT, OCRBackend.EASYOCR],
    )

    def fake_try_docling(_pdf_path: Path, backend: OCRBackend) -> ParseResult:
        attempted_backends.append(backend)
        if backend == OCRBackend.EASYOCR:
            return ParseResult(
                doc=successful_doc,
                backend_used=f"docling+{backend.value}",
                success=True,
            )

        return ParseResult(
            doc=None,
            backend_used=f"docling+{backend.value}",
            success=False,
            error="Docling failed",
        )

    monkeypatch.setattr(parser, "_try_docling", fake_try_docling)

    def fail_full_page_ocr(_pdf_path: Path, _backend: OCRBackend) -> ParseResult:
        raise AssertionError("Direct full-page OCR should not run when Docling succeeds")

    monkeypatch.setattr(parser, "_try_full_page_ocr", fail_full_page_ocr)

    doc = parser.parse(pdf_path)

    assert doc.text == successful_doc.text
    assert attempted_backends == [OCRBackend.TESSERACT, OCRBackend.EASYOCR]


def test_embedded_text_first_short_circuits_ocr(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "placeholder.pdf"
    pdf_path.write_text("placeholder")

    nlp = spacy.blank("en")
    nlp.add_pipe("sentencizer")
    parser = DoclingPDFParser(nlp, enable_image_ocr=False)

    embedded_doc = nlp("Embedded text already covers all pages")
    monkeypatch.setattr(
        parser,
        "_try_embedded_text_first",
        lambda _pdf_path, _backends: ParseResult(
            doc=embedded_doc,
            backend_used="embedded_text",
            success=True,
        ),
    )

    def fail_docling(_pdf_path: Path, _backend: OCRBackend) -> ParseResult:
        raise AssertionError("Docling OCR stage should not run when embedded text succeeds")

    monkeypatch.setattr(parser, "_try_docling", fail_docling)

    doc = parser.parse(pdf_path)

    assert doc.text == embedded_doc.text


def test_assess_embedded_text_identifies_low_text_pages(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "placeholder.pdf"
    pdf_path.write_text("placeholder")

    nlp = spacy.blank("en")
    parser = DoclingPDFParser(nlp, enable_image_ocr=False)

    class DummyPage:
        def __init__(self, text: str) -> None:
            self._text = text

        def get_text(self, _mode: str) -> str:
            return self._text

    class DummyPdf:
        def __init__(self, texts: list[str]) -> None:
            self._pages = [DummyPage(text) for text in texts]
            self.page_count = len(self._pages)

        def __getitem__(self, index: int) -> DummyPage:
            return self._pages[index]

        def close(self) -> None:
            return None

    texts = [
        "Dense embedded text page with substantial words " * 4,
        " ",
        "Short page",
    ]
    monkeypatch.setattr("app.nlp.pdf_parser.pymupdf.open", lambda _pdf_path: DummyPdf(texts))

    assessment = parser._assess_embedded_text(pdf_path)

    assert assessment.total_pages == 3
    assert assessment.pages_with_embedded_text == 1
    assert assessment.low_text_pages == [1, 2]
    assert assessment.has_embedded_text is True


def test_try_embedded_text_first_runs_selective_ocr_for_low_text_pages(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "placeholder.pdf"
    pdf_path.write_text("placeholder")

    nlp = spacy.blank("en")
    nlp.add_pipe("sentencizer")
    parser = DoclingPDFParser(nlp, enable_image_ocr=False)

    assessment = EmbeddedTextAssessment(
        page_texts=["Dense embedded text page " * 8, "", ""],
        low_text_pages=[1, 2],
        pages_with_embedded_text=1,
        total_pages=3,
    )
    monkeypatch.setattr(parser, "_assess_embedded_text", lambda _pdf_path: assessment)

    selective_attempts: list[OCRBackend] = []
    selective_doc = nlp("Combined embedded and selective OCR text")

    def fake_selective(
        _pdf_path: Path,
        *,
        backend: OCRBackend,
        assessment: EmbeddedTextAssessment,
    ) -> ParseResult:
        selective_attempts.append(backend)
        assert assessment.low_text_pages == [1, 2]
        if backend == OCRBackend.TESSERACT:
            return ParseResult(
                doc=selective_doc,
                backend_used=f"embedded+{backend.value}",
                success=True,
            )

        return ParseResult(
            doc=None,
            backend_used=f"embedded+{backend.value}",
            success=False,
            error="failed",
        )

    monkeypatch.setattr(parser, "_try_selective_page_ocr", fake_selective)

    result = parser._try_embedded_text_first(
        pdf_path,
        [OCRBackend.TESSERACT, OCRBackend.EASYOCR],
    )

    assert result.success is True
    assert result.doc is not None
    assert result.doc.text == selective_doc.text
    assert selective_attempts == [OCRBackend.TESSERACT]


def test_retry_docling_with_backend_text_forces_float32_default(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    torch = pytest.importorskip("torch")
    pdf_path = tmp_path / "placeholder.pdf"
    pdf_path.write_text("placeholder")

    nlp = spacy.blank("en")
    parser = DoclingPDFParser(nlp, enable_image_ocr=False)
    observed_dtypes: list[torch.dtype] = []

    class DummyResult:
        status = ConversionStatus.SUCCESS
        errors: list[object] = []
        document = object()

    class DummyConverter:
        def convert(self, _pdf_path: Path, *, raises_on_error: bool = False) -> DummyResult:
            del raises_on_error
            observed_dtypes.append(torch.get_default_dtype())
            return DummyResult()

    monkeypatch.setattr(
        "app.nlp.pdf_parser.DocumentConverter",
        lambda *args, **kwargs: DummyConverter(),
    )

    original_dtype = torch.get_default_dtype()
    try:
        torch.set_default_dtype(torch.float64)
        parser._retry_docling_with_backend_text(
            pdf_path,
            PdfPipelineOptions(),
            OCRBackend.TESSERACT,
        )
    finally:
        torch.set_default_dtype(original_dtype)

    assert observed_dtypes == [torch.float32]


def test_docling_tesseract_environment_sets_tessdata_prefix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "placeholder.pdf"
    pdf_path.write_text("placeholder")

    nlp = spacy.blank("en")
    parser = DoclingPDFParser(nlp, enable_image_ocr=False)
    observed_tessdata_prefixes: list[str | None] = []

    class DummyResult:
        status = ConversionStatus.SUCCESS
        errors: list[object] = []
        document = object()

    class DummyConverter:
        def convert(self, _pdf_path: Path, *, raises_on_error: bool = False) -> DummyResult:
            del raises_on_error
            observed_tessdata_prefixes.append(os.environ.get("TESSDATA_PREFIX"))
            return DummyResult()

    monkeypatch.setattr(
        "app.nlp.pdf_parser.DocumentConverter",
        lambda *args, **kwargs: DummyConverter(),
    )
    monkeypatch.setattr(parser, "_resolve_tessdata_path", lambda: "/tmp/tessdata/")

    original_tessdata_prefix = os.environ.pop("TESSDATA_PREFIX", None)
    try:
        parser._retry_docling_with_backend_text(
            pdf_path,
            PdfPipelineOptions(),
            OCRBackend.TESSERACT,
        )
    finally:
        if original_tessdata_prefix is not None:
            os.environ["TESSDATA_PREFIX"] = original_tessdata_prefix

    assert observed_tessdata_prefixes == ["/tmp/tessdata/"]
    assert "TESSDATA_PREFIX" not in os.environ


def test_try_docling_sets_tessdata_prefix_for_tesseract(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "placeholder.pdf"
    pdf_path.write_text("placeholder")

    nlp = spacy.blank("en")
    nlp.add_pipe("sentencizer")
    parser = DoclingPDFParser(nlp, enable_image_ocr=False)
    observed_tessdata_prefixes: list[str | None] = []

    class DummyDocument:
        texts = [object()]
        pages = {1: object()}

        def export_to_markdown(self) -> str:
            return "Study site description with enough text for validation."

    class DummyResult:
        document = DummyDocument()

    class DummyConverter:
        def convert(self, _pdf_path: Path) -> DummyResult:
            observed_tessdata_prefixes.append(os.environ.get("TESSDATA_PREFIX"))
            return DummyResult()

    monkeypatch.setattr(
        "app.nlp.pdf_parser.DocumentConverter",
        lambda *args, **kwargs: DummyConverter(),
    )
    monkeypatch.setattr(parser, "_resolve_tessdata_path", lambda: "/tmp/tessdata/")
    monkeypatch.setattr(parser, "_docling_to_spacy", lambda _doc: nlp("Study site text with content."))

    original_tessdata_prefix = os.environ.pop("TESSDATA_PREFIX", None)
    try:
        result = parser._try_docling(pdf_path, OCRBackend.TESSERACT)
    finally:
        if original_tessdata_prefix is not None:
            os.environ["TESSDATA_PREFIX"] = original_tessdata_prefix

    assert result.success is True
    assert observed_tessdata_prefixes == ["/tmp/tessdata/"]
    assert "TESSDATA_PREFIX" not in os.environ


def test_pipeline_factory_loads_spacy_model_under_float32_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    torch = pytest.importorskip("torch")
    observed_dtypes: list[torch.dtype] = []

    def fake_spacy_load(_model_name: str, *, disable: list[str] | None = None):
        del disable
        observed_dtypes.append(torch.get_default_dtype())
        return spacy.blank("en")

    monkeypatch.setattr("app.nlp.factories.spacy.load", fake_spacy_load)
    monkeypatch.setattr(PipelineFactory, "_configure_spacy_components", staticmethod(lambda nlp, _config: nlp))

    config = ModelConfig()
    original_dtype = torch.get_default_dtype()
    try:
        torch.set_default_dtype(torch.float64)
        PipelineFactory.create_pipeline(
            config=config,
            extractors=[],
            enable_geocoding=False,
            enable_clustering=False,
            enable_table_extraction=False,
            enable_improved_sentences=False,
            enable_quality_assessment=False,
            enable_enriched_context=False,
        )
    finally:
        torch.set_default_dtype(original_dtype)

    assert observed_dtypes == [torch.float32]


def test_base_extractor_lazy_spacy_load_uses_float32_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    torch = pytest.importorskip("torch")
    observed_dtypes: list[torch.dtype] = []

    class DummyExtractor(BaseEntityExtractor):
        def extract(self, text: str, section: str) -> list[GeoEntity]:
            del text, section
            return []

    def fake_spacy_load(_model_name: str):
        observed_dtypes.append(torch.get_default_dtype())
        return spacy.blank("en")

    monkeypatch.setattr("app.nlp.extractors.spacy.load", fake_spacy_load)

    extractor = DummyExtractor(ModelConfig())
    original_dtype = torch.get_default_dtype()
    try:
        torch.set_default_dtype(torch.float64)
        _ = extractor.nlp
    finally:
        torch.set_default_dtype(original_dtype)

    assert observed_dtypes == [torch.float32]


def test_study_site_selection_prefers_methods_coordinates() -> None:
    entities = [
        GeoEntity(
            text="45.5000, -122.3000",
            entity_type="COORDINATE",
            coordinates=(45.5, -122.3),
            context="Study site located at coordinates in the methods section",
            section="methods",
            confidence=0.82,
            start_char=0,
            end_char=18,
        ),
        GeoEntity(
            text="Santiago",
            entity_type="LOC",
            coordinates=(-33.4489, -70.6693),
            context="The abstract mentions observations near Santiago.",
            section="abstract",
            confidence=0.95,
            start_char=24,
            end_char=32,
        ),
    ]

    result = ExtractionResult(
        pdf_path=Path("test.pdf"),
        entities=entities,
        total_sections_processed=2,
        extraction_metadata=make_extraction_metadata(
            total_entities=2,
            coordinates=2,
            clusters=1,
            locations=1,
        ),
        doc=None,
        title="Study site extraction",
        cluster_info={"largest_cluster_size": 2},
        average_text_quality=0.92,
        section_quality_scores={},
    )

    study_sites = StudySiteResultAdapter.to_study_sites(
        result=result,
        item_id=uuid.uuid4(),
        min_confidence=0.5,
    )
    primary_site = get_primary_study_site(study_sites)

    assert primary_site is not None
    assert primary_site.section == PaperSections.METHODS
    assert primary_site.extraction_method == CoordinateExtractionMethod.REGEX

    methods_site = next(site for site in study_sites if site.section == PaperSections.METHODS)
    abstract_site = next(site for site in study_sites if site.section == PaperSections.ABSTRACT)
    assert methods_site.validation_score > abstract_site.validation_score
    assert study_sites[0].section == PaperSections.METHODS


def test_validator_accepts_extended_entity_types() -> None:
    result = ExtractionResult(
        pdf_path=Path("test.pdf"),
        entities=[
            GeoEntity(
                text="Pacific Northwest",
                entity_type="MULTIWORD_LOCATION",
                context="Study area in the Pacific Northwest",
                section="methods",
                confidence=0.74,
                start_char=0,
                end_char=18,
            ),
            GeoEntity(
                text="mangrove forest",
                entity_type="ECOSYSTEM",
                context="Mangrove forest study site",
                section="methods",
                confidence=0.68,
                start_char=19,
                end_char=35,
            ),
        ],
        total_sections_processed=1,
        extraction_metadata=make_extraction_metadata(total_entities=2),
        doc=None,
        title="Validation coverage",
        cluster_info={},
        average_text_quality=0.9,
        section_quality_scores={},
    )

    report = ExtractionValidator().validate_result(result)

    assert not any(issue.category == "entity_type" for issue in report.warnings)


def test_adapter_skips_bounding_box_candidates() -> None:
    result = ExtractionResult(
        pdf_path=Path("test.pdf"),
        entities=[
            GeoEntity(
                text="between 7 and 4 ; between 7 and 4",
                entity_type="BOUNDING_BOX",
                coordinates=(5.5, 5.5),
                bounding_box=(4.0, 4.0, 7.0, 7.0),
                context="Study area extent in other",
                section="other",
                confidence=1.0,
                start_char=0,
                end_char=31,
            ),
            GeoEntity(
                text="23°46'57\"South, 68°14'26\"West",
                entity_type="COORDINATE",
                coordinates=(-23.7825, -68.2406),
                context="Sampling station at 23°46'57\"South, 68°14'26\"West",
                section="methods",
                confidence=0.84,
                start_char=32,
                end_char=63,
            ),
        ],
        total_sections_processed=1,
        extraction_metadata=make_extraction_metadata(total_entities=2, coordinates=2),
        doc=None,
        title="Bounding box filtering",
        cluster_info={},
        average_text_quality=0.9,
        section_quality_scores={},
    )

    study_sites = StudySiteResultAdapter.to_study_sites(
        result=result,
        item_id=uuid.uuid4(),
        min_confidence=0.5,
    )

    assert len(study_sites) == 1
    assert study_sites[0].name.startswith("Site at ")
    assert all("between 7 and 4" not in site.name for site in study_sites)


def test_coordinate_name_extraction_rejects_institutional_phrase() -> None:
    entity = GeoEntity(
        text="23°41'03\"S, 68°03'29\"W",
        entity_type="COORDINATE",
        coordinates=(-23.6842, -68.0581),
        context=(
            "A meteorological station of the General Directorate of Water "
            "recorded conditions at 23°41'03\"S, 68°03'29\"W."
        ),
        section="methods",
        confidence=0.91,
        start_char=0,
        end_char=25,
    )

    name = StudySiteResultAdapter._extract_name(entity)

    assert name == 'Site at 23°41\'03"S, 68°03\'29"W'


def test_adapter_rejects_vague_geocoded_candidates() -> None:
    result = ExtractionResult(
        pdf_path=Path("test.pdf"),
        entities=[
            GeoEntity(
                text="near the study area",
                entity_type="CONTEXTUAL_LOCATION",
                coordinates=(-22.9, -68.2),
                context="Study sites were located near the study area.",
                section="methods",
                confidence=0.88,
                start_char=0,
                end_char=19,
            ),
            GeoEntity(
                text="Laguna Verde",
                entity_type="GPE",
                coordinates=(-22.8, -67.8),
                context="Study site located in Laguna Verde.",
                section="methods",
                confidence=0.83,
                start_char=20,
                end_char=33,
            ),
        ],
        total_sections_processed=1,
        extraction_metadata=make_extraction_metadata(total_entities=2, coordinates=2),
        doc=None,
        title="Vague geocoded candidates",
        cluster_info={},
        average_text_quality=0.9,
        section_quality_scores={},
    )

    study_sites = StudySiteResultAdapter.to_study_sites(
        result=result,
        item_id=uuid.uuid4(),
        min_confidence=0.5,
    )

    assert [site.name for site in study_sites] == ["Laguna Verde"]
