from polyfactory.factories.pydantic_factory import ModelFactory
from polyfactory.fields import Use

from app.models import CollectionCreate
from app.models import CreatorCreate
from app.models import ItemCreate
from app.models import RelationCreate
from app.models import StudySiteCreate
from app.models import TagCreate
from app.models import User
from tests.utils.utils import random_email


class ItemFactory(ModelFactory[ItemCreate]): ...


class CreatorFactory(ModelFactory[CreatorCreate]): ...


class UserFactory(ModelFactory[User]):
    email = Use(lambda: random_email())


class TagFactory(ModelFactory[TagCreate]): ...


class CollectionFactory(ModelFactory[CollectionCreate]): ...


class RelationFactory(ModelFactory[RelationCreate]): ...


class StudySiteFactory(ModelFactory[StudySiteCreate]): ...
