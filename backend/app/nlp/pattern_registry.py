"""Pattern registry for centralizing spaCy matcher patterns.

This module provides a centralized registry for all spaCy matcher patterns,
following NLP best practices:
- Single source of truth for patterns
- Version control for pattern evolution
- Easy pattern sharing across matchers
- Clear pattern documentation

Phase 1.5: Patterns are organized by matcher type and can be versioned,
documented, and maintained independently of matcher implementation.
"""

from typing import Any, ClassVar


class PatternRegistry:
    """Central registry for all spaCy matcher patterns.

    Patterns are organized by matcher type and version, allowing for:
    - Easy pattern updates without code changes
    - Pattern versioning and A/B testing
    - Clear documentation of pattern purpose
    - Reusable patterns across different matchers
    """

    # Version of the pattern registry
    VERSION: ClassVar[str] = "1.0.0"

    # === COORDINATE MATCHER PATTERNS ===

    @staticmethod
    def get_coordinate_token_patterns() -> dict[str, list[list[dict[str, Any]]]]:
        """Get token-based coordinate patterns for Matcher.

        Returns:
            Dictionary mapping pattern names to pattern lists
        """
        return {
            "LABELED_LATLON": [
                [
                    {"LOWER": {"IN": ["lat", "latitude"]}},
                    {"IS_PUNCT": True, "OP": "?"},  # Optional colon
                    {"IS_SPACE": True, "OP": "*"},  # Optional spaces
                    {"LIKE_NUM": True},  # Latitude value
                    {"IS_PUNCT": True},  # Comma
                    {"IS_SPACE": True, "OP": "*"},
                    {"LOWER": {"IN": ["lon", "long", "longitude"]}},
                    {"IS_PUNCT": True, "OP": "?"},
                    {"IS_SPACE": True, "OP": "*"},
                    {"LIKE_NUM": True},  # Longitude value
                ]
            ],
            "LABELED_LONLAT": [
                [
                    {"LOWER": {"IN": ["lon", "long", "longitude"]}},
                    {"IS_PUNCT": True, "OP": "?"},
                    {"IS_SPACE": True, "OP": "*"},
                    {"LIKE_NUM": True},
                    {"IS_PUNCT": True},
                    {"IS_SPACE": True, "OP": "*"},
                    {"LOWER": {"IN": ["lat", "latitude"]}},
                    {"IS_PUNCT": True, "OP": "?"},
                    {"IS_SPACE": True, "OP": "*"},
                    {"LIKE_NUM": True},
                ]
            ],
            "PREFIXED_COORDS": [
                [
                    {"LOWER": {"IN": ["coordinates", "coords", "coordinate"]}},
                    {"IS_PUNCT": True, "OP": "?"},
                    {"IS_SPACE": True, "OP": "*"},
                    {"LIKE_NUM": True},
                    {"IS_PUNCT": True},
                    {"IS_SPACE": True, "OP": "*"},
                    {"LIKE_NUM": True},
                ]
            ],
        }

    @staticmethod
    def get_coordinate_regex_patterns() -> list[dict[str, str]]:
        """Get regex-based coordinate patterns for EntityRuler.

        Returns:
            List of pattern dictionaries with label, pattern, and id
        """
        return [
            # === WELL-FORMED DMS/DM FORMATS ===
            {
                "label": "MARESS_COORDINATE",
                "pattern": r"\d+\s*[°º]\s*\d+\s*[\'′]\s*\d+\.?\d*\s*[\"″]\s*[NS]\s*,?\s*\d+\s*[°º]\s*\d+\s*[\'′]\s*\d+\.?\d*\s*[\"″]\s*[EW]",
                "id": "dms",
            },
            {
                "label": "MARESS_COORDINATE",
                "pattern": r"\d+\s*[°º]\s*\d+\s*[\'′]\s*[NS]\s*,?\s*\d+\s*[°º]\s*\d+\s*[\'′]\s*[EW]",
                "id": "dm",
            },
            {
                "label": "MARESS_COORDINATE",
                "pattern": r"-?\d+\.\d+\s*°\s*[NS]?\s*,?\s*-?\d+\.\d+\s*°\s*[EW]?",
                "id": "dd_symbol",
            },
            # === MALFORMED PATTERNS - PDF Extraction Artifacts ===
            {
                "label": "MARESS_COORDINATE",
                "pattern": r"\d+\s+7\s+\d+\s*[\'′b]\s*[NS]\s*,?\s*\d+\s+7\s+\d+\s*[\'′b]\s*[EW]",
                "id": "dm_deg7",
            },
            {
                "label": "MARESS_COORDINATE",
                "pattern": r"\d+\s*[oO]\s*\d+\s*[\'′]\s*[NS]\s*,?\s*\d+\s*[oO]\s*\d+\s*[\'′]\s*[EW]",
                "id": "dm_dego",
            },
            {
                "label": "MARESS_COORDINATE",
                "pattern": r"\d+\s*[°7oO]\s*\d+\s*[b]\s*[NS]\s*,?\s*\d+\s*[°7oO]\s*\d+\s*[b]\s*[EW]",
                "id": "dm_minb",
            },
            {
                "label": "MARESS_COORDINATE",
                "pattern": r"\d+\s*[°7oO]\s*\d+\s*[\'′b]\.?\d*\s*[NS]\s*,?\s*\d+\s*[°7oO]\s*\d+\s*[\'′b]\.?\d*\s*[EW]",
                "id": "dm_compact",
            },
            # === SIMPLE FORMATS ===
            {
                "label": "MARESS_COORDINATE",
                "pattern": r"\(\s*-?\d+\.\d{2,}\s*,\s*-?\d+\.\d{2,}\s*\)",
                "id": "parentheses",
            },
            {
                "label": "MARESS_COORDINATE",
                "pattern": r"\[\s*-?\d+\.\d{2,}\s*,\s*-?\d+\.\d{2,}\s*\]",
                "id": "brackets",
            },
            {
                "label": "MARESS_COORDINATE",
                "pattern": r"\d+\.\d+\s+[NS]\s*,?\s*\d+\.\d+\s+[EW]",
                "id": "dd_direction",
            },
            {
                "label": "MARESS_COORDINATE",
                "pattern": r"[+-]?\d+\.\d{2,}\s*,\s*[+-]?\d+\.\d{2,}",
                "id": "decimal_pair",
            },
            # === ADDITIONAL MALFORMED PATTERNS ===
            # Degree as "u", minute as "9": 13 u 13 9 09 S, 74 u 57 9 45 W
            {
                "label": "MARESS_COORDINATE",
                "pattern": r"\d+\s*u\s*\d+\s*9\s*\d+\.?\d*\s*[NS]\s*,?\s*\d+\s*u\s*\d+\s*9\s*\d+\.?\d*\s*[EW]",
                "id": "dms_u_9",
            },
            # Degree as "u" (without "9" minute marker): 13 u 13' S
            {
                "label": "MARESS_COORDINATE",
                "pattern": r"\d+\s*u\s*\d+\s*[\'′]\s*[NS]\s*,?\s*\d+\s*u\s*\d+\s*[\'′]\s*[EW]",
                "id": "dm_u",
            },
        ]

    # === STUDY SITE DEPENDENCY PATTERNS ===

    @staticmethod
    def get_study_site_dependency_patterns(
        study_verbs: list[str],
        location_preps: list[str],
        site_nouns: list[str],
    ) -> dict[str, list[list[dict[str, Any]]]]:
        """Get dependency patterns for study site detection.

        Args:
            study_verbs: List of study-related verbs
            location_preps: List of location prepositions
            site_nouns: List of site-related nouns

        Returns:
            Dictionary mapping pattern names to dependency pattern lists
        """
        return {
            "VERB_PREP_LOCATION": [
                [
                    {
                        "RIGHT_ID": "verb",
                        "RIGHT_ATTRS": {
                            "POS": "VERB",
                            "LEMMA": {"IN": study_verbs},
                        },
                    },
                    {
                        "LEFT_ID": "verb",
                        "REL_OP": ">",
                        "RIGHT_ID": "prep",
                        "RIGHT_ATTRS": {
                            "DEP": "prep",
                            "LEMMA": {"IN": location_preps},
                        },
                    },
                    {
                        "LEFT_ID": "prep",
                        "REL_OP": ">",
                        "RIGHT_ID": "location",
                        "RIGHT_ATTRS": {
                            "DEP": "pobj",
                            "ENT_TYPE": {"IN": ["GPE", "LOC", "FAC"]},
                        },
                    },
                ]
            ],
            "SITE_NOUN_PREP_LOCATION": [
                [
                    {
                        "RIGHT_ID": "site_noun",
                        "RIGHT_ATTRS": {
                            "POS": "NOUN",
                            "LEMMA": {"IN": site_nouns},
                        },
                    },
                    {
                        "LEFT_ID": "site_noun",
                        "REL_OP": ">",
                        "RIGHT_ID": "prep",
                        "RIGHT_ATTRS": {
                            "DEP": "prep",
                            "LEMMA": {"IN": location_preps},
                        },
                    },
                    {
                        "LEFT_ID": "prep",
                        "REL_OP": ">",
                        "RIGHT_ID": "location",
                        "RIGHT_ATTRS": {
                            "DEP": "pobj",
                            "ENT_TYPE": {"IN": ["GPE", "LOC", "FAC"]},
                        },
                    },
                ]
            ],
            "LOCATION_SITE_NOUN": [
                [
                    {
                        "RIGHT_ID": "site_noun",
                        "RIGHT_ATTRS": {
                            "POS": "NOUN",
                            "LEMMA": {"IN": site_nouns},
                        },
                    },
                    {
                        "LEFT_ID": "site_noun",
                        "REL_OP": ">",
                        "RIGHT_ID": "location",
                        "RIGHT_ATTRS": {
                            "DEP": {"IN": ["compound", "nmod", "amod"]},
                            "ENT_TYPE": {"IN": ["GPE", "LOC", "FAC"]},
                        },
                    },
                ]
            ],
            "PARTICIPLE_PREP_LOCATION": [
                [
                    {
                        "RIGHT_ID": "participle",
                        "RIGHT_ATTRS": {
                            "TAG": {"IN": ["VBN", "VBD"]},
                            "LEMMA": {"IN": ["locate", "situate", "position", "establish"]},
                        },
                    },
                    {
                        "LEFT_ID": "participle",
                        "REL_OP": ">",
                        "RIGHT_ID": "prep",
                        "RIGHT_ATTRS": {
                            "DEP": "prep",
                            "LEMMA": {"IN": location_preps},
                        },
                    },
                    {
                        "LEFT_ID": "prep",
                        "REL_OP": ">",
                        "RIGHT_ID": "location",
                        "RIGHT_ATTRS": {
                            "DEP": "pobj",
                            "ENT_TYPE": {"IN": ["GPE", "LOC", "FAC"]},
                        },
                    },
                ]
            ],
            "SITE_NOUN_PASSIVE_LOCATION": [
                [
                    {
                        "RIGHT_ID": "site_noun",
                        "RIGHT_ATTRS": {
                            "POS": "NOUN",
                            "LEMMA": {"IN": site_nouns},
                        },
                    },
                    {
                        "LEFT_ID": "site_noun",
                        "REL_OP": ">",
                        "RIGHT_ID": "verb",
                        "RIGHT_ATTRS": {
                            "POS": "VERB",
                            "DEP": {"IN": ["relcl", "acl"]},
                            "LEMMA": {"IN": study_verbs},
                        },
                    },
                    {
                        "LEFT_ID": "verb",
                        "REL_OP": ">",
                        "RIGHT_ID": "prep",
                        "RIGHT_ATTRS": {
                            "DEP": "prep",
                            "LEMMA": {"IN": location_preps},
                        },
                    },
                    {
                        "LEFT_ID": "prep",
                        "REL_OP": ">",
                        "RIGHT_ID": "location",
                        "RIGHT_ATTRS": {
                            "DEP": "pobj",
                            "ENT_TYPE": {"IN": ["GPE", "LOC", "FAC"]},
                        },
                    },
                ]
            ],
            "FOCUS_ON_LOCATION": [
                [
                    {
                        "RIGHT_ID": "verb",
                        "RIGHT_ATTRS": {
                            "POS": "VERB",
                            "LEMMA": {"IN": ["focus", "concentrate", "center", "centre"]},
                        },
                    },
                    {
                        "LEFT_ID": "verb",
                        "REL_OP": ">",
                        "RIGHT_ID": "prep",
                        "RIGHT_ATTRS": {
                            "DEP": "prep",
                            "LEMMA": "on",
                        },
                    },
                    {
                        "LEFT_ID": "prep",
                        "REL_OP": ">",
                        "RIGHT_ID": "location",
                        "RIGHT_ATTRS": {
                            "DEP": "pobj",
                            "ENT_TYPE": {"IN": ["GPE", "LOC", "FAC"]},
                        },
                    },
                ]
            ],
            "DATA_COLLECTED_LOCATION": [
                [
                    {
                        "RIGHT_ID": "data_noun",
                        "RIGHT_ATTRS": {
                            "POS": "NOUN",
                            "LEMMA": {"IN": ["data", "datum", "measurement", "observation", "sample"]},
                        },
                    },
                    {
                        "LEFT_ID": "data_noun",
                        "REL_OP": ">",
                        "RIGHT_ID": "verb",
                        "RIGHT_ATTRS": {
                            "POS": "VERB",
                            "DEP": {"IN": ["relcl", "acl", "ROOT"]},
                            "LEMMA": {"IN": ["collect", "gather", "obtain", "take", "record"]},
                        },
                    },
                    {
                        "LEFT_ID": "verb",
                        "REL_OP": ">",
                        "RIGHT_ID": "prep",
                        "RIGHT_ATTRS": {
                            "DEP": "prep",
                            "LEMMA": {"IN": location_preps},
                        },
                    },
                    {
                        "LEFT_ID": "prep",
                        "REL_OP": ">",
                        "RIGHT_ID": "location",
                        "RIGHT_ATTRS": {
                            "DEP": "pobj",
                            "ENT_TYPE": {"IN": ["GPE", "LOC", "FAC"]},
                        },
                    },
                ]
            ],
            "DOMAIN_COVERAGE_LOCATION": [
                [
                    {
                        "RIGHT_ID": "domain_noun",
                        "RIGHT_ATTRS": {
                            "POS": "NOUN",
                            "LEMMA": {"IN": ["domain", "region", "area", "model"]},
                        },
                    },
                    {
                        "LEFT_ID": "domain_noun",
                        "REL_OP": ">",
                        "RIGHT_ID": "verb",
                        "RIGHT_ATTRS": {
                            "POS": "VERB",
                            "LEMMA": {"IN": ["cover", "span", "extend", "encompass", "include"]},
                        },
                    },
                    {
                        "LEFT_ID": "verb",
                        "REL_OP": ">",
                        "RIGHT_ID": "location",
                        "RIGHT_ATTRS": {
                            "DEP": {"IN": ["dobj", "pobj"]},
                            "ENT_TYPE": {"IN": ["GPE", "LOC", "FAC"]},
                        },
                    },
                ]
            ],
        }

    # === SPATIAL RELATION PATTERNS ===

    @staticmethod
    def get_spatial_relation_token_patterns(
        distance_units: list[str],
        all_directions: list[str],
        directional_preps: list[str],
        proximity_preps: list[str],
        containment_preps: list[str],
        location_verbs: list[str],
        location_preps: list[str],
        location_descriptors: list[str],
    ) -> dict[str, list[list[dict[str, Any]]]]:
        """Get token patterns for spatial relation detection.

        Args:
            distance_units: List of distance units (km, miles, etc.)
            all_directions: Combined list of cardinal and hydrological directions
            directional_preps: Directional prepositions (of, from)
            proximity_preps: Proximity prepositions (near, close, etc.)
            containment_preps: Containment prepositions (within, inside, etc.)
            location_verbs: Location-specific verbs
            location_preps: General location prepositions
            location_descriptors: Location descriptor nouns

        Returns:
            Dictionary mapping pattern names to token pattern lists
        """
        return {
            "DISTANCE_DIRECTION": [
                [
                    {"LIKE_NUM": True},  # Distance number
                    {"LOWER": {"IN": distance_units}},  # Unit
                    {"LOWER": {"IN": all_directions}},  # Direction
                    {"LOWER": {"IN": directional_preps}},
                    {"ENT_TYPE": {"IN": ["LOC", "GPE", "FAC"]}, "OP": "+"},  # Location entity
                ]
            ],
            "SPATIAL_PREPOSITION": [
                [
                    {"LOWER": {"IN": proximity_preps}},
                    {"LOWER": "to", "OP": "?"},  # Optional "to"
                    {"POS": "DET", "OP": "?"},  # Optional determiner
                    {"ENT_TYPE": {"IN": ["LOC", "GPE", "FAC"]}, "OP": "+"},  # Location
                ],
                [
                    {"LOWER": {"IN": containment_preps}},
                    {"POS": "DET", "OP": "?"},  # Optional determiner
                    {"ENT_TYPE": {"IN": ["LOC", "GPE", "FAC"]}, "OP": "+"},
                ],
            ],
            "DIRECTION_OF": [
                [
                    {"LOWER": {"IN": all_directions}},
                    {"LOWER": "of"},
                    {"POS": "DET", "OP": "?"},  # Optional determiner
                    {"ENT_TYPE": {"IN": ["LOC", "GPE", "FAC"]}, "OP": "+"},
                ]
            ],
            "LOCATION_VERB": [
                [
                    {"LOWER": {"IN": location_verbs}},
                    {"LOWER": {"IN": location_preps}},
                    {"POS": "DET", "OP": "?"},  # Optional determiner
                    {"ENT_TYPE": {"IN": ["LOC", "GPE", "FAC"]}, "OP": "+"},
                ],
                [
                    {"LOWER": {"IN": location_verbs}},
                    {"LOWER": {"IN": location_preps}},
                    {"POS": "DET", "OP": "?"},  # Optional determiner
                    {"POS": {"IN": ["PROPN", "NOUN"]}, "OP": "+"},  # Location name (proper noun or noun)
                ],
            ],
            "LOCATION_DESCRIPTOR": [
                [
                    {"ENT_TYPE": {"IN": ["LOC", "GPE"]}},
                    {"LOWER": {"IN": location_descriptors}},
                ]
            ],
        }
