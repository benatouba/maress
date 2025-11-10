from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from pydantic_extra_types.coordinate import Latitude, Longitude
from sqlalchemy.orm import selectinload
from sqlmodel import Session, func, select

from app.core.security import get_password_hash, verify_password
from app.models import (
    Collection,
    CollectionCreate,
    Creator,
    CreatorCreate,
    Item,
    ItemCreate,
    Location,
    Relation,
    RelationCreate,
    StudySite,
    StudySiteCreate,
    StudySiteUpdate,
    Tag,
    TagCreate,
    User,
    UserCreate,
    UserUpdate,
)

if TYPE_CHECKING:
    from sqlmodel import Sequence, Session, SQLModel

logger = logging.getLogger(__name__)


def create_user(*, session: Session, user_create: UserCreate) -> User:
    db_obj = User.model_validate(
        user_create,
        update={"hashed_password": get_password_hash(user_create.password)},
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> User:
    user_data = user_in.model_dump(exclude_unset=True)
    extra_data: dict[str, str] = {}
    if user_in.password:
        hashed_password = get_password_hash(user_in.password)
        extra_data["hashed_password"] = hashed_password
    db_user.sqlmodel_update(user_data, update=extra_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def get_user_by_email(*, session: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    return session.exec(statement).first()


def get_study_site_by_id(*, session: Session, id: uuid.UUID) -> StudySite | None:
    statement = select(StudySite).where(StudySite.id == id)
    return session.exec(statement).first()


def authenticate(*, session: Session, email: str, password: str) -> User | None:
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        return None
    if not verify_password(password, db_user.hashed_password):
        return None
    return db_user


def create_item(*, session: Session, item_in: ItemCreate, owner_id: uuid.UUID) -> SQLModel:
    db_item: SQLModel = Item.model_validate(item_in, update={"owner_id": owner_id})
    session.add(db_item)
    session.commit()
    session.refresh(db_item)
    return db_item


def get_all_items(
    *,
    session: Session,
    skip: int = 0,
    limit: int = 500,
) -> Sequence[Item]:
    statement = select(Item).offset(skip).limit(limit)
    return session.exec(statement).all()


def get_tag(session: Session, tag_id: int) -> Tag | None:
    """Get a tag by ID."""
    query = select(Tag).options(selectinload(Tag.items)).where(Tag.id == tag_id)
    return session.exec(query).first()


def get_tags(
    session: Session,
    owner_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[Tag], int]:
    """Retrieve tags with optional filtering by owner_id.

    Returns a tuple (tags list, total count).
    """
    query = select(Tag).options(selectinload(Tag.items))
    count_query = select(func.count()).select_from(Tag)

    if owner_id is not None:
        query = query.where(Tag.owner_id == owner_id)
        count_query = count_query.where(Tag.owner_id == owner_id)

    total = session.exec(count_query).one()
    tags = session.exec(query.offset(skip).limit(limit)).all()
    return list(tags), total


def create_tag(session: Session, tag_in: TagCreate, owner_id: uuid.UUID) -> Tag:
    """Create a new Tag with owner assigned."""
    tag = Tag.model_validate(tag_in, update={"owner_id": owner_id})
    session.add(tag)

    if tag_in.item_ids:
        session.flush()  # Get the tag ID before adding associations
        for item_id in tag_in.item_ids:
            item = session.get(Item, item_id)
            if item:  # Only associate if item exists
                tag.items.append(item)

    try:
        session.commit()
        session.refresh(tag)
    except Exception:
        logger.exception("Failed to create tag")
        session.rollback()
        raise
    return tag


def update_tag(
    session: Session,
    tag_id: int,
    tag_in: TagCreate,
    owner_id: uuid.UUID,
) -> Tag | None:
    """Update a tag by ID if owner matches.

    Returns: Updated tag or None if not found.
    """
    tag = get_tag(session, tag_id)
    if not tag:
        return None
    if tag.owner_id != owner_id:
        msg = "Not enough permissions to update this tag."
        raise PermissionError(msg)

    # Copy fields from tag_in
    updated_data = tag_in.model_dump(exclude_unset=True)
    for key, value in updated_data.items():
        setattr(tag, key, value)

    try:
        session.add(tag)
        session.commit()
        session.refresh(tag)
    except Exception:
        logger.exception("Failed to update tag")
        session.rollback()
        raise
    return tag


def delete_tag(session: Session, tag_id: int, owner_id: uuid.UUID) -> bool:
    """Delete a tag by ID if owner matches.

    Returns: True if deleted, False otherwise.
    """
    tag = get_tag(session, tag_id)
    if not tag:
        return False
    if tag.owner_id != owner_id:
        msg = "Not enough permissions to delete this tag."
        raise PermissionError(msg)

    try:
        session.delete(tag)
        session.commit()
    except Exception:
        logger.exception("Failed to delete tag")
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
) -> tuple[Sequence[Creator], int]:
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
    session: Session,
    creator_in: CreatorCreate,
    item_id: uuid.UUID,
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
) -> tuple[Sequence[Relation], int]:
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
    session: Session,
    relation_in: RelationCreate,
    item_id: uuid.UUID,
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
    """Update a Relation by ID; returns updated relation or None."""
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
    session: Session,
    collection_in: CollectionCreate,
    item_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> Collection:
    """Create a new Collection associated with an item."""
    collection = Collection.model_validate(
        collection_in,
        update={"item_id": item_id, "owner_id": owner_id},
    )
    session.add(collection)
    session.commit()
    session.refresh(collection)
    return collection


def update_study_site(
    *,
    session: Session,
    db_study_site: StudySite,
    study_site_in: StudySiteUpdate,
) -> StudySite:
    study_site_data = study_site_in.model_dump(exclude_unset=True)
    extra_data = {
        "confidence_score": 1.0,
        "extraction_method": "manual",
    }
    db_study_site.sqlmodel_update(study_site_data, update=extra_data)
    session.add(db_study_site)
    session.commit()
    session.refresh(db_study_site)
    return db_study_site

def create_location_if_needed(
    *,
    session: Session,
    latitude: Latitude,
    longitude: Longitude,
) -> Location:
    existing_location = get_location_by_lat_lon(
        session=session,
        latitude=latitude,
        longitude=longitude,
    )
    if existing_location:
        return existing_location

    new_location = Location(
        latitude=latitude,
        longitude=longitude,
    )
    session.add(new_location)
    session.commit()
    session.refresh(new_location)
    return new_location

def get_location_by_lat_lon(
    *,
    session: Session,
    latitude: Latitude,
    longitude: Longitude,
) -> Location | None:
    statement = select(Location).where(
        Location.latitude == float(latitude),
        Location.longitude == float(longitude),
    )
    return session.exec(statement).first()


def create_study_site(
    session: Session,
    study_site_data: StudySiteCreate,
) -> StudySite:
    """Create a study site with location deduplication."""
    location_id = study_site_data.location_id

    if (
        location_id is None
        and study_site_data.latitude is not None
        and study_site_data.longitude is not None
    ):
        # Check for existing location
        existing_location = get_location_by_lat_lon(
            session=session,
            latitude=study_site_data.latitude,
            longitude=study_site_data.longitude,
        )

        if existing_location:
            location_id = existing_location.id
        else:
            # Create new location
            location = Location(
                latitude=study_site_data.latitude,
                longitude=study_site_data.longitude,
            )
            session.add(location)
            session.commit()
            session.refresh(location)
            location_id = location.id

    # Create study site
    study_site_dict = study_site_data.model_dump(
        exclude={"latitude", "longitude", "location_id"},
    )
    study_site_dict["location_id"] = location_id

    study_site = StudySite(**study_site_dict)  # pyright: ignore[reportAny]
    session.add(study_site)
    session.flush()
    session.refresh(study_site)

    return study_site
