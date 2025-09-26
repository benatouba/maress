from enum import Enum
from typing import Any, Literal

ZoteroItemKey = str
ZoteroItemVersion = int
ZoteroItemLibraryKey = Literal["type", "id", "name"]
ZoteroItemLinkKey = Literal["href", "type", "title", "length", "alternate"]
ZoteroItemLinks = dict[ZoteroItemLinkKey, str | int]
ZoteroItemLibrary = dict[ZoteroItemLibraryKey, str | int | ZoteroItemLinks]
ZoteroItemMetaCreatedByUser = dict[
    Literal["id", "username", "name"],
    str | int | ZoteroItemLinks,
]
ZoteroItemMeta = dict[
    Literal["createdByUser", "numChildren"],
    ZoteroItemMetaCreatedByUser | int,
]
ZoteroItemDataKey = Literal[
    "key",
    "version",
    "parentItem",
    "itemType",
    "linkMode",
    "title",
    "accessDate",
    "url",
    "note",
    "contentType",
    "charset",
    "filename",
    "md5",
    "mtime",
    "tags",
    "relations",
    "dateAdded",
    "dateModified",
]
ZoteroItemData = dict[ZoteroItemDataKey, str | int | list[str] | dict[str, Any]]

ZoteroItem = dict[
    Literal["key", "version", "library", "links", "meta", "data"],
    ZoteroItemLibrary | ZoteroItemLinks | ZoteroItemMeta | ZoteroItemData,
]
ZoteroItemList = list[ZoteroItem]


class CoordinateExtractionMethod(str, Enum):
    REGEX = "regex"
    TABLE_PARSING = "table_parsing"
    NER = "ner"
    GEOCODED = "geocoded"
    MANUAL = "manual"


class CoordinateSourceType(str, Enum):
    TEXT = "text"
    TABLE = "table"
    CAPTION = "caption"
    MANUAL = "manual"
    METADATA = "metadata"

class PaperSections(str, Enum):
    TITLE = "title"
    ABSTRACT = "abstract"
    INTRODUCTION = "introduction"
    METHODS = "methods"
    RESULTS = "results"
    DISCUSSION = "discussion"
    CONCLUSION = "conclusion"
    REFERENCES = "references"
    OTHER = "other"
