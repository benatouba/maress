from pathlib import Path
from app.nlp.pdf_text_extractor import PyPDFTextExtractor
from app.services import SpaCyModelManager
import pytest

@pytest.fixture(scope="module")
def model_manager() -> SpaCyModelManager:
    return SpaCyModelManager()

@pytest.fixture(scope="module")
def example_pdf_path() -> Path:
    return Path(__file__).parent / "example.pdf"

def test_pdf_text_extractor() -> None:
    extractor = PyPDFTextExtractor()
    assert extractor is not None
