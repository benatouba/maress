from pyzotero import zotero

from app.models import User


class Zotero(zotero.Zotero):
    def __init__(self, user: User, library_type: str = "user"):
        # Initialize Zotero client with init function from pyzotero and extend it
        user_json = user.model_dump()
        super().__init__(
            library_id=user_json["zotero_id"],
            library_type=library_type,
            api_key=user_json["enc_zotero_api_key"],
        )
