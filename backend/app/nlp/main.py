"""Study Site Extraction Pipeline for Scientific PDFs.

This module provides a maintainable, testable pipeline for extracting
geo-referenced study sites from scientific papers following SOLID
principles.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rich import print as rprint

from app.nlp.factories import PipelineFactory
from app.nlp.model_config import ModelConfig

if TYPE_CHECKING:
    import pandas as pd


def main() -> None:
    """Example usage of the extraction pipeline."""
    # Create config from model_config.py
    config = ModelConfig()
    pipeline = PipelineFactory.create_pipeline(config=config)

    # Process a PDF
    pdf_path = next(iter((Path.cwd() / "zotero_files").glob("*.pdf")))
    result = pipeline.extract_from_pdf(
        pdf_path,
        title="Late Holocene eruptive activity at Nevado Cayambe Volcano, Ecuador",
    )

    # Access results
    print(f"\nProcessed: {result.pdf_path.name}")
    print(f"Sections analysed: {result.total_sections_processed}")
    print(f"Total entities: {len(result.entities)}")
    print(f"Metadata: {result.extraction_metadata}")

    # High confidence entities
    high_conf = result.get_high_confidence_entities(threshold=config.MIN_CONFIDENCE)
    print(f"\nHigh confidence entities: {len(high_conf)}")

    # Explicit coordinates
    coords = result.get_entities_with_coordinates()
    print(f"Entities with coordinates: {len(coords)}")
    for entity in coords[:5]:
        print(f"  {entity.text}: {entity.coordinates}")

    # Convert to DataFrame
    df: pd.DataFrame = result.to_dataframe()

    rprint(df)
    df.to_csv("study_sites_extracted.csv", index=False)
    print("\nResults saved to study_sites_extracted.csv")


if __name__ == "__main__":
    main()
