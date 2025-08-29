import logging
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from magic import Magic
from sqlalchemy.orm import selectinload
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.models import (
    Item,
    ItemCreate,
    ItemPublic,
    ItemsPublic,
    ItemUpdate,
    Message,
    StudySite,
)
from app.nlp.find_my_home import StudySiteExtractor
from app.services import Zotero
from maress_types import ZoteroItemList

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/items", tags=["items"])


def read_db_items(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 500
) -> tuple[Sequence[Item], int]:
    """Helper function to retrieve items with pagination."""
    if current_user.is_superuser:
        count_statement = select(func.count()).select_from(Item)
        count = session.exec(count_statement).one()
        statement = select(Item).offset(skip).limit(limit)
        items = session.exec(statement).all()
    else:
        count_statement = (
            select(func.count())
            .select_from(Item)
            .where(Item.owner_id == current_user.id)
        )
        count = session.exec(count_statement).one()
        statement = (
            select(Item)
            .where(Item.owner_id == current_user.id)
            .offset(skip)
            .limit(limit)
        )
        items = session.exec(statement).all()
    return items, count


@router.get("/")
def read_items(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 10
) -> ItemsPublic:
    """Retrieve items."""
    items, count = read_db_items(session, current_user, skip, limit)
    return ItemsPublic(data=items, count=count)  # pyright: ignore[reportArgumentType]


