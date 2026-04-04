"""Tests for location coreference resolution."""

from __future__ import annotations

import spacy

from app.nlp.coreference_resolver import LocationCoreferenceResolver
from app.nlp.domain_models import GeoEntity


def test_resolve_coreferences_with_missing_sentence_boundaries() -> None:
    """Coreference resolution should work when doc.sents is unavailable."""
    nlp = spacy.blank("en")  # no parser/sentencizer -> doc.sents raises E030
    text = "The study was conducted in Quito. The site is located at high elevation."
    doc = nlp(text)

    quito_start = text.index("Quito")
    entities = [
        GeoEntity(
            text="Quito",
            entity_type="GPE",
            context="The study was conducted in Quito.",
            section="methods",
            confidence=0.95,
            start_char=quito_start,
            end_char=quito_start + len("Quito"),
        ),
    ]

    resolver = LocationCoreferenceResolver()
    links = resolver.resolve_coreferences(doc, entities)

    assert len(links) == 1
    assert links[0].mention_text.lower() == "the site"
    assert links[0].antecedent_text == "Quito"


def test_expand_entities_with_coreferences_with_missing_sentence_boundaries() -> None:
    """Coreference expansion should add anaphoric entities without E030 failures."""
    nlp = spacy.blank("en")
    text = "The study was conducted in Quito. The site is located at high elevation."
    doc = nlp(text)

    quito_start = text.index("Quito")
    site_start = text.index("The site")

    entities = [
        GeoEntity(
            text="Quito",
            entity_type="GPE",
            context="The study was conducted in Quito.",
            section="methods",
            confidence=0.95,
            start_char=quito_start,
            end_char=quito_start + len("Quito"),
        ),
    ]

    resolver = LocationCoreferenceResolver()
    expanded = resolver.expand_entities_with_coreferences(doc, entities)

    assert len(expanded) == 2
    coref_entity = next(entity for entity in expanded if entity.text.lower() == "the site")
    assert coref_entity.start_char == site_start
    assert coref_entity.entity_type == "GPE"
