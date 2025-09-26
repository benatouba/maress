from datetime import datetime

from sqlmodel import Session

from app import crud
from app.models import Collection, Creator, Item, Relation, Tag
from tests.factories import (
    CollectionFactory,
    CreatorFactory,
    ItemFactory,
    RelationFactory,
    TagFactory,
)
from tests.utils.user import create_random_user


def create_random_creator(db: Session) -> Creator:
    item = create_random_item(db)
    assert item.id is not None, "Item ID must not be None"
    creator_in = CreatorFactory.build(item_id=item.id)
    return crud.create_creator(session=db, creator_in=creator_in, item_id=item.id)


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
    return crud.create_collection(
        session=db, collection_in=collection_in, item_id=item.id, owner_id=owner.id
    )


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
