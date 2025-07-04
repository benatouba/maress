import sys

from pyzotero import zotero

from maress.config import config


def main():
    print("Hello from maress!")

    zot = zotero.Zotero(
        config["PERSONAL_LIBRARY_ID"],
        config["ZOTERO"]["LIBRARY_TYPE"],
        config["ZOTERO_API_KEY"],
    )

    collection = zot.collections()[0]

    COLLECTION_KEY = collection["key"]
    limit = 100
    unread_items = zot.collection_items(COLLECTION_KEY, limit=limit)
    for item in unread_items:
        url = item["data"]["url"]
        if url.startswith("http"):
            print(url, flush=True)
        else:
            print("Bad url: " + url, file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
