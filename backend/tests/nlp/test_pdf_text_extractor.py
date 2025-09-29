from app.nlp.pdf_text_extractor import PyPDFTextExtractor
from app.services import SpaCyModelManager


def test_pdf_text_extractor(model_manager: SpaCyModelManager) -> None:
    extractor = PyPDFTextExtractor(model_manager=model_manager)
    assert extractor is not None
