"""Tests for spaCy spatial relation matcher.

Tests the Matcher-based spatial relation extraction (replacing regex).
"""

import pytest
import spacy
from spacy.language import Language

from app.nlp.spacy_spatial_relation_matcher import SpatialRelationMatcher


@pytest.fixture
def nlp() -> Language:
    """Create a spaCy language model with spatial relation matcher."""
    nlp = spacy.load("en_core_web_sm")
    if "spatial_relation_matcher" not in nlp.pipe_names:
        nlp.add_pipe("spatial_relation_matcher", after="ner")
    return nlp


class TestDistanceDirectionPatterns:
    """Test patterns like '10 km north of Paris'."""

    def test_distance_direction_pattern(self, nlp: Language) -> None:
        """Test basic distance + direction pattern."""
        text = "The site is located 10 km north of Paris."
        doc = nlp(text)

        relations = [ent for ent in doc.ents if ent.label_ == "SPATIAL_RELATION"]
        assert len(relations) > 0
        assert "km" in relations[0].text.lower()
        assert "north" in relations[0].text.lower()

    def test_different_units(self, nlp: Language) -> None:
        """Test different distance units."""
        test_cases = [
            "5 miles north of London",
            "100 meters south of the station",
            "2 kilometers east of Berlin",
        ]

        for text in test_cases:
            doc = nlp(text)
            relations = [ent for ent in doc.ents if ent.label_ == "SPATIAL_RELATION"]
            assert len(relations) > 0, f"Failed to match: {text}"

    def test_all_directions(self, nlp: Language) -> None:
        """Test all cardinal and intercardinal directions."""
        directions = ["north", "south", "east", "west", "northeast", "northwest", "southeast", "southwest"]

        for direction in directions:
            text = f"Located 5 km {direction} of Berlin."
            doc = nlp(text)
            relations = [ent for ent in doc.ents if ent.label_ == "SPATIAL_RELATION"]
            assert len(relations) > 0, f"Failed to match direction: {direction}"


class TestSpatialPrepositionPatterns:
    """Test patterns like 'near Paris', 'adjacent to the river'."""

    def test_near_pattern(self, nlp: Language) -> None:
        """Test 'near [LOCATION]' pattern."""
        text = "The study site is near San Francisco."
        doc = nlp(text)

        relations = [ent for ent in doc.ents if ent.label_ == "SPATIAL_RELATION"]
        assert len(relations) > 0
        assert "near" in relations[0].text.lower()

    def test_adjacent_to_pattern(self, nlp: Language) -> None:
        """Test 'adjacent to [LOCATION]' pattern."""
        text = "The facility is adjacent to the Amazon River."
        doc = nlp(text)

        relations = [ent for ent in doc.ents if ent.label_ == "SPATIAL_RELATION"]
        assert len(relations) > 0

    def test_close_to_pattern(self, nlp: Language) -> None:
        """Test 'close to [LOCATION]' pattern."""
        text = "Sites were close to Berlin."
        doc = nlp(text)

        relations = [ent for ent in doc.ents if ent.label_ == "SPATIAL_RELATION"]
        assert len(relations) > 0

    def test_prepositions_with_article(self, nlp: Language) -> None:
        """Test patterns with articles: 'near the river'."""
        text = "Located near the Pacific Ocean."
        doc = nlp(text)

        relations = [ent for ent in doc.ents if ent.label_ == "SPATIAL_RELATION"]
        assert len(relations) > 0

    def test_within_pattern(self, nlp: Language) -> None:
        """Test 'within [LOCATION]' pattern."""
        text = "Samples collected within California."
        doc = nlp(text)

        relations = [ent for ent in doc.ents if ent.label_ == "SPATIAL_RELATION"]
        assert len(relations) > 0


