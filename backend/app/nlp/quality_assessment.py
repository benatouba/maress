"""Text quality assessment for PDF extraction.

This module provides quality scoring for extracted text to identify
poor-quality extractions that may affect NLP accuracy.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.nlp.nlp_logger import logger


@dataclass
class QualityScore:
    """Quality assessment scores for extracted text."""

    char_ratio: float  # Ratio of alphanumeric characters (0-1)
    word_completeness: float  # Ratio of complete words (0-1)
    encoding_health: float  # Encoding quality (0-1)
    line_fragmentation: float  # Line fragmentation score (0-1, higher is better)
    whitespace_health: float  # Whitespace normality (0-1)
    overall_score: float  # Combined overall score (0-1)

    def __str__(self) -> str:
        """Human-readable quality summary."""
        if self.overall_score >= 0.8:
            quality = "excellent"
        elif self.overall_score >= 0.7:
            quality = "good"
        elif self.overall_score >= 0.5:
            quality = "fair"
        else:
            quality = "poor"

        return (
            f"Quality: {quality} (score={self.overall_score:.2f}) - "
            f"chars={self.char_ratio:.2f}, words={self.word_completeness:.2f}, "
            f"encoding={self.encoding_health:.2f}"
        )


class TextQualityAssessor:
    """Assess text extraction quality to identify problematic sections.

    Quality issues can indicate:
    - OCR errors or poor PDF extraction
    - Encoding problems (mojibake)
    - Scanned PDFs without proper text layer
    - Corrupted or malformed documents
    """

    # Common encoding corruption indicators
    ENCODING_CORRUPTION_PATTERNS = [
        "â€™",  # UTF-8 mojibake for '
        "â€œ",  # UTF-8 mojibake for "
        "â€",  # UTF-8 mojibake for "
        "â€¦",  # UTF-8 mojibake for …
        "Ã©",  # UTF-8 mojibake for é
        "Ã±",  # UTF-8 mojibake for ñ
        "ï¿½",  # Replacement character
        "\\x",  # Escaped hex characters
    ]

    # Common English words for vocabulary check
    COMMON_WORDS = {
        "the",
        "be",
        "to",
        "of",
        "and",
        "a",
        "in",
        "that",
        "have",
        "it",
        "for",
        "not",
        "on",
        "with",
        "as",
        "you",
        "do",
        "at",
        "this",
        "but",
        "his",
        "by",
        "from",
        "they",
        "we",
        "say",
        "her",
        "she",
        "or",
        "an",
        "will",
        "my",
        "one",
        "all",
        "would",
        "there",
        "their",
        # Scientific terms
        "study",
        "site",
        "data",
        "method",
        "result",
        "analysis",
        "sample",
        "test",
        "area",
        "location",
        "research",
        "species",
        "population",
        "measurement",
        "experiment",
    }

    def assess_quality(self, text: str) -> QualityScore:
        """Assess overall text quality.

        Args:
            text: Extracted text to assess

        Returns:
            QualityScore with individual and overall metrics
        """
        if not text or len(text) < 10:
            return QualityScore(
                char_ratio=0.0,
                word_completeness=0.0,
                encoding_health=0.0,
                line_fragmentation=0.0,
                whitespace_health=0.0,
                overall_score=0.0,
            )

        char_ratio = self._alpha_numeric_ratio(text)
        word_completeness = self._word_completeness_score(text)
        encoding_health = self._encoding_health_score(text)
        line_fragmentation = self._fragmentation_score(text)
        whitespace_health = self._whitespace_health_score(text)

        # Weighted overall score (prioritize encoding and word completeness)
        overall = (
            char_ratio * 0.15
            + word_completeness * 0.30
            + encoding_health * 0.25
            + line_fragmentation * 0.15
            + whitespace_health * 0.15
        )

        return QualityScore(
            char_ratio=char_ratio,
            word_completeness=word_completeness,
            encoding_health=encoding_health,
            line_fragmentation=line_fragmentation,
            whitespace_health=whitespace_health,
            overall_score=overall,
        )

    def _alpha_numeric_ratio(self, text: str) -> float:
        """Calculate ratio of alphanumeric characters to total.

        High ratio indicates clean text extraction.
        Low ratio may indicate garbled extraction or excessive formatting.
        """
        if not text:
            return 0.0

        alpha_num = sum(c.isalnum() or c.isspace() for c in text)
        return alpha_num / len(text)

    def _word_completeness_score(self, text: str) -> float:
        """Calculate ratio of complete words to total tokens.

        Uses common word dictionary and reasonable word patterns.
        Low score indicates fragmented or corrupted text.
        """
        words = text.lower().split()
        if not words:
            return 0.0

        complete_words = 0
        for word in words:
            # Remove punctuation
            clean_word = re.sub(r"[^\w]", "", word)
            if not clean_word:
                continue

            # Check if it's a known word or looks like a valid word
            if (
                clean_word in self.COMMON_WORDS
                or len(clean_word) >= 3
                and clean_word.isalpha()
            ):
                complete_words += 1

        return complete_words / len(words)

    def _encoding_health_score(self, text: str) -> float:
        """Assess text encoding health.

        Looks for mojibake and encoding corruption patterns.
        Returns 1.0 for clean encoding, lower for problems.
        """
        if not text:
            return 0.0

        # Count corruption indicators
        corruption_count = 0
        for pattern in self.ENCODING_CORRUPTION_PATTERNS:
            corruption_count += text.count(pattern)

        # Penalize based on corruption density
        corruption_density = corruption_count / len(text) * 1000
        health_score = max(0.0, 1.0 - corruption_density)

        # Check for excessive non-ASCII that might indicate problems
        non_ascii_ratio = sum(1 for c in text if ord(c) > 127) / len(text)
        if non_ascii_ratio > 0.3:  # More than 30% non-ASCII is suspicious
            health_score *= 0.8

        return health_score

    def _fragmentation_score(self, text: str) -> float:
        """Assess line fragmentation.

        Fragmented text has many very short lines, indicating
        poor extraction or OCR issues.
        """
        lines = text.split("\n")
        if not lines:
            return 0.0

        # Count lines by length
        very_short_lines = sum(1 for line in lines if 0 < len(line.strip()) < 10)
        short_lines = sum(1 for line in lines if 10 <= len(line.strip()) < 30)
        normal_lines = sum(1 for line in lines if len(line.strip()) >= 30)

        total_content_lines = very_short_lines + short_lines + normal_lines
        if total_content_lines == 0:
            return 0.0

        # Calculate score (prefer longer lines)
        score = (normal_lines * 1.0 + short_lines * 0.5 + very_short_lines * 0.1) / (
            total_content_lines
        )

        return min(1.0, score)

    def _whitespace_health_score(self, text: str) -> float:
        """Assess whitespace normality.

        Excessive or irregular whitespace indicates extraction problems.
        """
        if not text:
            return 0.0

        # Check for excessive spaces
        multiple_spaces = len(re.findall(r"  +", text))
        space_density = multiple_spaces / len(text) * 100

        # Check for excessive newlines
        multiple_newlines = len(re.findall(r"\n\n\n+", text))
        newline_density = multiple_newlines / len(text) * 100

        # Calculate score (penalize excessive whitespace)
        space_score = max(0.0, 1.0 - space_density)
        newline_score = max(0.0, 1.0 - newline_density)

        return (space_score + newline_score) / 2

    def should_process_text(
        self, text: str, min_quality: float = 0.5
    ) -> tuple[bool, QualityScore]:
        """Determine if text quality is sufficient for processing.

        Args:
            text: Text to assess
            min_quality: Minimum acceptable quality score (0-1)

        Returns:
            Tuple of (should_process: bool, quality_score: QualityScore)
        """
        quality = self.assess_quality(text)

        if quality.overall_score < min_quality:
            logger.warning(
                f"Text quality below threshold: {quality.overall_score:.2f} < {min_quality:.2f}"
            )
            logger.debug(f"Quality details: {quality}")
            return False, quality

        return True, quality

    def assess_section_quality(
        self, sections: dict[str, str]
    ) -> dict[str, QualityScore]:
        """Assess quality for all document sections.

        Args:
            sections: Dictionary mapping section names to text content

        Returns:
            Dictionary mapping section names to QualityScore objects
        """
        quality_scores = {}

        for section_name, section_text in sections.items():
            quality = self.assess_quality(section_text)
            quality_scores[section_name] = quality

            if quality.overall_score < 0.7:
                logger.warning(
                    f"Section '{section_name}' has poor quality: {quality.overall_score:.2f}"
                )
                logger.debug(f"  Details: {quality}")

        # Log summary
        avg_quality = (
            sum(q.overall_score for q in quality_scores.values()) / len(quality_scores)
            if quality_scores
            else 0.0
        )
        logger.info(
            f"Average section quality: {avg_quality:.2f} across {len(quality_scores)} sections"
        )

        return quality_scores


# Example usage
if __name__ == "__main__":
    assessor = TextQualityAssessor()

    # Test with good quality text
    good_text = """
    Study sites were located in Ecuador at coordinates 45.5°N, 122.3°W.
    The research area encompassed three distinct ecological zones with
    varying elevation gradients. Data collection occurred from January
    to December 2020 using standardized protocols.
    """
    good_score = assessor.assess_quality(good_text)
    print(f"Good text: {good_score}")

    # Test with poor quality text (fragmented)
    bad_text = """
    S t u d y
    s i t e s
    w e r e
    l o c a t e d
    """
    bad_score = assessor.assess_quality(bad_text)
    print(f"Bad text (fragmented): {bad_score}")

    # Test with encoding issues
    mojibake_text = """
    Study sites were located in SÃ£o Paulo at coordinates 45Â°30â€²N.
    The research area encompassed â€œthree distinct ecological zonesâ€.
    """
    mojibake_score = assessor.assess_quality(mojibake_text)
    print(f"Mojibake text: {mojibake_score}")
