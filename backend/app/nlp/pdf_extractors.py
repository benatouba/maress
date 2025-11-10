import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, override

import camelot
import pandas as pd
from pydantic import BaseModel
import pypdf

from app.nlp.nlp_logger import logger



import re
from pathlib import Path
from typing import Any, list, dict, Optional, override
from pydantic import BaseModel
import pypdf
import logging

# Set up logging
logger = logging.getLogger(__name__)

class TextObject(BaseModel):
    text: str
    page_number: int
    section: str | None

class ExtractedContent(BaseModel):
    text_objects: list[TextObject]
    figures_captions: list[dict[str, Any]]
    tables_captions: list[dict[str, Any]]
    total_pages: int
    sections_found: list[str]

class PyPDFTextExtractor:
    """
    State-of-the-art PDF text extraction for scientific documents.

    Features:
    - Automatic section detection and organization
    - Comprehensive citation removal (multiple academic formats)
    - Figure and table caption extraction and removal
    - Advanced line break and hyphenation handling
    - Proper text cleaning and normalization
    - Structured output with Pydantic models
    """

    # Comprehensive section patterns for academic papers
    SECTION_PATTERNS = [
        # Standard academic sections with optional numbering
        re.compile(r'^\s*(?:\d+\.?\s*)?(?:abstract|summary)\s*$', re.IGNORECASE),
        re.compile(r'^\s*(?:\d+\.?\s*)?(?:introduction|background)\s*$', re.IGNORECASE),
        re.compile(r'^\s*(?:\d+\.?\s*)?(?:literature\s+review|related\s+work|prior\s+work)\s*$', re.IGNORECASE),
        re.compile(r'^\s*(?:\d+\.?\s*)?(?:methods?|methodology|materials?\s+and\s+methods?|experimental\s+setup)\s*$', re.IGNORECASE),
        re.compile(r'^\s*(?:\d+\.?\s*)?(?:results?|findings?|observations?)\s*$', re.IGNORECASE),
        re.compile(r'^\s*(?:\d+\.?\s*)?(?:discussion|analysis|interpretation)\s*$', re.IGNORECASE),
        re.compile(r'^\s*(?:\d+\.?\s*)?(?:results?\s+and\s+discussion)\s*$', re.IGNORECASE),
        re.compile(r'^\s*(?:\d+\.?\s*)?(?:conclusions?|conclusion|summary|concluding\s+remarks?)\s*$', re.IGNORECASE),
        re.compile(r'^\s*(?:\d+\.?\s*)?(?:acknowledgments?|acknowledgements?)\s*$', re.IGNORECASE),
        re.compile(r'^\s*(?:\d+\.?\s*)?(?:references?|bibliography|works?\s+cited|citations?)\s*$', re.IGNORECASE),
        re.compile(r'^\s*(?:\d+\.?\s*)?(?:appendix|appendices|supplementary|supporting\s+information|data\s+availability)\s*$', re.IGNORECASE),

        # Numbered sections (e.g., "1. Introduction", "2.1 Methods")
        re.compile(r'^\s*\d+(?:\.\d+)*\.?\s*[A-Z][A-Za-z\s]{2,50}\s*$'),

        # All caps sections (common in older papers)
        re.compile(r'^\s*[A-Z][A-Z\s&]{3,30}\s*$'),

        # Roman numeral sections
        re.compile(r'^\s*[IVX]+\.\s*[A-Z][A-Za-z\s]{2,30}\s*$'),
    ]

    # Sections to stop processing (end of main content)
    STOP_SECTIONS = [
        re.compile(r'^\s*(?:\d+\.?\s*)?(?:references?|bibliography|works?\s+cited)\s*$', re.IGNORECASE),
        re.compile(r'^\s*(?:\d+\.?\s*)?(?:appendix|appendices|supplementary)\s*$', re.IGNORECASE),
        re.compile(r'^\s*(?:\d+\.?\s*)?(?:acknowledgments?|acknowledgements?)\s*$', re.IGNORECASE),
        re.compile(r'^\s*(?:\d+\.?\s*)?(?:supporting\s+information|data\s+availability)\s*$', re.IGNORECASE),
    ]

    # Citation patterns - comprehensive patterns for academic citations
    CITATION_PATTERNS = [
        # Standard parenthetical: (Author, Year), (Author & Author, Year)
        re.compile(r'\(\s*[A-Z][a-z]+(?:\s*,?\s*[A-Z][a-z]*)*(?:\s*[&,]\s*[A-Z][a-z]+)*\s*,\s*(?:19|20)\d{2}[a-z]?\s*\)', re.IGNORECASE),

        # Et al. citations: (Author et al., Year)
        re.compile(r'\(\s*[A-Z][a-z]+\s*(?:et\s*al\.?|&\s*others)\s*,\s*(?:19|20)\d{2}[a-z]?\s*\)', re.IGNORECASE),

        # Multiple citations: (Author1, Year1; Author2, Year2)
        re.compile(r'\([^()]*?[A-Z][a-z]+[^()]*?(?:19|20)\d{2}[^()]*?(?:;[^()]*?[A-Z][a-z]+[^()]*?(?:19|20)\d{2}[^()]*?)+\)', re.IGNORECASE),

        # Special status citations: (Author, in press), (Author, submitted)
        re.compile(r'\(\s*[A-Z][a-z]+(?:\s*et\s*al\.?)?\s*,\s*(?:in\s*press|submitted|forthcoming|accepted|personal\s*communication)\s*\)', re.IGNORECASE),

        # Numbered citations: [1], [1,2], [1-3], [1,3-5]
        re.compile(r'\[\s*\d+(?:\s*[-–—,]\s*\d+)*(?:\s*,\s*\d+(?:\s*[-–—]\s*\d+)*)*\s*\]'),

        # Superscript-style citations
        re.compile(r'(?<=\w)\s*\d+(?:\s*,\s*\d+)*(?=\s*[.!?]|\s+[A-Z]|\s*$)'),

        # Nature-style citations: Author et al.1, Author1,2
        re.compile(r'[A-Z][a-z]+(?:\s*et\s*al\.?)?\s*\d+(?:\s*,\s*\d+)*(?=\s|[.!?])', re.IGNORECASE),

        # Remove isolated years in parentheses that might be citations
        re.compile(r'\(\s*(?:19|20)\d{2}[a-z]?\s*\)'),
    ]

    # Figure and table caption patterns
    FIGURE_PATTERNS = [
        re.compile(r'^\s*(?:figure|fig\.?)\s*\d+[A-Z]?[\.-:\s]', re.IGNORECASE),
        re.compile(r'^\s*(?:figure|fig\.?)\s*[A-Z]\d*[\.-:\s]', re.IGNORECASE),
        re.compile(r'^\s*(?:figure|fig\.?)\s*S\d+[\.-:\s]', re.IGNORECASE),  # Supplementary figures
    ]

    TABLE_PATTERNS = [
        re.compile(r'^\s*table\s*\d+[A-Z]?[\.-:\s]', re.IGNORECASE),
        re.compile(r'^\s*table\s*[A-Z]\d*[\.-:\s]', re.IGNORECASE),
        re.compile(r'^\s*table\s*S\d+[\.-:\s]', re.IGNORECASE),  # Supplementary tables
    ]

    def __init__(self):
        self.current_section = None
        self.sections_found = []
        self.figures_captions = []
        self.tables_captions = []

    def clean_line_breaks_and_hyphens(self, text: str) -> str:
        """Advanced line break and hyphenation handling."""
        lines = text.split('\n')
        processed_lines = []

        i = 0
        while i < len(lines):
            current_line = lines[i].strip()

            if not current_line:
                if processed_lines and processed_lines[-1]:
                    processed_lines.append('')
                i += 1
                continue

            # Check if line ends with a hyphen (potential word break)
            if current_line.endswith('-') and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and next_line[0].islower():
                    next_words = next_line.split()
                    if next_words:
                        word_part = current_line[:-1]
                        next_word = next_words[0]
                        merged_word = word_part + next_word

                        # Heuristic: if merged word looks valid, merge it
                        if (len(merged_word) > 2 and 
                            merged_word.isalpha() and 
                            not any(char.isupper() for char in next_word[1:])):

                            remaining_next_line = ' '.join(next_words[1:]) if len(next_words) > 1 else ''
                            current_line = current_line[:-1] + next_word + ' ' + remaining_next_line
                            i += 1
                        else:
                            current_line = current_line + ' ' + next_line
                            i += 1
                    else:
                        current_line = current_line[:-1]
                        i += 1

            # Handle sentences broken across lines (no hyphen)
            elif (i + 1 < len(lines) and 
                  not current_line.endswith(('.', '!', '?', ':', ';', '-', ')', ']', '}')) and 
                  lines[i + 1].strip() and 
                  lines[i + 1].strip()[0].islower()):

                next_line = lines[i + 1].strip()
                current_line = current_line + ' ' + next_line
                i += 1

            processed_lines.append(current_line)
            i += 1

        result = '\n'.join(processed_lines)
        result = re.sub(r'\n\s*\n\s*\n+', '\n\n', result)
        return result

    def remove_citations(self, text: str) -> str:
        """Remove academic citations using comprehensive patterns."""
        for pattern in self.CITATION_PATTERNS:
            text = pattern.sub(' ', text)

        # Clean up artifacts from citation removal
        text = re.sub(r'\s*,\s*,\s*', ', ', text)
        text = re.sub(r'\s*;\s*;+', ';', text)
        text = re.sub(r'\(\s*\)', '', text)
        text = re.sub(r'\[\s*\]', '', text)
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    def detect_section(self, text: str) -> Optional[str]:
        """Detect if text contains a section header."""
        lines = text.split('\n')

        for line in lines[:5]:
            line = line.strip()
            if len(line) < 3 or len(line) > 100:
                continue

            cleaned_line = re.sub(r'^\s*[\d\.-\*\•\)\]]+\s*', '', line).strip()

            for pattern in self.SECTION_PATTERNS:
                if pattern.match(line) or (cleaned_line and pattern.match(cleaned_line)):
                    section_name = cleaned_line if cleaned_line else line
                    section_name = re.sub(r'^\W+|\W+$', '', section_name)
                    return section_name.title() if section_name.islower() else section_name

        return None

    def is_stop_section(self, text: str) -> bool:
        """Check if we've reached a section where we should stop processing."""
        lines = text.split('\n')

        for line in lines[:3]:
            line = line.strip()
            if not line:
                continue

            for pattern in self.STOP_SECTIONS:
                if pattern.match(line):
                    return True
        return False

    def extract_figures_tables_captions(self, text: str, page_num: int) -> tuple[str, list[dict], list[dict]]:
        """Extract and remove figure/table captions from text."""
        lines = text.split('\n')
        cleaned_lines = []
        figures_found = []
        tables_found = []

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            if not line:
                cleaned_lines.append(line)
                i += 1
                continue

            is_figure = any(pattern.match(line) for pattern in self.FIGURE_PATTERNS)
            is_table = any(pattern.match(line) for pattern in self.TABLE_PATTERNS)

            if is_figure or is_table:
                caption_lines = [line]
                j = i + 1

                while (j < len(lines) and 
                       lines[j].strip() and 
                       len(lines[j].strip()) > 10 and
                       not lines[j].strip().startswith(('Figure', 'Table', 'Fig.')) and
                       not any(pattern.match(lines[j].strip()) for pattern in self.SECTION_PATTERNS)):
                    caption_lines.append(lines[j].strip())
                    j += 1

                caption_text = ' '.join(caption_lines).strip()

                match = re.match(r'^((?:Figure|Fig\.?|Table)\s*\d+[A-Z]?)', caption_text, re.IGNORECASE)
                identifier = match.group(1) if match else "Unknown"

                caption_data = {
                    'page': page_num,
                    'identifier': identifier,
                    'caption': caption_text,
                    'line_start': i,
                    'line_end': j - 1
                }

                if is_figure:
                    figures_found.append(caption_data)
                else:
                    tables_found.append(caption_data)

                logger.debug(f"Extracted {identifier} on page {page_num}")
                i = j
            else:
                cleaned_lines.append(line)
                i += 1

        return '\n'.join(cleaned_lines), figures_found, tables_found

    def clean_text(self, text: str) -> str:
        """Comprehensive text cleaning pipeline."""
        if not text:
            return ""

        # Remove common PDF artifacts
        text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*[-–—]+\s*\d+\s*[-–—]+\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*Page\s+\d+.*$', '', text, flags=re.MULTILINE | re.IGNORECASE)
        text = re.sub(r'^\s*\d+\s+of\s+\d+\s*$', '', text, flags=re.MULTILINE)

        # URLs and DOIs
        text = re.sub(r'https?://[^\s]+', '', text)
        text = re.sub(r'www\.[^\s]+', '', text)
        text = re.sub(r'doi:\s*[^\s]+', '', text, flags=re.IGNORECASE)
        text = re.sub(r'DOI\s*[:\s]\s*[^\s]+', '', text, flags=re.IGNORECASE)

        # Email addresses
        text = re.sub(r'\S+@\S+\.\S+', '', text)

        # Handle line breaks and hyphenation BEFORE citation removal
        text = self.clean_line_breaks_and_hyphens(text)

        # Remove citations
        text = self.remove_citations(text)

        # Remove common artifacts
        text = re.sub(r'\b(?:et\s+al\.?|ibid\.?|op\.?\s+cit\.?|cf\.?|viz\.?)\s*', '', text, flags=re.IGNORECASE)

        # Clean up punctuation artifacts
        text = re.sub(r'\s*[,;]\s*[,;]+', ',', text)
        text = re.sub(r'\s+([,.;!?])', r'\1', text)
        text = re.sub(r'([.!?])\s*([.!?])+', r'\1', text)

        # Normalize whitespace
        text = re.sub(r' +', ' ', text)
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        text = re.sub(r'^\s+|\s+$', '', text)

        return text

    @override
    def extract_text(self, pdf_path: Path) -> ExtractedContent:
        """Extract and structure text from PDF with enhanced processing."""
        try:
            with open(pdf_path, "rb") as file:
                reader = pypdf.PdfReader(file)
                text_objects = []
                self.current_section = None
                self.sections_found = []
                self.figures_captions = []
                self.tables_captions = []
                found_stop_section = False

                for page_num, page in enumerate(reader.pages, 1):
                    if found_stop_section:
                        break

                    raw_text = page.extract_text()
                    if not raw_text:
                        continue

                    if self.is_stop_section(raw_text):
                        logger.info(f"Found stop section on page {page_num}, ending extraction")
                        found_stop_section = True
                        break

                    # Extract figures and tables first
                    text_without_captions, page_figures, page_tables = self.extract_figures_tables_captions(raw_text, page_num)
                    self.figures_captions.extend(page_figures)
                    self.tables_captions.extend(page_tables)

                    # Detect section changes
                    detected_section = self.detect_section(text_without_captions)
                    if detected_section:
                        self.current_section = detected_section
                        if detected_section not in self.sections_found:
                            self.sections_found.append(detected_section)
                        logger.info(f"Detected section: {detected_section} on page {page_num}")

                    # Clean the text
                    cleaned_text = self.clean_text(text_without_captions)

                    if cleaned_text and len(cleaned_text.split()) > 5:
                        text_objects.append(TextObject(
                            text=cleaned_text,
                            page_number=page_num,
                            section=self.current_section
                        ))

                        logger.debug(f"Processed page {page_num}: {len(cleaned_text)} chars, section: {self.current_section}")

                return ExtractedContent(
                    text_objects=text_objects,
                    figures_captions=self.figures_captions,
                    tables_captions=self.tables_captions,
                    total_pages=len(text_objects),
                    sections_found=self.sections_found
                )

        except Exception as e:
            logger.error(f"Error extracting text from {pdf_path}: {e}")
            return ExtractedContent(
                text_objects=[],
                figures_captions=[],
                tables_captions=[],
                total_pages=0,
                sections_found=[]
            )

