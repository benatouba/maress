from polyfactory.factories.pydantic_factory import ModelFactory
from polyfactory.fields import Use

from app.models import CollectionCreate, CreatorCreate, ItemCreate, RelationCreate, TagCreate, UserCreate
from app.tests.utils.utils import random_email


class ItemFactory(ModelFactory[ItemCreate]): ...


class CreatorFactory(ModelFactory[CreatorCreate]): ...


class UserFactory(ModelFactory[UserCreate]):
    email = Use(lambda: random_email())


class TagFactory(ModelFactory[TagCreate]): ...


class CollectionFactory(ModelFactory[CollectionCreate]): ...


class RelationFactory(ModelFactory[RelationCreate]): ...
