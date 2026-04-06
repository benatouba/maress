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
            {
                "label": "MARESS_COORDINATE",
                "pattern": r"\d+\s*[°]\s*\d+\s*[`´]\s*[NS]\s*,?\s*\d+\s*[°]\s*\d+\s*[`´]\s*[EW]",
                "id": "dm_min_corrupt_quote",
            },
            {
                "label": "MARESS_COORDINATE",
                "pattern": r"\d+\s*[7oOu]\s*\d+\s*[b`´]\s*\d+\s*[c]\s*[NS]\s*,?\s*\d+\s*[7oOu]\s*\d+\s*[b`´]\s*\d+\s*[c]\s*[EW]",
                "id": "dms_full_corrupt",
            },
            {
                "label": "MARESS_COORDINATE",
                "pattern": r"\d+\s*[oO]\s*\d+\s*[\'′`´]\s*[NS]",
                "id": "single_axis_dm_corrupt",
            },
            # === DASH-SEPARATED FORMATS (lat-lon joined by hyphen/dash) ===
            {
                "label": "MARESS_COORDINATE",
                "pattern": r"\d+\s*[°º]\s*\d+\s*[\'′]\s*\d+\.?\d*\s*[\"″]\s*[NS]\s*[-\u2013\u2014]\s*\d+\s*[°º]\s*\d+\s*[\'′]\s*\d+\.?\d*\s*[\"″]\s*[EW]",
                "id": "dms_dash",
            },
            {
                "label": "MARESS_COORDINATE",
                "pattern": r"\d+\s*[°º]\s*\d+\s*[\'′]\s*[NS]\s*[-\u2013\u2014]\s*\d+\s*[°º]\s*\d+\s*[\'′]\s*[EW]",
                "id": "dm_dash",
            },
            {
                "label": "MARESS_COORDINATE",
                "pattern": r"-?\d+\.\d+\s*°\s*[NS]\s*[-\u2013\u2014]\s*-?\d+\.\d+\s*°\s*[EW]",
                "id": "dd_symbol_dash",
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

    @staticmethod
    def get_extended_study_site_dependency_patterns(
        location_preps: list[str],
        site_nouns: list[str],
    ) -> dict[str, list[list[dict[str, Any]]]]:
        """Get extended dependency patterns for study site detection.

        These patterns capture domain-specific and passive constructions commonly
        found in earth and environmental science papers.
        """
        return {
            "FIELDWORK_AT_LOCATION": [
                [
                    {
                        "RIGHT_ID": "fieldwork",
                        "RIGHT_ATTRS": {
                            "POS": "NOUN",
                            "LEMMA": {
                                "IN": ["fieldwork", "field", "work", "campaign", "expedition"]
                            },
                        },
                    },
                    {
                        "LEFT_ID": "fieldwork",
                        "REL_OP": ">",
                        "RIGHT_ID": "verb",
                        "RIGHT_ATTRS": {
                            "POS": "VERB",
                            "LEMMA": {"IN": ["carry", "conduct", "perform", "undertake", "complete"]},
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
            "LOCATION_SELECTED_AS_SITE": [
                [
                    {
                        "RIGHT_ID": "location",
                        "RIGHT_ATTRS": {
                            "ENT_TYPE": {"IN": ["GPE", "LOC", "FAC"]},
                        },
                    },
                    {
                        "LEFT_ID": "location",
                        "REL_OP": "<",
                        "RIGHT_ID": "verb",
                        "RIGHT_ATTRS": {
                            "POS": "VERB",
                            "LEMMA": {"IN": ["select", "choose", "designate", "identify", "define"]},
                        },
                    },
                    {
                        "LEFT_ID": "verb",
                        "REL_OP": ">",
                        "RIGHT_ID": "prep_as",
                        "RIGHT_ATTRS": {
                            "DEP": "prep",
                            "LEMMA": "as",
                        },
                    },
                    {
                        "LEFT_ID": "prep_as",
                        "REL_OP": ">",
                        "RIGHT_ID": "site_noun",
                        "RIGHT_ATTRS": {
                            "DEP": "pobj",
                            "LEMMA": {"IN": site_nouns},
                        },
                    },
                ]
            ],
            "SAMPLES_FROM_LOCATION": [
                [
                    {
                        "RIGHT_ID": "sample_noun",
                        "RIGHT_ATTRS": {
                            "POS": "NOUN",
                            "LEMMA": {"IN": ["core", "sample", "specimen", "sediment", "ice", "peat"]},
                        },
                    },
                    {
                        "LEFT_ID": "sample_noun",
                        "REL_OP": ">",
                        "RIGHT_ID": "verb",
                        "RIGHT_ATTRS": {
                            "POS": "VERB",
                            "LEMMA": {"IN": ["extract", "retrieve", "obtain", "collect", "drill", "take"]},
                        },
                    },
                    {
                        "LEFT_ID": "verb",
                        "REL_OP": ">",
                        "RIGHT_ID": "prep",
                        "RIGHT_ATTRS": {
                            "DEP": "prep",
                            "LEMMA": {"IN": ["from", "in", "at"]},
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
            "INSTRUMENTS_AT_LOCATION": [
                [
                    {
                        "RIGHT_ID": "instrument",
                        "RIGHT_ATTRS": {
                            "POS": "NOUN",
                            "LEMMA": {
                                "IN": [
                                    "sensor",
                                    "instrument",
                                    "tower",
                                    "station",
                                    "buoy",
                                    "logger",
                                    "probe",
                                    "gauge",
                                ]
                            },
                        },
                    },
                    {
                        "LEFT_ID": "instrument",
                        "REL_OP": ">",
                        "RIGHT_ID": "verb",
                        "RIGHT_ATTRS": {
                            "POS": "VERB",
                            "LEMMA": {"IN": ["deploy", "install", "place", "position", "set", "mount"]},
                        },
                    },
                    {
                        "LEFT_ID": "verb",
                        "REL_OP": ">",
                        "RIGHT_ID": "prep",
                        "RIGHT_ATTRS": {
                            "DEP": "prep",
                            "LEMMA": {"IN": list(set(location_preps) | {"across", "throughout"})},
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
            "TRANSECTS_ACROSS_LOCATION": [
                [
                    {
                        "RIGHT_ID": "survey_noun",
                        "RIGHT_ATTRS": {
                            "POS": "NOUN",
                            "LEMMA": {"IN": ["transect", "plot", "quadrat", "grid", "profile", "survey"]},
                        },
                    },
                    {
                        "LEFT_ID": "survey_noun",
                        "REL_OP": ">",
                        "RIGHT_ID": "verb",
                        "RIGHT_ATTRS": {
                            "POS": "VERB",
                            "LEMMA": {"IN": ["establish", "set", "lay", "run", "conduct", "perform"]},
                        },
                    },
                    {
                        "LEFT_ID": "verb",
                        "REL_OP": ">",
                        "RIGHT_ID": "prep",
                        "RIGHT_ATTRS": {
                            "DEP": "prep",
                            "LEMMA": {"IN": ["across", "along", "through", "in", "within", "throughout"]},
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
            "NETWORK_IN_LOCATION": [
                [
                    {
                        "RIGHT_ID": "network_noun",
                        "RIGHT_ATTRS": {
                            "POS": "NOUN",
                            "LEMMA": {"IN": ["network", "array", "system", "infrastructure", "observatory"]},
                        },
                    },
                    {
                        "LEFT_ID": "network_noun",
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
            "DERIVED_FROM_LOCATION": [
                [
                    {
                        "RIGHT_ID": "verb",
                        "RIGHT_ATTRS": {
                            "POS": "VERB",
                            "LEMMA": {"IN": ["derive", "obtain", "acquire", "source", "extract"]},
                        },
                    },
                    {
                        "LEFT_ID": "verb",
                        "REL_OP": ">",
                        "RIGHT_ID": "prep_from",
                        "RIGHT_ATTRS": {
                            "DEP": "prep",
                            "LEMMA": "from",
                        },
                    },
                    {
                        "LEFT_ID": "prep_from",
                        "REL_OP": ">",
                        "RIGHT_ID": "imagery",
                        "RIGHT_ATTRS": {
                            "DEP": "pobj",
                            "LEMMA": {"IN": ["imagery", "image", "satellite", "scene", "data", "product"]},
                        },
                    },
                    {
                        "LEFT_ID": "imagery",
                        "REL_OP": ">",
                        "RIGHT_ID": "prep_cover",
                        "RIGHT_ATTRS": {
                            "DEP": "acl",
                        },
                    },
                    {
                        "LEFT_ID": "prep_cover",
                        "REL_OP": ">",
                        "RIGHT_ID": "location",
                        "RIGHT_ATTRS": {
                            "DEP": {"IN": ["dobj", "pobj"]},
                            "ENT_TYPE": {"IN": ["GPE", "LOC", "FAC"]},
                        },
                    },
                ]
            ],
            "EXPERIMENTS_AT_LOCATION": [
                [
                    {
                        "RIGHT_ID": "experiment",
                        "RIGHT_ATTRS": {
                            "POS": "NOUN",
                            "LEMMA": {"IN": ["experiment", "trial", "test", "manipulation", "treatment"]},
                        },
                    },
                    {
                        "LEFT_ID": "experiment",
                        "REL_OP": ">",
                        "RIGHT_ID": "verb",
                        "RIGHT_ATTRS": {
                            "POS": "VERB",
                            "LEMMA": {"IN": ["perform", "conduct", "carry", "run", "execute"]},
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
            "BASED_AT_LOCATION": [
                [
                    {
                        "RIGHT_ID": "based",
                        "RIGHT_ATTRS": {
                            "LEMMA": "base",
                            "TAG": {"IN": ["VBN", "VBD"]},
                        },
                    },
                    {
                        "LEFT_ID": "based",
                        "REL_OP": ">",
                        "RIGHT_ID": "prep",
                        "RIGHT_ATTRS": {
                            "DEP": "prep",
                            "LEMMA": {"IN": ["in", "at", "on"]},
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
            "ALONG_LOCATION_FEATURE": [
                [
                    {
                        "RIGHT_ID": "prep_along",
                        "RIGHT_ATTRS": {
                            "LEMMA": {"IN": ["along", "across", "through"]},
                        },
                    },
                    {
                        "LEFT_ID": "prep_along",
                        "REL_OP": ">",
                        "RIGHT_ID": "feature",
                        "RIGHT_ATTRS": {
                            "DEP": "pobj",
                            "LEMMA": {
                                "IN": [
                                    "coast",
                                    "coastline",
                                    "river",
                                    "border",
                                    "margin",
                                    "shore",
                                    "gradient",
                                    "transect",
                                ]
                            },
                        },
                    },
                    {
                        "LEFT_ID": "feature",
                        "REL_OP": ">",
                        "RIGHT_ID": "location",
                        "RIGHT_ATTRS": {
                            "DEP": {"IN": ["compound", "nmod", "poss"]},
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
                ,
                [
                    {"LIKE_NUM": True},
                    {"LOWER": {"IN": distance_units}},
                    {"LOWER": {"IN": all_directions}},
                    {"LOWER": {"IN": directional_preps}},
                    {"POS": "DET", "OP": "?"},
                    {"POS": {"IN": ["PROPN", "NOUN"]}, "OP": "+"},
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
                    {"LOWER": {"IN": proximity_preps}},
                    {"LOWER": "to", "OP": "?"},  # Optional "to"
                    {"POS": "DET", "OP": "?"},  # Optional determiner
                    {"POS": {"IN": ["PROPN", "NOUN"]}, "OP": "+"},
                ],
                [
                    {"LOWER": "adjacent"},
                    {"LOWER": "to", "OP": "?"},
                    {"POS": "DET", "OP": "?"},
                    {"POS": {"IN": ["PROPN", "NOUN"]}, "OP": "+"},
                ],
                [
                    {"LOWER": "adjacent"},
                    {"LOWER": "to", "OP": "?"},
                    {"POS": "DET", "OP": "?"},
                    {"LOWER": {"IN": ["national", "state", "regional"]}, "OP": "*"},
                    {"POS": "NOUN", "OP": "+"},
                ],
                [
                    {"LOWER": {"IN": containment_preps}},
                    {"POS": "DET", "OP": "?"},  # Optional determiner
                    {"ENT_TYPE": {"IN": ["LOC", "GPE", "FAC"]}, "OP": "+"},
                ],
                [
                    {"LOWER": {"IN": containment_preps}},
                    {"POS": "DET", "OP": "?"},  # Optional determiner
                    {"POS": {"IN": ["PROPN", "NOUN"]}, "OP": "+"},
                ],
            ],
            "DIRECTION_OF": [
                [
                    {"LOWER": {"IN": all_directions}},
                    {"LOWER": "of"},
                    {"POS": "DET", "OP": "?"},  # Optional determiner
                    {"ENT_TYPE": {"IN": ["LOC", "GPE", "FAC"]}, "OP": "+"},
                ]
                ,
                [
                    {"LOWER": {"IN": all_directions}},
                    {"LOWER": "of"},
                    {"POS": "DET", "OP": "?"},  # Optional determiner
                    {"POS": {"IN": ["PROPN", "NOUN"]}, "OP": "+"},
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
                    {"POS": {"IN": ["PROPN", "NOUN"]}},
                ],
                [
                    {"LOWER": {"IN": location_verbs}},
                    {"LOWER": {"IN": location_preps}},
                    {"POS": "DET", "OP": "?"},
                    {"POS": {"IN": ["PROPN", "NOUN"]}},
                    {"POS": {"IN": ["PROPN", "NOUN"]}, "OP": "?"},
                ],
                [
                    {"LOWER": {"IN": location_verbs}},
                    {"LOWER": "offshore"},
                    {"LOWER": {"IN": directional_preps}, "OP": "?"},
                    {"POS": "DET", "OP": "?"},
                    {"POS": {"IN": ["PROPN", "NOUN"]}, "OP": "+"},
                ],
            ],
            "LOCATION_DESCRIPTOR": [
                [
                    {"ENT_TYPE": {"IN": ["LOC", "GPE"]}},
                    {"LOWER": {"IN": location_descriptors}},
                ]
                ,
                [
                    {"POS": {"IN": ["PROPN", "NOUN"]}, "OP": "+"},
                    {"LOWER": {"IN": location_descriptors}},
                ]
            ],
        }
