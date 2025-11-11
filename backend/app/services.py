from pathlib import Path

import spacy
from pyzotero import zotero
from spacy.language import Language
from spacy.tokens import Doc
from spacy_layout import spaCyLayout

from app.models import User


class Zotero(zotero.Zotero):
    def __init__(self, user: User, library_type: str = "user"):
        user_json = user.model_dump()
        print(f"Used api key: {user_json['enc_zotero_api_key']}")
        super().__init__(
            library_id=user_json["zotero_id"],
            library_type=library_type,
            api_key=user_json["enc_zotero_api_key"],
        )


class SpaCyModelManager:
    """Efficient model manager for spaCy and spacy-layout models.

    This class handles loading and caching of models to avoid repeated
    initialization when processing multiple documents.
    """

    def __init__(self, model_name: str = "en_core_web_lg") -> None:
        """Initialize model manager with specified spaCy model.

        Args:
            model_name: Name of the spaCy model to load (default: en_core_web_lg)
        """
        self.model_name: str = model_name
        self._nlp: Language
        self._layout: spaCyLayout | None = None
        self._is_loaded: bool = False
        self.load_models()

    def load_models(self) -> None:
        """Load spaCy and spacy-layout models if not already loaded."""
        if not self._is_loaded:
            print(f"Loading spaCy model: {self.model_name}")
            if len(self.model_name.strip()) <= 2:
                print("Short model name provided interpreted as language code. Loading spaCyLayout with blank model.")
                self._nlp = spacy.blank(self.model_name)
                print("Initialising spacy-layout")
                self._layout = spaCyLayout(
                    self._nlp,
                    headings=["section_header", "title", "page_header"],
                    separator="\n\n",
                )
            else:
                if self.model_name not in spacy.util.get_installed_models():
                    print(f"Model {self.model_name} not found. Downloading...")
                    spacy.cli.download(self.model_name)
                self._nlp = spacy.load(self.model_name)

            self._is_loaded = True
            print("Models loaded successfully")

    @property
    def nlp(self) -> Language:
        """Get the loaded spaCy model, loading if necessary."""
        if not self._is_loaded:
            self.load_models()
        return self._nlp

    @property
    def layout(self) -> spaCyLayout:
        """Get the loaded spacy-layout processor, loading if necessary."""
        if not self._is_loaded:
            self.load_models()
        return self._layout

    def process_document(self, pdf_path: Path) -> Doc:
        """Process a PDF document and return spaCy Doc object.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Processed spaCy Doc object with layout information

        Raises:
            FileNotFoundError: If the PDF file doesn't exist
        """
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        if not self._is_loaded:
            self.load_models()

        # Process with layout first, then apply spaCy pipeline
        doc = self._layout(pdf_path)
        doc = self._nlp(doc)
        return doc

