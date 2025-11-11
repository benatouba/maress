"""Service layer for external integrations."""

from __future__ import annotations

from pyzotero import zotero

from app.models import User


class Zotero(zotero.Zotero):
    """Zotero API client wrapper with user authentication.

    Extends pyzotero.Zotero to automatically configure with user credentials.

    Example:
        >>> zot = Zotero(user, library_type="user")
        >>> items = zot.items()
    """

    def __init__(self, user: User, library_type: str = "user") -> None:
        """Initialize Zotero client with user credentials.

        Args:
            user: User model with Zotero credentials
            library_type: Library type ("user" or "group")
        """
        user_json = user.model_dump()
        super().__init__(
            library_id=user_json["zotero_id"],
            library_type=library_type,
            api_key=user_json["enc_zotero_api_key"],
        )
