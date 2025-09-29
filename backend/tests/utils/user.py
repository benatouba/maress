from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import User, UserCreate, UserUpdate
from tests.utils.utils import random_lower_string


def user_authentication_headers(
    *,
    client: TestClient,
    email: str,
    password: str,
) -> dict[str, str]:
    data = {"username": email, "password": password}

    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=data)
    response = r.json()
    auth_token = response["access_token"]
    headers = {"Authorization": f"Bearer {auth_token}"}
    return headers


def create_test_user(
    db_session: Session,
    *,
    email: str | None = None,
    password: str | None = None,
    is_superuser: bool = False,
) -> User:
    """Create a test user with proper credentials."""
    from app.core.security import get_password_hash
    from app.models import User
    from tests.factories import UserFactory

    # Use settings credentials for superuser, test credentials for regular user
    if is_superuser:
        email = email or settings.FIRST_SUPERUSER
        password = password or settings.FIRST_SUPERUSER_PASSWORD
        user = UserFactory.build(is_superuser=True, is_active=True, email=email)
    else:
        user = UserFactory.build(is_active=True)
        password = password if password is not None else random_lower_string()

    user.hashed_password = get_password_hash(password)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    user._test_password = password

    return user


def authentication_token_from_email(
    *,
    client: TestClient,
    email: str,
    db: Session,
) -> dict[str, str]:
    """Return a valid token for the user with given email.

    If the user doesn't exist it is created first.
    """
    password = random_lower_string()
    user = crud.get_user_by_email(session=db, email=email)
    if not user:
        user_in_create = UserCreate(email=email, password=password)
        user = crud.create_user(session=db, user_create=user_in_create)
    else:
        user_in_update = UserUpdate(password=password)
        if not user.id:
            msg = "User id not set"
            raise ValueError(msg)
        user = crud.update_user(session=db, db_user=user, user_in=user_in_update)

    return user_authentication_headers(client=client, email=email, password=password)
