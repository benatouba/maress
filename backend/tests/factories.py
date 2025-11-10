from polyfactory.factories.pydantic_factory import ModelFactory
from polyfactory.fields import Use

from app.models.collections import CollectionCreate
from app.models.creators import CreatorCreate
from app.models.items import ItemCreate
from app.models.relations import RelationCreate
from app.models.study_sites import StudySiteCreate
from app.models.tags import TagCreate
from app.models.users import User
from tests.utils.utils import random_email


class ItemFactory(ModelFactory[ItemCreate]): ...


class CreatorFactory(ModelFactory[CreatorCreate]): ...


class UserFactory(ModelFactory[User]):
    email = Use(lambda: random_email())


class TagFactory(ModelFactory[TagCreate]): ...


class CollectionFactory(ModelFactory[CollectionCreate]): ...


class RelationFactory(ModelFactory[RelationCreate]): ...


class StudySiteFactory(ModelFactory[StudySiteCreate]): ...
