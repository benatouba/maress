from datetime import datetime

from sqlmodel import Session

from app import crud
from app.models import Collection
from app.models import Creator
from app.models import Item
from app.models import Relation
from app.models import Tag
from tests.factories import (
    CollectionFactory,
    CreatorFactory,
    ItemFactory,
    RelationFactory,
    TagFactory,
)
from tests.utils.user import create_test_user


def create_random_creator(db_session: Session) -> Creator:
    item = create_random_item(db_session)
    assert item.id is not None, "Item ID must not be None"
    creator_in = CreatorFactory.build(item_id=item.id)
    return crud.create_creator(session=db_session, creator_in=creator_in, item_id=item.id)


def create_random_tag(db_session: Session) -> Tag:
    owner = create_test_user(db_session)
    assert owner.id is not None, "Owner ID must not be None"
    tag_in = TagFactory.build()
    return crud.create_tag(session=db_session, tag_in=tag_in, owner_id=owner.id)


def create_random_collection(db_session: Session) -> Collection:
    item = create_random_item(db_session)
    assert item.id is not None, "Item ID must not be None"
    owner = create_test_user(db_session)
    assert owner.id is not None, "Owner ID must not be None"
    collection_in = CollectionFactory.build(item_id=item.id)
    return crud.create_collection(
        session=db_session,
        collection_in=collection_in,
        item_id=item.id,
        owner_id=owner.id,
    )


def create_random_item(db_session: Session) -> Item:
    user = create_test_user(db_session)
    owner_id = user.id
    assert owner_id is not None

    item_in = ItemFactory.build(OwnerId=owner_id, accessDate=datetime.now().isoformat())
    return crud.create_item(session=db_session, item_in=item_in, owner_id=owner_id)


def create_random_relation(db_session: Session) -> Relation:
    item = create_random_item(db_session)
    assert item.id is not None, "Item ID must not be None"

    relation_in = RelationFactory.build()
    return crud.create_relation(session=db_session, relation_in=relation_in, item_id=item.id)
