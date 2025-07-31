from datetime import datetime

from polyfactory.factories.pydantic_factory import ModelFactory
from sqlmodel import Session

from app import crud
from app.models import Collection, Creator, Item, Relation, Tag, User
from app.tests.utils.user import create_random_user


class ItemFactory(ModelFactory[Item]): ...


class CreatorFactory(ModelFactory[Creator]): ...


class UserFactory(ModelFactory[User]): ...


class TagFactory(ModelFactory[Tag]): ...


class CollectionFactory(ModelFactory[Collection]): ...
class RelationFactory(ModelFactory[Relation]): ...

def create_random_user(db: Session) -> User:
    user_in = UserFactory.build()
    return crud.create_user(session=db, user_create=user_in)

def create_random_creator(db: Session) -> Creator:
    item = create_random_item(db)
    creator_in = CreatorFactory.build(item_id=item.id)
    return crud.create_creator(session=db, creator_in=creator_in)

def create_random_tag(db: Session) -> Tag:
    owner = create_random_user(db)
    assert owner.id is not None, "Owner ID must not be None"
    tag_in = TagFactory.build()
    return crud.create_tag(session=db, tag_in=tag_in, owner_id=owner.id)

def create_random_collection(db: Session) -> Collection:
    item = create_random_item(db)
    assert item.id is not None, "Item ID must not be None"
    owner = create_random_user(db)
    assert owner.id is not None, "Owner ID must not be None"
    collection_in = CollectionFactory.build(item_id=item.id)
    return crud.create_collection(session=db, collection_in=collection_in, item_id=item.id, owner_id=owner.id)


def create_random_item(db: Session) -> Item:
    user = create_random_user(db)
    owner_id = user.id
    assert owner_id is not None

    item_in = ItemFactory.build(OwnerId=owner_id, accessDate=datetime.now().isoformat())
    return crud.create_item(session=db, item_in=item_in, owner_id=owner_id)

def create_random_relation(db: Session) -> Relation:
    item = create_random_item(db)
    assert item.id is not None, "Item ID must not be None"

    relation_in = RelationFactory.build()
    return crud.create_relation(session=db, relation_in=relation_in, item_id=item.id)
