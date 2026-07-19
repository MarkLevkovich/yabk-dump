from dataclasses import dataclass

from yandex_books import YandexBookClient


@dataclass
class BookInfo:
    title: str
    authors: list
    lang: str
    publication_date: int
    about: str


def get_book_info(client: YandexBookClient, book_id: str) -> BookInfo:
    book = client.get_book(book_id)
    return BookInfo(
        title=book.title,
        authors=[a.name for a in book.authors_objects],
        lang=book.language,
        publication_date=book.publication_date,
        about=book.annotation,
    )
