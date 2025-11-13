from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelConfig(BaseSettings):
    """Configuration for NLP models and pipeline settings."""

    model_config = SettingsConfigDict(  # pyright: ignore[reportUnannotatedClassAttribute]
        env_prefix="NLP_",
        env_file="../.env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    # Transformer model settings
    NER_MODEL_NAME: str = Field(
        default="dslim/bert-base-NER",
        description="Hugging Face model for NER",
    )
    DEVICE: int = Field(default=-1, description="Device ID (-1 for CPU or GPU ID)")

    # spaCy settings
    SPACY_LANGUAGE: str = Field(default="en", description="spaCy language model")
    SPACY_MODEL: str = Field(default="en_core_web_lg", description="spaCy model name")

    # Extraction settings
    # Increased context window for better entity ranking and study site detection
    CONTEXT_WINDOW: int = Field(
        default=250,
        ge=20,
        le=500,
        description="Characters of context around entities",
    )
    MIN_CONFIDENCE: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold",
    )
    DEFAULT_COORDINATE_CONFIDENCE: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Default confidence for coordinate entities without scores",
    )
    DEFAULT_NER_CONFIDENCE: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description="Default confidence for NER entities without scores",
    )
    DEFAULT_SPATIAL_RELATION_CONFIDENCE: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Default confidence for spatial relation entities without scores",
    )
    DEFAULT_CONTEXTUAL_LOCATION_CONFIDENCE: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        description="Default confidence for contextual location entities without scores",
    )

    # Section priorities
    PRIORITY_SECTIONS: list[str] = Field(
        default=["methods", "study_area", "data", "materials", "study site"],
        description="Sections to prioritise for extraction",
    )

model_config = ModelConfig()
