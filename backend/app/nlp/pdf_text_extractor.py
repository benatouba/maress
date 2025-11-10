"""PyPDFTextExtractor: Scientific PDF text extraction with section-based processing.

This module provides efficient PDF processing for academic/scientific documents
with proper type annotations and model management.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict
from rich import print as rprint
from spacy.tokens import Doc
from spacy_layout import spaCyLayout

from app.services import SpaCyModelManager

if TYPE_CHECKING:
    from spacy.tokens import Span

# Type aliases for better readability
PathLike = str | Path
SectionDict = dict[str, Doc]
CaptionList = list[dict[str, Any]]
CoordinateList = list[str]
CleanResult = dict[str, SectionDict | CaptionList | Doc]


def serialize_span(v: Any) -> dict[str, Any]:
    """Convert Span to serializable dict."""
    if hasattr(v, "text"):  # It's a Span object
        return {
            "text": v.text,
            "start": v.start,
            "end": v.end,
            "start_char": v.start_char,
            "end_char": v.end_char,
            "label": v.label_ if hasattr(v, "label_") else None,
        }
    return v  # Already serialized


SerializedSpan = Annotated[dict[str, Any], BeforeValidator(serialize_span)]


class ExtractedPDF(BaseModel):
    sections: dict[str, str]
    captions: CaptionList
    tables: list[SerializedSpan]
    full_doc: Doc

    model_config: ConfigDict = ConfigDict(arbitrary_types_allowed=True)


class PyPDFTextExtractor:
    """Scientific PDF text extractor with section-based processing.

    This class provides methods to extract and clean text from
    scientific PDFs, organising content by sections and handling
    geographic coordinates.
    """

    def __init__(self, model_manager: SpaCyModelManager | None = None) -> None:
        """Initialize the PDF text extractor."""
        self.model_manager: SpaCyModelManager = model_manager or SpaCyModelManager()

    def clean_document_text(self, doc: Doc) -> list[Span]:
        """Remove headers, footers, author info, and other metadata.

        Args:
            doc: spaCy Doc object with layout information

        Returns:
            List of clean text spans without unwanted content
        """
        clean_spans: list[Span] = []

        for span in doc.spans["layout"]:
            # Skip unwanted content types
            if span.label_ in [
                "page_header",
                "page_footer",
                "footnote",
                "page_number",
                "reference",
                "bibliography",
            ]:
                continue

            # Filter by position - remove very top/bottom content
            layout_info = getattr(span._, "layout", None)
            if layout_info and hasattr(layout_info, "bbox"):
                bbox = layout_info.bbox
                page_height = getattr(layout_info, "page", {}).get("height", 1000)

                # Skip content in top 10% or bottom 10% of page
                if bbox.y1 < page_height * 0.1 or bbox.y0 > page_height * 0.9:
                    continue

            # Filter by content patterns
            text = span.text.strip()
            if (
                len(text) < 20
                or re.match(r"^[A-Z][a-z]+ [A-Z]\. [A-Z][a-z]+", text)
                or ("@" in text and len(text.split()) < 10)
                or re.match(r"^\d+$", text)
                or any(
                    keyword in text.lower()
                    for keyword in [
                        "copyright",
                        "©",
                        "journal",
                        "volume",
                        "doi:",
                        "manuscript",
                        "submitted",
                        "accepted",
                    ]
                )
            ):
                continue

            clean_spans.append(span)

        return clean_spans

    def extract_figure_captions(self, doc: Doc) -> CaptionList:
        """Extract figure captions separately from main text.

        Args:
            doc: spaCy Doc object with layout information

        Returns:
            List of dictionaries containing caption information with keys:
            - type: Always 'figure_caption'
            - text: Caption text content
            - position: Character position in document
            - layout: Layout information if available
        """
        captions: CaptionList = []

        for span in doc.spans["layout"]:
            text = span.text.strip()

            # Identify figure captions by pattern
            if (
                span.label_ in ["caption", "figure"]
                or re.match(r"^(Figure|Fig\.?|Table)\s+\d+", text, re.IGNORECASE)
                or re.match(r"^(Panel|Supplementary)\s+", text, re.IGNORECASE)
            ):
                captions.append(
                    {
                        "type": "figure_caption",
                        "text": text,
                        "position": span.start_char,
                        "layout": getattr(span._, "layout", None),
                    },
                )

        return captions

    def extract_tables(self, doc: Doc) -> list[Span]:
        """Extract table spans from the document.

        Args:
            doc: spaCy Doc object with layout information
        Returns:
            List of spans identified as tables
        """
        tables: list[Span] = []

        for span in doc.spans["layout"]:
            if span.label_ == "table":
                tables.append(span)

        return tables

    def fix_geographic_symbols(self, text: str) -> str:
        """Fix degree and second symbols for coordinate extraction.

        Args:
            text: Input text with potentially malformed symbols

        Returns:
            Text with corrected geographic symbols (°, ', ")
        """
        symbol_fixes = {
            # Degree symbol variants
            "°": "°",  # Ensure proper Unicode
            "\u00b0": "°",  # Standard degree
            "\u2103": "°C",  # Celsius
            "Â°": "°",  # Common encoding issue
            "â°": "°",
            "&deg;": "°",  # HTML entity
            # Second/minute symbols
            "″": '"',  # Double prime (seconds)
            "′": "'",  # Prime (minutes)
            "\u2033": '"',  # Double prime Unicode
            "\u2032": "'",  # Prime Unicode
            "&prime;": "'",
            "&Prime;": '"',
            # Fix common coordinate separators
            "Â ": " ",  # Non-breaking space issues
            "\xa0": " ",  # Non-breaking space
            # Remove line breaks
            "\n": " ",
        }

        for wrong, correct in symbol_fixes.items():
            text = text.replace(wrong, correct)

        return text

    def extract_sections(self, clean_spans: list[Span]) -> SectionDict:
        """Extract text organized by document sections.

        Args:
            clean_spans: List of cleaned text spans

        Returns:
            Dictionary mapping section names to their combined text content.
            Common sections: 'introduction', 'methods', 'results', 'discussion'
        """
        sections: dict[str, list[str]] = defaultdict(list)
        current_section = "introduction"

        for span in clean_spans:
            if span.label_ == "text":
                # Fix geographic symbols
                clean_text = self.fix_geographic_symbols(span.text)
                clean_text_start = re.sub(r"[^a-zA-Z]", "", clean_text.lstrip()[:30]).lower()

                # Determine section from heading context
                heading = str(getattr(span._, "heading", None))
                if heading:
                    heading_lower = heading.lower()
                    if any(
                        word in heading_lower
                        for word in ["method", "material", "experiment", "data"]
                    ) or clean_text_start.startswith(("method", "data", "material")):
                        current_section = "methods"
                    elif "abstract" in heading_lower or clean_text_start.startswith("abstract"):
                        current_section = "abstract"
                    elif any(
                        word in heading_lower for word in ["result", "finding"]
                    ) or clean_text_start.startswith("result"):
                        current_section = "results"
                    elif "discuss" in heading_lower or clean_text_start.startswith("discuss"):
                        current_section = "discussion"
                    elif any(
                        word in heading_lower for word in ["conclusion", "summary", "outlook"]
                    ) or clean_text_start.startswith(("conclusion", "outlook")):
                        current_section = "conclusion"
                    elif any(
                        word in heading_lower for word in ["intro", "background"]
                    ) or clean_text_start.startswith(("intro", "background")):
                        current_section = "introduction"
                    elif any(
                        word in heading_lower for word in ["reference", "bibliography"]
                    ) or clean_text_start.startswith(("reference", "bibliograph")):
                        current_section = "references"
                    else:
                        current_section = "other"

                sections[current_section].append(clean_text)

        # Join text within sections for complete spans
        return {section: " ".join(texts) for section, texts in sections.items()}

    def extract_coordinates(self, text: str) -> CoordinateList:
        """Extract geographic coordinates from cleaned text.

        Args:
            text: Input text to search for coordinates

        Returns:
            List of coordinate strings found in the text.
            Supports formats like: 45.123°N, 45°12'N, 45°12'30"N
        """
        patterns = [
            # Decimal degrees: 45.123°N, -122.456°W
            r"(\d+\.?\d*)[°]\s*([NS])\s*,?\s*(\d+\.?\d*)[°]\s*([EW])",
            # Degrees minutes: 45°12'N, 122°30'W
            r"(\d+)[°]\s*(\d+)[\'′]\s*([NS])\s*,?\s*(\d+)[°]\s*(\d+)[\'′]\s*([EW])",
            # Degrees minutes seconds: 45°12'30"N
            r"(\d+)[°]\s*(\d+)[\'′]\s*(\d+\.?\d*)[\"″]\s*([NS])\s*,?\s*(\d+)[°]\s*(\d+)[\'′]\s*(\d+\.?\d*)[\"″]\s*([EW])",
        ]

        coordinates: CoordinateList = []
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                coordinates.append(match.group())

        return coordinates

    def process_scientific_pdf(self, pdf_path: Path) -> ExtractedPDF:
        """Complete pipeline for scientific PDF processing.

        This is the main method that orchestrates the entire processing pipeline.

        Args:
            pdf_path: Path to the PDF file to process

        Returns:
            Dictionary containing:
            - sections: Dict mapping section names to clean text
            - captions: List of figure caption dictionaries
            - full_doc: Original spaCy Doc object for advanced processing

        Raises:
            FileNotFoundError: If the PDF file doesn't exist
        """
        if not pdf_path.exists():
            msg = f"PDF file not found: {pdf_path}"
            raise FileNotFoundError(msg)

        doc = self.model_manager.process_document(pdf_path)

        clean_spans = self.clean_document_text(doc)
        captions = self.extract_figure_captions(doc)
        sections = self.extract_sections(clean_spans)
        tables = self.extract_tables(doc)

        return ExtractedPDF.model_validate(
            {
                "sections": sections,
                "captions": captions,
                "tables": tables,
                "full_doc": doc,
            },
        )

    def extract_all_coordinates(self, result: CleanResult) -> dict[str, CoordinateList]:
        """Extract coordinates from all sections of processed document.

        Args:
            result: Result dictionary from process_scientific_pdf()

        Returns:
            Dictionary mapping section names to lists of coordinates found
            in each section. Empty sections are omitted.
        """
        section_coordinates: dict[str, CoordinateList] = {}

        sections = result.get("sections", {})
        for section_name, section_text in sections.items():
            coordinates = self.extract_coordinates(section_text)
            if coordinates:
                section_coordinates[section_name] = coordinates

        return section_coordinates


# Example usage:
if __name__ == "__main__":
    model_manager = SpaCyModelManager("en")
    extractor = PyPDFTextExtractor(model_manager)

    # Process first PDF in zotero_files directory
    pdf_paths = Path.cwd().joinpath("zotero_files").glob("*.pdf")

    try:
        layout = spaCyLayout(model_manager.nlp)
        for doc in layout.pipe(pdf_paths):
            print(doc._.layout)

        # for span in doc.spans["layout"]:
        #     rprint(f"{span.label_}: {span.text}")

        # result = extractor.process_scientific_pdf(pdf_path)
        #
        # print(f"Processed {pdf_path}")
        # for section, doc in result.sections.items():
        #     print(f"Section: {section}, Length: {len(doc)} tokens")
        #     rprint([doc.sent for doc in doc.sents][:2])
        #
        # captions = result.captions
        # coordinates = extractor.extract_all_coordinates(result.model_dump())
        #
        # print(f"Processed {pdf_path}")
        # print(f"Sections found: {list(result.sections.keys())}")
        # print(f"Figure captions: {len(captions)}")
        # print(f"Tables found: {len(result.tables)}")
        # for table in result.tables:
        #     print(f"Table text: {table.text}...")
        # print(f"Coordinates found: {sum(len(coords) for coords in coordinates.values())}")

    except FileNotFoundError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Processing error for {pdf_paths}: {e}")
