from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import SessionDep
from app.core.config import settings
from app.core.security import get_password_hash
from app.models import (
    User,
    UserPublic,
)

router = APIRouter(tags=["private"], prefix="/private")


class PrivateUserCreate(BaseModel):
    email: str
    password: str
    full_name: str = "Super User"
    is_verified: bool = False
    zotero_id: str | None = settings.ZOTERO_USER_ID
    enc_zotero_api_key: str | None = settings.ZOTERO_API_KEY


@router.post("/users/", response_model=UserPublic)
def create_user(user_in: PrivateUserCreate, session: SessionDep) -> Any:
    """Create a new user."""
    user = User(
        email=user_in.email,
        full_name=user_in.full_name,
        hashed_password=get_password_hash(user_in.password),
        zotero_id=user_in.zotero_id,
        zotero_api_key=user_in.enc_zotero_api_key,
    )

    session.add(user)
    session.commit()

    return user
