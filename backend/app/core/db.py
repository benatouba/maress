# pyright: reportUnusedImport=false
from collections.abc import Generator

from sqlalchemy.orm import sessionmaker
from sqlmodel import Session as SQLModelSession
from sqlmodel import create_engine, select

from app import crud
from app.core.config import settings
from app.models import Collection  # noqa: F401
from app.models import Creator  # noqa: F401
from app.models import Item  # noqa: F401
from app.models import ItemTagLink  # noqa: F401
from app.models import Relation  # noqa: F401
from app.models import StudySite  # noqa: F401
from app.models import Tag  # noqa: F401
from app.models import User, UserCreate

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI), pool_pre_ping=True)


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=SQLModelSession)


def get_session() -> Generator[SQLModelSession, None, None]:
    """Get a new database session.

    Needed for async endpoints, async testing or celery tasks.

    Yields:
        A new local database session.
    """
    with SessionLocal() as session:
        yield session


def init_db(session: SQLModelSession) -> None:
    """Initialize the database with the first superuser.

    Args:
        session: An SQLModel session to interact with the database.
    """
    user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER),
    ).first()
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
            is_active=True,
            full_name="Admin",
            zotero_id=settings.ZOTERO_USER_ID,
            zotero_api_key=settings.ZOTERO_API_KEY,
        )
        user = crud.create_user(session=session, user_create=user_in)
