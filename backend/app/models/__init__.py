# pyright: reportUnknownVariableType=false, reportMissingImports=false
from sqlmodel import SQLModel

from .collections import Collection, CollectionCreate, CollectionPublic
from .creators import Creator, CreatorCreate, CreatorPublic
from .items import Item, ItemCreate, ItemPublic, ItemUpdate
from .links import ItemTagLink
from .relations import Relation, RelationCreate, RelationPublic
from .study_sites import StudySite, StudySiteCreate, StudySitePublic, StudySiteUpdate
from .tags import Tag, TagCreate, TagPublic
from .users import User, UserCreate, UserPublic, UserUpdate

# Export commonly used classes
__all__ = [
    "Collection",
    "CollectionCreate",
    "CollectionPublic",
    "Creator",
    "CreatorCreate",
    "CreatorPublic",
    "Item",
    "ItemCreate",
    "ItemPublic",
    "ItemTagLink",
    "ItemUpdate",
    "Relation",
    "RelationCreate",
    "RelationPublic",
    "SQLModel",  # SQLModel base
    "StudySite",
    "StudySiteCreate",
    "StudySitePublic",
    "StudySiteUpdate",
    "Tag",
    "TagCreate",
    "TagPublic",
    "User",  # ORM Models (table=True)
    "UserCreate",  # Pydantic schemas
    "UserPublic",
    "UserUpdate",
]