# class PyPDFTextExtractor(TextExtractor):
#     """Text extraction using PyPDF."""
#
#     SECTION_SKIP_PATTERNS: list[re.Pattern[str]] = [
#         re.compile(
#             r"^(?:references?|bibliography|appendix|supplementary|notes|data)$",
#             re.IGNORECASE,
#         ),
#         # line with the word "references" or similar and non-alphabetical characters before or after
#         # re.compile(r"^\s*[-—–—]*\s*(?:references?|bibliography|appendix|supplementary|notes|data)\s*[-—–—]*\s*$", re.IGNORECASE),
#     ]
#
#     def strip_non_alpha_ends(self, s: str) -> str:
#         return s.strip("0123456789!@#$%^&*()_+-=~`[]{}|\\:;\"'<>,.?/ \t\n\r")
#
#     def _is_nonprose_section(self, text: str) -> bool:
#         """Checks if a page/line contains the start of a non-prose section."""
#         for pattern in self.SECTION_SKIP_PATTERNS:
#             if pattern.search(text):
#                 logger.info(f"Detected non-prose section header: {text.strip()}")
#                 return True
#         return False
#
#     @override
#     def extract_text(self, pdf_path: Path) -> dict[str, Any]:
#         try:
#             with open(pdf_path, "rb") as file:
#                 reader = pypdf.PdfReader(file)
#                 pages_text = []
#                 found_section_cutoff = False
#
#                 for page_num, page in enumerate(reader.pages, 1):
#                     text = page.extract_text()
#                     if not text:
#                         continue
#
#                     for i, line in enumerate(text.splitlines()):
#                         cleaned_line = self.strip_non_alpha_ends(line.strip())
#                         logger.debug(
#                             f"Processing line {i + 1} on page {page_num}: {cleaned_line}"
#                         )
#                         if self._is_nonprose_section(cleaned_line):
#                             msg = f"Skipping page {page_num} due to non-prose section header."
#                             logger.info(msg)
#                             # Stop adding pages after hitting references etc.
#                             found_section_cutoff = True
#                             text = "\n".join(text.splitlines()[:i])
#                             break
#
#                     if found_section_cutoff:
#                         # Stop adding pages after hitting references etc.
#                         break
#
#                     if page_num <= 2 and "introduction" in text.lower():
#                         idx = text.lower().find("introduction")
#                         if idx != -1:
#                             text = text[idx:]
#                     # go through lines and lstrip numbers
#                     text_lines = text.splitlines()
#                     text_lines = [
#                         line.strip("0123456789. ")
#                         for line in text_lines
#                         if line.strip()
#                     ]
#                     text = "\n".join(text_lines)
#                     # Remove text in parentheses
#                     text = re.sub(r"\(.*?\)", "", text)
#                     # Remove extra whitespace
#                     text = re.sub(r"\s+", " ", text).strip()
#                     logger.debug(
#                         f"Extracted text from page {page_num}: {text[:100]}...{text[-100:]}"
#                     )
#                     pages_text.append(
#                         {
#                             "page_number": page_num,
#                             "text": text,
#                             "word_count": len(text.split()),
#                         }
#                     )
#
#                 return {
#                     "pages": pages_text,
#                     "full_text": "\n".join([p["text"] for p in pages_text]),
#                     "total_pages": len(pages_text),  # Use filtered count
#                 }
#         except Exception as e:
#             logger.error(f"Error extracting text from {pdf_path}: {e}")
#             return {"pages": [], "full_text": "", "total_pages": 0}
#
#
# class CamelotTableExtractor:
#     """Table extraction using Camelot."""
#
#     def extract_tables(self, pdf_path: Path) -> list[pd.DataFrame]:
#         """Extract tables from PDF using Camelot."""
#         try:
#             # Try lattice first (for tables with borders)
#             tables = camelot.read_pdf(str(pdf_path), pages="all", flavor="lattice")
#
#             tables_detected = any(t.df.all().all() for t in tables) if tables else False
#             if not tables_detected:
#                 # Fall back to stream (for tables without borders)
#                 tables = camelot.read_pdf(str(pdf_path), pages="all", flavor="stream")
#
#             table_data = []
#             for i, table in enumerate(tables):
#                 df = table.df
#                 if df.empty or not df.all().all():
#                     logger.debug(
#                         f"Skipping empty or invalid table {i + 1} on page {table.parsing_report['page']}"
#                     )
#                     continue
#                 df.attrs["page_number"] = table.parsing_report["page"]
#                 df.attrs["table_number"] = i + 1
#                 df.attrs["accuracy"] = table.accuracy
#                 table_data.append(df)
#
#             logger.info(f"Extracted {len(table_data)} tables from {pdf_path}")
#             return table_data
#
#         except Exception as e:
#             logger.error(f"Error extracting tables from {pdf_path}: {e}")
#             return []


if __name__ == "__main__":
    pdf_folder = Path.cwd() / "zotero_files"
    pdf_path = next(iter(pdf_folder.glob("*.pdf")))
    extractor = PyPDFTextExtractor()

    if pdf_path.exists():
        # You can also provide a title for better geocoding bias
        text = extractor.extract_text(pdf_path)

        print(f"Text: {text}")
