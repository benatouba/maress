from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel

from app.core.config import settings
from app.main import app
from app.models.collections import Collection  # noqa: F401
from app.models.creators import Creator  # noqa: F401
from app.models.items import Item  # noqa: F401
from app.models.links import ItemTagLink  # noqa: F401
from app.models.relations import Relation  # noqa: F401
from app.models.study_sites import StudySite  # noqa: F401
from app.models.tags import Tag  # noqa: F401
from app.models.users import User
from app.services import SpaCyModelManager

# Create a separate test database
POSTGRES_BASE_URL = str(settings.SQLALCHEMY_DATABASE_URI).rsplit("/", 1)[0]
TEST_DATABASE_NAME = "maress_test"
TEST_DATABASE_URL = f"{POSTGRES_BASE_URL}/{TEST_DATABASE_NAME}"
test_engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
TestSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False, class_=Session)


@pytest.fixture(scope="session")
def create_test_database():
    """Create test database at session start, drop at session end."""
    admin_engine = create_engine(f"{POSTGRES_BASE_URL}/postgres", isolation_level="AUTOCOMMIT")

    try:
        with admin_engine.connect() as conn:
            # Check if database exists first
            result = conn.execute(
                text(f"SELECT 1 FROM pg_database WHERE datname = '{TEST_DATABASE_NAME}'"),
            )
            if not result.fetchone():
                conn.execute(text(f"CREATE DATABASE {TEST_DATABASE_NAME}"))

        yield  # Run all tests

    finally:
        # Clean up: close all connections first, then drop database
        try:
            test_engine.dispose()  # ✅ Close all connections first

            with admin_engine.connect() as conn:
                # Terminate any remaining connections
                conn.execute(
                    text(f"""
                    SELECT pg_terminate_backend(pg_stat_activity.pid)
                    FROM pg_stat_activity
                    WHERE pg_stat_activity.datname = '{TEST_DATABASE_NAME}'
                      AND pid <> pg_backend_pid()
                """),
                )

                # Now drop the database
                conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DATABASE_NAME}"))
        except Exception as e:
            print(f"Database cleanup failed: {e}")
        finally:
            admin_engine.dispose()


@pytest.fixture(autouse=True)
def setup_fresh_db_per_test(create_test_database) -> Generator[None, None, None]:
    """Fresh database setup for each test - single source of truth."""
    # Create all tables
    SQLModel.metadata.create_all(bind=test_engine)

    yield  # Test runs here

    # Clean up: truncate all tables (faster than drop/create)
    try:
        with TestSessionLocal() as session:
            # Disable foreign key checks temporarily for truncation
            session.execute(text("SET session_replication_role = replica;"))

            # Truncate all tables
            for table in reversed(SQLModel.metadata.sorted_tables):
                session.execute(text(f'TRUNCATE TABLE "{table.name}" RESTART IDENTITY CASCADE'))

            # Re-enable foreign key checks
            session.execute(text("SET session_replication_role = DEFAULT;"))
            session.commit()
    except Exception as e:
        print(f"Table cleanup failed: {e}")
        # Fallback: drop and recreate all tables
        SQLModel.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session(setup_fresh_db_per_test) -> Generator[Session, None, None]:
    """Database session for tests that need direct database access."""
    with TestSessionLocal() as session:
        yield session


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Test client with overridden database session."""
    from app.api.deps import get_db

    def override_get_session() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create a test user."""
    from tests.utils.user import create_test_user

    return create_test_user(db_session)


@pytest.fixture
def test_superuser(db_session: Session) -> User:
    """Create a test superuser."""
    from tests.utils.user import create_test_user

    return create_test_user(
        db_session,
        email=settings.FIRST_SUPERUSER,
        password=settings.FIRST_SUPERUSER_PASSWORD,
        is_superuser=True,
    )


@pytest.fixture
def superuser_token_headers(
    client: TestClient,
    db_session: Session,
    test_superuser: User,
) -> dict[str, str]:
    """Fresh superuser token for each test."""
    from tests.utils.utils import get_superuser_token_headers

    return get_superuser_token_headers(client=client)


@pytest.fixture
def normal_user_token_headers(
    db_session: Session,
    client: TestClient,
    test_user: User,
) -> dict[str, str]:
    """Fresh normal user token for each test."""
    from tests.utils.user import authentication_token_from_email

    return authentication_token_from_email(
        client=client,
        email=test_user.email,
        db=db_session,
    )


@pytest.fixture(scope="module")
def model_manager() -> SpaCyModelManager:
    return SpaCyModelManager()


@pytest.fixture(scope="module")
def example_pdf_path() -> Path:
    return (Path(__file__).parent / "zotero_files").resolve().glob("*.pdf").__next__()
