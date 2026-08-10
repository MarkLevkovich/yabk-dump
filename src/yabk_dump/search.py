from yandex_book import YandexBookClient


def search_book(query: str, yclient: YandexBookClient):
    results = yclient.search(query, types=["TEXTBOOK"])
    res = {}

    if not results or "data" not in results or "search" not in results.get("data", ""):
        return res

    for item in results.get("data", {}).get("search", {}).get("page", []):
        book = item.get("book")
        if not book:
            continue

        title = book.get("name")
        if not title:
            continue
        book_id = book.get("uuid")
        if not book_id:
            continue

        authors = book.get("authors", [])
        if authors:
            author = authors[0].get("name", "Unknown")
        else:
            author = "Unknown"
        res[title] = {"author": author, "id": book_id}
    return res
