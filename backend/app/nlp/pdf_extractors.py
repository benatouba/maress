import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, override

import camelot
import pandas as pd
import pypdf

from .nlp_logger import logger


class TextExtractor(ABC):
    """Abstract base class for text extraction from PDFs."""

    @abstractmethod
    def extract_text(self, pdf_path: Path) -> dict[str, Any]:
        pass


class PyPDFTextExtractor(TextExtractor):
    """Text extraction using PyPDF."""

    SECTION_SKIP_PATTERNS: list[re.Pattern[str]] = [
        re.compile(
            r"^(?:references?|bibliography|appendix|supplementary|notes|data)$",
            re.IGNORECASE,
        ),
        # line with the word "references" or similar and non-alphabetical characters before or after
        # re.compile(r"^\s*[-—–—]*\s*(?:references?|bibliography|appendix|supplementary|notes|data)\s*[-—–—]*\s*$", re.IGNORECASE),
    ]

    def strip_non_alpha_ends(self, s: str) -> str:
        return s.strip("0123456789!@#$%^&*()_+-=~`[]{}|\\:;\"'<>,.?/ \t\n\r")

    def _is_nonprose_section(self, text: str) -> bool:
        """Checks if a page/line contains the start of a non-prose section."""
        for pattern in self.SECTION_SKIP_PATTERNS:
            if pattern.search(text):
                logger.info(f"Detected non-prose section header: {text.strip()}")
                return True
        return False

    @override
    def extract_text(self, pdf_path: Path) -> dict[str, Any]:
        try:
            with open(pdf_path, "rb") as file:
                reader = pypdf.PdfReader(file)
                pages_text = []
                found_section_cutoff = False

                for page_num, page in enumerate(reader.pages, 1):
                    text = page.extract_text()
                    if not text:
                        continue

                    for i, line in enumerate(text.splitlines()):
                        cleaned_line = self.strip_non_alpha_ends(line.strip())
                        logger.debug(
                            f"Processing line {i + 1} on page {page_num}: {cleaned_line}"
                        )
                        if self._is_nonprose_section(cleaned_line):
                            msg = f"Skipping page {page_num} due to non-prose section header."
                            logger.info(msg)
                            # Stop adding pages after hitting references etc.
                            found_section_cutoff = True
                            text = "\n".join(text.splitlines()[:i])
                            break

                    if found_section_cutoff:
                        # Stop adding pages after hitting references etc.
                        break

                    if page_num <= 2 and "introduction" in text.lower():
                        idx = text.lower().find("introduction")
                        if idx != -1:
                            text = text[idx:]
                    # go through lines and lstrip numbers
                    text_lines = text.splitlines()
                    text_lines = [
                        line.strip("0123456789. ")
                        for line in text_lines
                        if line.strip()
                    ]
                    text = "\n".join(text_lines)
                    # Remove text in parentheses
                    text = re.sub(r"\(.*?\)", "", text)
                    # Remove extra whitespace
                    text = re.sub(r"\s+", " ", text).strip()
                    logger.debug(
                        f"Extracted text from page {page_num}: {text[:100]}...{text[-100:]}"
                    )
                    pages_text.append(
                        {
                            "page_number": page_num,
                            "text": text,
                            "word_count": len(text.split()),
                        }
                    )

                return {
                    "pages": pages_text,
                    "full_text": "\n".join([p["text"] for p in pages_text]),
                    "total_pages": len(pages_text),  # Use filtered count
                }
        except Exception as e:
            logger.error(f"Error extracting text from {pdf_path}: {e}")
            return {"pages": [], "full_text": "", "total_pages": 0}


class CamelotTableExtractor:
    """Table extraction using Camelot."""

    def extract_tables(self, pdf_path: Path) -> list[pd.DataFrame]:
        """Extract tables from PDF using Camelot."""
        try:
            # Try lattice first (for tables with borders)
            tables = camelot.read_pdf(str(pdf_path), pages="all", flavor="lattice")

            tables_detected = any(t.df.all().all() for t in tables) if tables else False
            if not tables_detected:
                # Fall back to stream (for tables without borders)
                tables = camelot.read_pdf(str(pdf_path), pages="all", flavor="stream")

            table_data = []
            for i, table in enumerate(tables):
                df = table.df
                if df.empty or not df.all().all():
                    logger.debug(
                        f"Skipping empty or invalid table {i + 1} on page {table.parsing_report['page']}"
                    )
                    continue
                df.attrs["page_number"] = table.parsing_report["page"]
                df.attrs["table_number"] = i + 1
                df.attrs["accuracy"] = table.accuracy
                table_data.append(df)

            logger.info(f"Extracted {len(table_data)} tables from {pdf_path}")
            return table_data

        except Exception as e:
            logger.error(f"Error extracting tables from {pdf_path}: {e}")
            return []
