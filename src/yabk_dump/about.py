from dataclasses import dataclass
from datetime import UTC, datetime

from yandex_book import YandexBookClient


@dataclass
class BookInfo:
    uuid: str = "No info"
    title: str = "No info"
    authors: str = "No info"
    translators: str = "No info"
    lang: str = "No info"
    publication_date: str = "No info"
    about: str = "No info"
    editor_annotation: str = "No info"
    readers_count: str = "No info"
    bookshelves_count: str = "No info"


def get_book_info(client: YandexBookClient, book_id: str) -> BookInfo:
    book = client.get_book(book_id)
    return BookInfo(
        uuid=book.uuid or "No info",
        title=book.display_title or "No info",
        authors=", ".join(a.name for a in book.authors_objects) or "No info",
        translators=", ".join(t.name for t in book.translators)
        if book.translators
        else "No info",
        lang=book.language or "No info",
        publication_date=str(datetime.fromtimestamp(book.publication_date, tz=UTC))
        if book.publication_date
        else "No info",
        about=book.annotation or "No info",
        editor_annotation=book.editor_annotation or "No info",
        readers_count=str(book.readers_count) if book.readers_count else "No info",
        bookshelves_count=str(book.bookshelves_count)
        if book.bookshelves_count
        else "No info",
    )
