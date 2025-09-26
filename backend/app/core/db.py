from collections.abc import Generator

from sqlalchemy.orm import sessionmaker
from sqlmodel import Session as SQLModelSession
from sqlmodel import create_engine, select

from app import crud
from app.core.config import settings
from app.models import *  # noqa: F403
from app.models import User, UserCreate

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI), pool_pre_ping=True)


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=SQLModelSession)


def get_session() -> Generator[SQLModelSession, None, None]:
    with SessionLocal() as session:
        yield session


def init_db(session: SQLModelSession) -> None:
    user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER),
    ).first()
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        )
        user = crud.create_user(session=session, user_create=user_in)
