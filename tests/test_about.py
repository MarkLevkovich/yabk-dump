from types import SimpleNamespace

from yabk_dump.about import BookInfo, get_book_info


def make_client(book):
    return SimpleNamespace(get_book=lambda book_id: book)


def test_full_field_mapping():
    book = SimpleNamespace(
        uuid="U1",
        display_title="Title",
        authors_objects=[SimpleNamespace(name="A"), SimpleNamespace(name="B")],
        translators=[SimpleNamespace(name="T")],
        language="ru",
        publication_date=1735689600,
        annotation="about text",
        editor_annotation="editor note",
        readers_count=5,
        bookshelves_count=3,
    )
    info = get_book_info(make_client(book), "bookid")
    assert isinstance(info, BookInfo)
    assert info.uuid == "U1"
    assert info.title == "Title"
    assert info.authors == "A, B"
    assert info.translators == "T"
    assert info.lang == "ru"
    assert info.publication_date == "2025-01-01 00:00:00+00:00"
    assert info.about == "about text"
    assert info.editor_annotation == "editor note"
    assert info.readers_count == "5"
    assert info.bookshelves_count == "3"


def test_missing_fields_default_to_no_info():
    book = SimpleNamespace(
        uuid=None,
        display_title=None,
        authors_objects=[],
        translators=[],
        language=None,
        publication_date=None,
        annotation=None,
        editor_annotation=None,
        readers_count=None,
        bookshelves_count=None,
    )
    info = get_book_info(make_client(book), "bookid")
    assert info.uuid == "No info"
    assert info.title == "No info"
    assert info.authors == "No info"
    assert info.translators == "No info"
    assert info.lang == "No info"
    assert info.publication_date == "No info"
    assert info.about == "No info"
    assert info.editor_annotation == "No info"
    assert info.readers_count == "No info"
    assert info.bookshelves_count == "No info"


def test_zero_counters_default_to_no_info():
    book = SimpleNamespace(
        uuid="U",
        display_title="T",
        authors_objects=[],
        translators=[],
        language="ru",
        publication_date=1,
        annotation=None,
        editor_annotation=None,
        readers_count=0,
        bookshelves_count=0,
    )
    info = get_book_info(make_client(book), "bookid")
    assert info.readers_count == "No info"
    assert info.bookshelves_count == "No info"


def test_no_translators_default_to_no_info():
    book = SimpleNamespace(
        uuid="U",
        display_title="T",
        authors_objects=[SimpleNamespace(name="A")],
        translators=[],
        language=None,
        publication_date=None,
        annotation=None,
        editor_annotation=None,
        readers_count=None,
        bookshelves_count=None,
    )
    info = get_book_info(make_client(book), "bookid")
    assert info.authors == "A"
    assert info.translators == "No info"
