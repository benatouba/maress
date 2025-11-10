"""Improved sentence boundary detection for scientific text.

Scientific papers have many abbreviations and special formats that
confuse standard sentence boundary detectors. This module provides
custom rules optimized for scientific text.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from spacy.language import Language
from spacy.symbols import ORTH

from app.nlp.nlp_logger import logger

if TYPE_CHECKING:
    from spacy.tokens import Doc


# Scientific abbreviations that should not trigger sentence breaks
SCIENTIFIC_ABBREVIATIONS = [
    # Common Latin abbreviations
    "et al",
    "e.g",
    "i.e",
    "vs",
    "cf",
    "viz",
    "etc",
    "ibid",
    # Figure and table references
    "Fig",
    "Figs",
    "Tab",
    "Tabs",
    "Eq",
    "Eqs",
    "Suppl",
    "Appendix",
    # Titles and degrees
    "Dr",
    "Prof",
    "Ph.D",
    "M.Sc",
    "B.Sc",
    "M.D",
    "Jr",
    "Sr",
    # Months
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Sept",
    "Oct",
    "Nov",
    "Dec",
    # Scientific terms
    "approx",
    "ca",
    "est",
    "max",
    "min",
    "temp",
    "elev",
    "lat",
    "lon",
    "alt",
    "vol",
    "no",
    "p",
    "pp",
    "n",
    "sp",
    "spp",
    "subsp",
    "var",
    "gen",
    # Units
    "mm",
    "cm",
    "km",
    "ml",
    "mg",
    "kg",
    "ha",
]


def add_scientific_abbreviations(nlp: Language) -> Language:
    """Add scientific abbreviations as special cases to prevent sentence breaks.

    Args:
        nlp: spaCy Language model

    Returns:
        Modified Language model with special cases added
    """
    logger.info(f"Adding {len(SCIENTIFIC_ABBREVIATIONS)} scientific abbreviations to tokenizer")

    for abbrev in SCIENTIFIC_ABBREVIATIONS:
        # Add with period as special case
        nlp.tokenizer.add_special_case(f"{abbrev}.", [{ORTH: f"{abbrev}."}])

    return nlp


@Language.component("scientific_sentencizer")
def scientific_sentencizer(doc: Doc) -> Doc:
    """Custom sentence boundary detection for scientific text.

    Handles:
    - List numbering: "(1) Site A" - don't split after )
    - Parenthetical citations: "(Smith et al., 2020)" - don't split after )
    - Coordinates: "45°30'15\"N, 122°30'W" - don't split at comma
    - Multi-part figures: "Fig. 1A-C" - don't split at hyphen

    Args:
        doc: spaCy Doc object

    Returns:
        Modified Doc with corrected sentence boundaries
    """
    # Handle list numbering: (1) Site A, (2) Site B
    for i, token in enumerate(doc[:-1]):
        if token.text == ")":
            # Check if preceded by digit or letter: (1) or (a)
            if i > 0 and (doc[i - 1].text.isdigit() or doc[i - 1].text.isalpha()):
                # Next non-space token is NOT a sentence start
                next_idx = i + 1
                while next_idx < len(doc) and doc[next_idx].is_space:
                    next_idx += 1
                if next_idx < len(doc):
                    doc[next_idx].is_sent_start = False

    # Handle coordinate commas: "45°30'N, 122°30'W"
    # Don't start sentence after comma if surrounded by coordinates
    for i, token in enumerate(doc[:-1]):
        if token.text == ",":
            # Check if in coordinate context (has degree symbols nearby)
            window_start = max(0, i - 5)
            window_end = min(len(doc), i + 6)
            window_text = doc[window_start:window_end].text

            if any(symbol in window_text for symbol in ["°", "'", '"', "N", "S", "E", "W"]):
                # Likely coordinate comma, don't start sentence
                if i + 1 < len(doc):
                    doc[i + 1].is_sent_start = False

    # Handle figure references: "Fig. 1A" - don't split between Fig. and number
    for i, token in enumerate(doc[:-2]):
        if token.text.lower() in ["fig", "figure", "table", "tab", "eq"]:
            # If next token is period, and token after that is digit
            if doc[i + 1].text == "." and doc[i + 2].text[0].isdigit():
                doc[i + 2].is_sent_start = False

    return doc


def improve_sentence_boundaries(nlp: Language) -> Language:
    """Add all sentence boundary improvements to spaCy pipeline.

    This is the main function to call when setting up the pipeline.

    Args:
        nlp: spaCy Language model

    Returns:
        Modified Language model with improved sentence boundary detection
    """
    # Add scientific abbreviations
    nlp = add_scientific_abbreviations(nlp)

    # Add custom sentencizer component if not already present
    if "scientific_sentencizer" not in nlp.pipe_names:
        # Add after parser (which does initial sentence segmentation)
        if "parser" in nlp.pipe_names:
            nlp.add_pipe("scientific_sentencizer", after="parser")
            logger.info("Added scientific_sentencizer after parser")
        else:
            # If no parser, add at the end
            nlp.add_pipe("scientific_sentencizer", last=True)
            logger.info("Added scientific_sentencizer at end of pipeline")
    else:
        logger.info("scientific_sentencizer already in pipeline")

    return nlp


# Example usage and testing
if __name__ == "__main__":
    import spacy

    # Load model and improve sentence boundaries
    nlp = spacy.load("en_core_web_sm")
    nlp = improve_sentence_boundaries(nlp)

    # Test cases
    test_texts = [
        # Test 1: et al. should not split
        "Study by Smith et al. The coordinates were recorded.",
        # Test 2: List numbering
        "Sites were: (1) Ecuador, (2) Peru, (3) Chile. Data was collected.",
        # Test 3: Coordinate commas
        "Location at 45°30'N, 122°30'W. The site was established.",
        # Test 4: Figure references
        "As shown in Fig. 1A. The pattern is clear.",
        # Test 5: Months
        "Sampling from Jan. 2020 to Dec. 2020 was conducted.",
    ]

    print("Testing improved sentence boundaries:\n")
    for i, text in enumerate(test_texts, 1):
        doc = nlp(text)
        print(f"Test {i}: {text}")
        print(f"  Sentences: {[sent.text.strip() for sent in doc.sents]}")
        print()
