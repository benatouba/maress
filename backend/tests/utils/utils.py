from __future__ import annotations

import secrets
import string
from typing import TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


alphabet = string.ascii_letters.lower() + string.digits
def random_lower_string() -> str:
    return "".join(secrets.choice(alphabet) for _ in range(32))


def random_email() -> str:
    return f"{random_lower_string()}@{random_lower_string()}.com"


def get_superuser_token_headers(client: TestClient) -> dict[str, str]:
    login_data = {
        "username": settings.FIRST_SUPERUSER,
        "password": settings.FIRST_SUPERUSER_PASSWORD,
    }
    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
    tokens = r.json()  # pyright: ignore[reportAny]
    a_token = tokens["access_token"]  # pyright: ignore[reportAny]
    headers: dict[str, str] = {"Authorization": f"Bearer {a_token}"}
    return headers