class TestDirectionOfPatterns:
    """Test patterns like 'north of Paris'."""

    def test_direction_of_pattern(self, nlp: Language) -> None:
        """Test '[DIRECTION] of [LOCATION]' pattern."""
        text = "The site is north of Paris."
        doc = nlp(text)

        relations = [ent for ent in doc.ents if ent.label_ == "SPATIAL_RELATION"]
        assert len(relations) > 0
        assert "north" in relations[0].text.lower()
        assert "of" in relations[0].text.lower()

    def test_upstream_downstream(self, nlp: Language) -> None:
        """Test upstream/downstream patterns."""
        test_cases = [
            "upstream of the dam",
            "downstream of the reservoir",
        ]

        for text in test_cases:
            doc = nlp(text)
            relations = [ent for ent in doc.ents if ent.label_ == "SPATIAL_RELATION"]
            assert len(relations) > 0, f"Failed to match: {text}"

    def test_offshore_pattern(self, nlp: Language) -> None:
        """Test offshore pattern."""
        text = "Located offshore from California."
        doc = nlp(text)

        relations = [ent for ent in doc.ents if ent.label_ == "SPATIAL_RELATION"]
        assert len(relations) > 0


class TestLocationVerbPatterns:
    """Test patterns like 'located in California'."""

    def test_located_in_pattern(self, nlp: Language) -> None:
        """Test 'located in [LOCATION]' pattern."""
        text = "The study site is located in California."
        doc = nlp(text)

        relations = [ent for ent in doc.ents if ent.label_ == "SPATIAL_RELATION"]
        assert len(relations) > 0
        assert "located" in relations[0].text.lower()

    def test_situated_at_pattern(self, nlp: Language) -> None:
        """Test 'situated at [LOCATION]' pattern."""
        text = "The station is situated at the coast."
        doc = nlp(text)

        relations = [ent for ent in doc.ents if ent.label_ == "SPATIAL_RELATION"]
        assert len(relations) > 0

    def test_found_near_pattern(self, nlp: Language) -> None:
        """Test 'found near [LOCATION]' pattern."""
        text = "Specimens were found near Tokyo."
        doc = nlp(text)

        relations = [ent for ent in doc.ents if ent.label_ == "SPATIAL_RELATION"]
        assert len(relations) > 0

    def test_established_in_pattern(self, nlp: Language) -> None:
        """Test 'established in [LOCATION]' pattern."""
        text = "Sites established in the Amazon."
        doc = nlp(text)

        relations = [ent for ent in doc.ents if ent.label_ == "SPATIAL_RELATION"]
        assert len(relations) > 0

    def test_positioned_along_pattern(self, nlp: Language) -> None:
        """Test 'positioned along [LOCATION]' pattern."""
        text = "Sensors positioned along the river."
        doc = nlp(text)

        relations = [ent for ent in doc.ents if ent.label_ == "SPATIAL_RELATION"]
        assert len(relations) > 0


class TestLocationDescriptorPatterns:
    """Test patterns like 'Amazon River region'."""

    def test_region_descriptor(self, nlp: Language) -> None:
        """Test '[LOCATION] region' pattern."""
        text = "Study conducted in the Amazon region."
        doc = nlp(text)

        relations = [ent for ent in doc.ents if ent.label_ == "SPATIAL_RELATION"]
        assert len(relations) > 0

    def test_area_descriptor(self, nlp: Language) -> None:
        """Test '[LOCATION] area' pattern."""
        text = "Located in the Berlin area."
        doc = nlp(text)

        relations = [ent for ent in doc.ents if ent.label_ == "SPATIAL_RELATION"]
        assert len(relations) > 0

    def test_vicinity_descriptor(self, nlp: Language) -> None:
        """Test '[LOCATION] vicinity' pattern."""
        text = "Sites in the Paris vicinity."
        doc = nlp(text)

        relations = [ent for ent in doc.ents if ent.label_ == "SPATIAL_RELATION"]
        assert len(relations) > 0