@router.get("/{id}", response_model=ItemPublic)
def read_item(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Item:
    """Get item by ID."""
    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
    return item


@router.post("/", response_model=ItemPublic)
def create_item(
    *, session: SessionDep, current_user: CurrentUser, item_in: ItemCreate
) -> Any:
    """Create new item."""
    item = Item.model_validate(item_in, update={"owner_id": current_user.id})
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.get("/import_from_zotero/")
def import_zotero_items(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 500
):
    zot = Zotero(
        library_id=settings.ZOTERO_USER_ID,
        library_type=settings.ZOTERO_LIBRARY_TYPE,
        api_key=settings.ZOTERO_API_KEY,
    )
    # if not limit or limit is greater than 100, repeat until all items are fetched
    zot_items: ZoteroItemList = []
    start = skip
    while True:
        batch: ZoteroItemList = zot.collection_items_top("AQXEVQ8C", start=start)
        if not batch:
            break
        zot_items.extend(batch)
        if len(batch) < 100:
            break
        start += 100
    # apply limit to the total items fetched
    if limit:
        zot_items = zot_items[:limit]
    zot_items_data = [item["data"] for item in zot_items]
    local_items, _ = read_db_items(session, current_user, skip, limit)
    local_keys = [item.key for item in local_items]
    new_items = [
        Item.model_validate(item, update={"owner_id": current_user.id})
        for item in zot_items_data
        if item["key"] not in local_keys
    ]
    # if not new_items:
    #     return Message(message="No new items to import from Zotero")
    session.add_all(new_items)
    session.commit()
    for item in new_items:
        session.refresh(item)
    return ItemsPublic(data=new_items, count=len(new_items))  # pyright: ignore[reportArgumentType]


@router.get("/import_file_zotero/{id}", response_model=ItemPublic)
def import_file_from_zotero(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Any:
    """Import a single item from Zotero by file ID."""
    zot = Zotero(
        library_id=settings.ZOTERO_USER_ID,
        library_type=settings.ZOTERO_LIBRARY_TYPE,
        api_key=settings.ZOTERO_API_KEY,
    )

    item: Item = read_item(session, current_user, id)
    zot_item = zot.item(item.key)
    if not zot_item:
        raise HTTPException(status_code=404, detail="Zotero item not found")
    if "links" not in zot_item:
        logger.warning(f"Zotero item {item.key} does not have links. The item is: {zot_item}")
        return item
    if "attachment" not in zot_item["links"]:
        logger.warning(
            f"Zotero item {item.key} does not have an attachment link. The item links are: {zot_item['links']}"
        )
        return item
    if not zot_item["links"]["attachment"].get("href"):
        logger.warning(
            f"Zotero item {item.key} does not have a valid attachment link. The item links are: {zot_item['links']}"
        )
        return item
    file_key = str(zot_item["links"]["attachment"]["href"].split("/")[-1])
    file_path: Path = Path.cwd() / "zotero_files" / (file_key + ".pdf")
    if not file_path.is_file():
        with file_path.open("wb") as f:
            file: bytes = zot.file(file_key)
            if not isinstance(file, bytes):
                raise HTTPException(
                    status_code=400, detail="Zotero file is not a valid byte stream"
                )
            if not file:
                raise HTTPException(status_code=404, detail="Zotero file not found")
            m = Magic(mime=True)
            if not m.from_buffer(file) == "application/pdf":
                logger.warning( "Only PDF files can be imported from Zotero")
                return item
            # TODO: More malware checking should be done here (e.g. yara rules, and )
            f.write(file)

    updated_item = ItemUpdate(attachment=str(file_path))
    item = update_item(
        session=session,
        current_user=current_user,
        id=id,
        item_in=updated_item,
    )
    return item


@router.get("/import_file_zotero/", response_model=ItemsPublic)
def import_files_from_zotero(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 10
) -> Any:
    items, _ = read_db_items(session, current_user, skip, limit)
    for item in items:
        if item.attachment:
            continue
        if Path(item.attachment or "").is_file():
            continue
        db_item = import_file_from_zotero(
            session=session, current_user=current_user, id=item.id
        )
        if not db_item:
            raise HTTPException(
                status_code=404, detail=f"Item {item.id} not found in Zotero"
            )
    items, count = read_db_items(session, current_user, skip, limit)
    return ItemsPublic(data=items, count=count)  # pyright: ignore[reportArgumentType]


@router.put("/{id}", response_model=ItemPublic)
def update_item(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    item_in: ItemUpdate,
) -> Any:
    """Update an item."""
    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
    update_dict = item_in.model_dump(exclude_unset=True)
    item.sqlmodel_update(update_dict)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.delete("/{id}")
def delete_item(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """Delete an item."""
    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
    session.delete(item)
    session.commit()
    return Message(message="Item deleted successfully")


@router.post("/study_sites/", response_model=Any)
def extract_study_site(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID | None = None
) -> Any:
    """Use StudySiteExtractor to get study site from items."""

    def extract_study_sites(
        session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 500
    ) -> ItemsPublic:
        """Get all items with study sites."""
        items, _ = read_db_items(session, current_user, skip, limit)
        # items without study sites
        items_without_study_sites = [item for item in items if not item.study_site_id]
        new_study_sites_items: list[Item] = []
        for item in items_without_study_sites:
            new_item: Item = extract_study_site(
                session=session,
                current_user=current_user,
                id=item.id,
            )
            new_study_sites_items.append(new_item)
        return ItemsPublic(data=new_study_sites_items, count=len(new_study_sites_items))  # pyright: ignore[reportArgumentType]

    print(id)
    if id is None or id == "null":
        # If no ID is provided, extract study sites for all items
        return extract_study_sites(session, current_user)

    item = read_item(session, current_user, id)
    if item.study_site_id:
        return item  # Study site already exists, return the item
    if not item.attachment:
        msg = "Item does not have an attachment"
        logger.warning(msg)
        return item  # No attachment to process
    path = Path(item.attachment)
    if not path.exists():
        msg = f"File {path} does not exist in the filesystem"
        raise FileNotFoundError(msg)
    extractor = StudySiteExtractor()
    result = extractor.extract_study_site(path)
    if not result or not result.primary_study_site:
        logger.warning(
            f"Study site not found in the item {item.id} with attachment {item.attachment}"
        )
        return item
    primary_candidate = result.primary_study_site
    study_site = StudySite(
        validation_score=result.validation_score,
        latitude=primary_candidate.latitude,
        longitude=primary_candidate.longitude,
        confidence_score=primary_candidate.confidence_score,
        source_type=primary_candidate.source_type,
        context=primary_candidate.context,
        page_number=primary_candidate.page_number,
        extraction_method=primary_candidate.extraction_method,
        owner_id=current_user.id,
    )
    # add study site to the session and update the item
    session.add(study_site)
    session.commit()
    session.refresh(study_site)
    # item = item.model_copy(update={"study_site_id": study_site.id})
    item.study_site_id = study_site.id
    session.add(item)
    session.commit()
    session.refresh(item)
    # refresh the item to get the updated study_site
    item_from_db = session.get(Item, item.id)
    if not item_from_db:
        msg = "Item not found in the database after update"
        raise ValueError(msg)
    if not item_from_db.study_site_id:
        msg = "Study site not found in the item after update"
        raise ValueError(msg)
    return item_from_db


@router.get("/study_sites/{id}", response_model=StudySite)
def get_study_site(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> StudySite:
    """Get study site by item ID."""
    study_site = session.get(StudySite, id)
    if not study_site:
        raise HTTPException(status_code=404, detail="StudySite not found")
    if not current_user.is_superuser and (study_site.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
    return study_site


@router.get("/study_sites/", response_model=Sequence[StudySite])
def get_study_sites(
    session: SessionDep, current_user: CurrentUser
) -> Sequence[StudySite]:
    """Get all study sites."""
    statement = select(StudySite).where(StudySite.owner_id == current_user.id)
    if not current_user.is_superuser:
        statement = statement.where(StudySite.owner_id == current_user.id)
    study_sites = session.exec(statement).all()
    if not study_sites:
        raise HTTPException(status_code=404, detail="No study sites found")
    return study_sites
