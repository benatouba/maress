from polyfactory.factories.pydantic_factory import ModelFactory
from polyfactory.fields import Use

from app.models import CollectionCreate, CreatorCreate, ItemCreate, RelationCreate, TagCreate, User, UserCreate
from tests.utils.utils import random_email


class ItemFactory(ModelFactory[ItemCreate]): ...


class CreatorFactory(ModelFactory[CreatorCreate]): ...


class UserFactory(ModelFactory[User]):
    email = Use(lambda: random_email())


class TagFactory(ModelFactory[TagCreate]): ...


class CollectionFactory(ModelFactory[CollectionCreate]): ...


class RelationFactory(ModelFactory[RelationCreate]): ...
