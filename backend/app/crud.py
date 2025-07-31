import logging
import uuid
from typing import Any

from sqlmodel import Sequence, Session, select

from app.core.security import get_password_hash, verify_password
from app.models import (
    Collection,
    CollectionCreate,
    Creator,
    CreatorCreate,
    Item,
    ItemCreate,
    Relation,
    RelationCreate,
    Tag,
    TagCreate,
    User,
    UserCreate,
    UserUpdate,
)

logger = logging.getLogger(__name__)


def create_user(*, session: Session, user_create: UserCreate) -> User:
    db_obj = User.model_validate(
        user_create, update={"hashed_password": get_password_hash(user_create.password)}
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> Any:
    user_data = user_in.model_dump(exclude_unset=True)
    extra_data = {}
    if "password" in user_data:
        password = user_data["password"]
        hashed_password = get_password_hash(password)
        extra_data["hashed_password"] = hashed_password
    db_user.sqlmodel_update(user_data, update=extra_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def get_user_by_email(*, session: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    session_user = session.exec(statement).first()
    return session_user


def authenticate(*, session: Session, email: str, password: str) -> User | None:
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        return None
    if not verify_password(password, db_user.hashed_password):
        return None
    return db_user


def create_item(*, session: Session, item_in: ItemCreate, owner_id: uuid.UUID) -> Item:
    db_item = Item.model_validate(item_in, update={"owner_id": owner_id})
    session.add(db_item)
    session.commit()
    session.refresh(db_item)
    return db_item


def get_all_items(
    *, session: Session, skip: int = 0, limit: int = 100
) -> Sequence[Item]:
    statement = select(Item).offset(skip).limit(limit)
    return session.exec(statement).all()


def get_tag(session: Session, tag_id: int) -> Tag | None:
    """Get a tag by ID."""
    return session.get(Tag, tag_id)


def get_tags(
    session: Session, owner_id: uuid.UUID | None = None, skip: int = 0, limit: int = 100
) -> tuple[list[Tag], int]:
    """Retrieve tags with optional filtering by owner_id.

    Returns a tuple (tags list, total count).
    """
    query = select(Tag)
    count_query = select(func.count()).select_from(Tag)

    if owner_id is not None:
        query = query.where(Tag.owner_id == owner_id)
        count_query = count_query.where(Tag.owner_id == owner_id)

    total = session.exec(count_query).one()
    tags = session.exec(query.offset(skip).limit(limit)).all()
    return tags, total


def create_tag(session: Session, tag_in: TagCreate, owner_id: uuid.UUID) -> Tag:
    """Create a new Tag with owner assigned."""
    tag = Tag.model_validate(tag_in, update={"owner_id": owner_id})
    session.add(tag)
    try:
        session.commit()
        session.refresh(tag)
    except Exception as e:
        logger.error(f"Failed to create tag: {e}")
        session.rollback()
        raise
    return tag


def update_tag(
    session: Session, tag_id: int, tag_in: TagCreate, owner_id: uuid.UUID
) -> Tag | None:
    """Update a tag by ID if owner matches; returns updated tag or None if not
    found."""
    tag = get_tag(session, tag_id)
    if not tag:
        return None
    if tag.owner_id != owner_id:
        raise PermissionError("Not enough permissions to update this tag.")

    # Copy fields from tag_in
    updated_data = tag_in.model_dump(exclude_unset=True)
    for key, value in updated_data.items():
        setattr(tag, key, value)

    try:
        session.add(tag)
        session.commit()
        session.refresh(tag)
    except Exception as e:
        logger.error(f"Failed to update tag: {e}")
        session.rollback()
        raise
    return tag


def delete_tag(session: Session, tag_id: int, owner_id: uuid.UUID) -> bool:
    """Delete a tag by ID if owner matches; returns True if deleted, False
    otherwise."""
    tag = get_tag(session, tag_id)
    if not tag:
        return False
    if tag.owner_id != owner_id:
        raise PermissionError("Not enough permissions to delete this tag.")

    try:
        session.delete(tag)
        session.commit()
    except Exception as e:
        logger.error(f"Failed to delete tag: {e}")
        session.rollback()
        raise
    return True


def get_creator(session: Session, creator_id: int) -> Creator | None:
    """Get a creator by ID."""
    return session.get(Creator, creator_id)


def get_creators(
    session: Session,
    item_id: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[Creator], int]:
    """Retrieve creators, optionally filtered by item_id.

    Returns a tuple (creators list, total count).
    """
    query = select(Creator)
    count_query = select(func.count()).select_from(Creator)

    if item_id is not None:
        query = query.where(Creator.item_id == item_id)
        count_query = count_query.where(Creator.item_id == item_id)

    total = session.exec(count_query).one()
    creators = session.exec(query.offset(skip).limit(limit)).all()
    return creators, total


def create_creator(
    session: Session, creator_in: CreatorCreate, item_id: str
) -> Creator:
    """Create a new Creator with linked item_id."""
    creator = Creator.model_validate(creator_in, update={"item_id": item_id})
    session.add(creator)
    session.commit()
    session.refresh(creator)
    return creator


def update_creator(
    session: Session,
    creator_id: int,
    creator_in: CreatorCreate,
) -> Creator | None:
    """Update a Creator by ID; returns updated creator or None if not found."""
    creator = get_creator(session, creator_id)
    if not creator:
        return None

    updated_data = creator_in.model_dump(exclude_unset=True)
    for key, value in updated_data.items():
        setattr(creator, key, value)

    session.add(creator)
    session.commit()
    session.refresh(creator)
    return creator


def delete_creator(session: Session, creator_id: int) -> bool:
    """Delete a Creator by ID; returns True if deleted, False otherwise."""
    creator = get_creator(session, creator_id)
    if not creator:
        return False

    session.delete(creator)
    session.commit()
    return True


def get_relation(session: Session, relation_id: int) -> Relation | None:
    """Get a Relation by ID."""
    return session.get(Relation, relation_id)


def get_relations(
    session: Session,
    item_id: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[Relation], int]:
    """Retrieve relations, optionally filtered by item_id.

    Returns a tuple (list of relations, total count).
    """
    query = select(Relation)
    count_query = select(func.count()).select_from(Relation)

    if item_id is not None:
        query = query.where(Relation.item_id == item_id)
        count_query = count_query.where(Relation.item_id == item_id)

    total = session.exec(count_query).one()
    relations = session.exec(query.offset(skip).limit(limit)).all()
    return relations, total


def create_relation(
    session: Session, relation_in: RelationCreate, item_id: uuid.UUID
) -> Relation:
    """Create a new Relation associated with an item."""
    relation = Relation.model_validate(relation_in, update={"item_id": item_id})
    session.add(relation)
    session.commit()
    session.refresh(relation)
    return relation


def update_relation(
    session: Session,
    relation_id: int,
    relation_in: RelationCreate,
) -> Relation | None:
    """Update a Relation by ID; returns updated relation or None if not
    found."""
    relation = get_relation(session, relation_id)
    if not relation:
        return None

    updated_data = relation_in.model_dump(exclude_unset=True)
    for key, value in updated_data.items():
        setattr(relation, key, value)

    session.add(relation)
    session.commit()
    session.refresh(relation)
    return relation


def delete_relation(session: Session, relation_id: int) -> bool:
    """Delete a Relation by ID; returns True if deleted, False otherwise."""
    relation = get_relation(session, relation_id)
    if not relation:
        return False

    session.delete(relation)
    session.commit()
    return True


def create_collection(
    session: Session, collection_in: CollectionCreate, item_id: uuid.UUID, owner_id: uuid.UUID
) -> Collection:
    """Create a new Collection associated with an item."""
    collection = Collection.model_validate(collection_in, update={"item_id": item_id, "owner_id": owner_id})
    session.add(collection)
    session.commit()
    session.refresh(collection)
    return collection
