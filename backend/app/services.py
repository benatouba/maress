from pyzotero import zotero


class Zotero(zotero.Zotero):
    def __init__(self, library_id: str, api_key: str, library_type: str = "user"):
        # Initialize Zotero client with init function from pyzotero and extend it
        super().__init__(
            library_id=library_id, library_type=library_type, api_key=api_key
        )
        # self.library_id: str = library_id
        # self.library_type: str = library_type
        # self.api_key: str = api_key
