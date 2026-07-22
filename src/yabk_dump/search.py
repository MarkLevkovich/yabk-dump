from yandex_book import YandexBookClient


def search_book(query: str, yclient: YandexBookClient):
    results = yclient.search(query)
    res = {}

    if not results or "data" not in results or "search" not in results["data"]:
        return res

    for item in results["data"]["search"]["page"]:
        book = item.get("book", "Unknown")
        if not book:
            continue

        title = book.get("name")
        if not title:
            continue

        authors = book.get("authors", [])
        if authors:
            author = authors[0].get("name", "Unknown")
        else:
            author = "Unknown"
        res[title] = author
    return res