class TestGreedyLongestMatching:
    """Test that greedy longest matching works correctly."""

    def test_longest_match_preferred(self, nlp: Language) -> None:
        """Test that longer matches are preferred over shorter ones."""
        text = "Located 10 km north of San Francisco."
        doc = nlp(text)

        relations = [ent for ent in doc.ents if ent.label_ == "SPATIAL_RELATION"]
        assert len(relations) > 0

        # Should match the full phrase including distance
        full_match = relations[0]
        assert "km" in full_match.text.lower()
        assert "north" in full_match.text.lower()

    def test_no_overlapping_matches(self, nlp: Language) -> None:
        """Test that no overlapping matches are created."""
        text = "Site A near Paris and Site B near London."
        doc = nlp(text)

        relations = [ent for ent in doc.ents if ent.label_ == "SPATIAL_RELATION"]

        # Check no overlaps
        for i, ent1 in enumerate(relations):
            for ent2 in relations[i+1:]:
                # Entities should not overlap
                assert not (ent1.start_char < ent2.end_char and ent1.end_char > ent2.start_char)

    def test_multiple_non_overlapping_relations(self, nlp: Language) -> None:
        """Test multiple spatial relations in the same text."""
        text = "Site A is 5 km north of Paris, while Site B is located in Berlin."
        doc = nlp(text)

        relations = [ent for ent in doc.ents if ent.label_ == "SPATIAL_RELATION"]
        assert len(relations) >= 2


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_no_spatial_relations(self, nlp: Language) -> None:
        """Test text without spatial relations."""
        text = "This is a simple sentence without any location information."
        doc = nlp(text)

        relations = [ent for ent in doc.ents if ent.label_ == "SPATIAL_RELATION"]
        assert len(relations) == 0

    def test_empty_text(self, nlp: Language) -> None:
        """Test empty text."""
        text = ""
        doc = nlp(text)

        relations = [ent for ent in doc.ents if ent.label_ == "SPATIAL_RELATION"]
        assert len(relations) == 0

    def test_location_without_relation(self, nlp: Language) -> None:
        """Test that plain location names are not matched as spatial relations."""
        text = "Paris is a city."
        doc = nlp(text)

        relations = [ent for ent in doc.ents if ent.label_ == "SPATIAL_RELATION"]
        # Should not match plain location names
        assert len(relations) == 0

    def test_mixed_entities(self, nlp: Language) -> None:
        """Test that spatial relations coexist with other entity types."""
        text = "The site near Paris was studied by Dr. Smith in 2020."
        doc = nlp(text)

        # Should have spatial relation
        relations = [ent for ent in doc.ents if ent.label_ == "SPATIAL_RELATION"]
        assert len(relations) > 0

        # Should also have other entities (PERSON, DATE)
        other_ents = [ent for ent in doc.ents if ent.label_ != "SPATIAL_RELATION"]
        assert len(other_ents) > 0


class TestRealWorldExamples:
    """Test with real-world scientific text examples."""

    def test_methods_section_example(self, nlp: Language) -> None:
        """Test typical methods section text."""
        text = """
        Study sites were established 10 km north of Berlin, Germany.
        Additional sampling locations were situated near the Amazon River basin.
        """
        doc = nlp(text)

        relations = [ent for ent in doc.ents if ent.label_ == "SPATIAL_RELATION"]
        assert len(relations) >= 2

    def test_abstract_example(self, nlp: Language) -> None:
        """Test typical abstract text."""
        text = """
        We conducted fieldwork in sites located in the Pacific Northwest,
        approximately 50 km east of Seattle.
        """
        doc = nlp(text)

        relations = [ent for ent in doc.ents if ent.label_ == "SPATIAL_RELATION"]
        assert len(relations) >= 2

    def test_complex_spatial_description(self, nlp: Language) -> None:
        """Test complex spatial descriptions."""
        text = """
        The research station is positioned along the coast,
        5 kilometers north of the city center and adjacent to
        the national park boundary.
        """
        doc = nlp(text)

        relations = [ent for ent in doc.ents if ent.label_ == "SPATIAL_RELATION"]
        assert len(relations) >= 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
