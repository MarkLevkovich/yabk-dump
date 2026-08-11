from unittest.mock import Mock

from yabk_dump.search import search_book


def make_client(payload):
    client = Mock()
    client.search.return_value = payload
    return client


def test_none_results():
    assert search_book("q", make_client(None)) == {}


def test_empty_results():
    assert search_book("q", make_client({})) == {}


def test_missing_data_key():
    assert search_book("q", make_client({"other": 1})) == {}


def test_data_missing_search():
    assert search_book("q", make_client({"data": {"page": []}})) == {}


def test_data_none_returns_empty():
    assert search_book("q", make_client({"data": None})) == {}


def test_search_empty():
    assert search_book("q", make_client({"data": {"search": {}}})) == {}
    assert search_book("q", make_client({"data": {"search": {"page": []}}})) == {}


def test_full_payload_mapping():
    payload = {
        "data": {
            "search": {
                "page": [
                    {
                        "book": {
                            "name": "B1",
                            "uuid": "u1",
                            "authors": [{"name": "A1"}],
                        }
                    },
                    {"book": {"name": "B2", "uuid": "u2", "authors": []}},
                    {"book": {"name": "B3", "uuid": "u3"}},
                ]
            }
        }
    }
    result = search_book("q", make_client(payload))
    assert result == {
        "B1": {"author": "A1", "id": "u1"},
        "B2": {"author": "Unknown", "id": "u2"},
        "B3": {"author": "Unknown", "id": "u3"},
    }


def test_skips_incomplete_entries():
    payload = {
        "data": {
            "search": {
                "page": [
                    {"book": {"uuid": "u1", "authors": [{"name": "A"}]}},
                    {"book": {"name": "B2"}},
                    {"other": 1},
                    {
                        "book": {
                            "name": "B4",
                            "uuid": "u4",
                            "authors": [{"name": "A4"}],
                        }
                    },
                ]
            }
        }
    }
    assert search_book("q", make_client(payload)) == {
        "B4": {"author": "A4", "id": "u4"}
    }


def test_search_called_with_textbook_type():
    client = make_client({})
    search_book("query", client)
    client.search.assert_called_once_with("query", types=["TEXTBOOK"])
