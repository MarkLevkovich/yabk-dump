import logging
from unittest.mock import MagicMock, call

import pytest
from colorama import Fore, Style

from yabk_dump import cli
from yabk_dump.about import BookInfo


class _FakeAsk:
    def __init__(self, value):
        self._value = value

    def ask(self):
        return self._value


class _Q:
    def __init__(self, selects, texts):
        self._sel = iter(selects)
        self._txt = iter(texts)

    def select(self, *args, **kwargs):
        return _FakeAsk(next(self._sel))

    def text(self, *args, **kwargs):
        return _FakeAsk(next(self._txt))


def _patch_questionary(monkeypatch, selects, texts):
    monkeypatch.setattr(cli, "questionary", _Q(selects, texts))


def _patch_run_setup(monkeypatch, selects, texts):
    _patch_questionary(monkeypatch, selects, texts)
    client = MagicMock()
    monkeypatch.setattr(cli, "YandexBookClient", MagicMock(return_value=client))
    return client


class TestGetIdFromUrl:
    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://books.yandex.ru/book/KFHDG3bp/", "KFHDG3bp"),
            ("https://books.yandex.ru/book/KFHDG3bp", "KFHDG3bp"),
            ("https://books.yandex.ru/book/KFHDG3bp?x=1&y=2", "KFHDG3bp"),
            ("https://books.yandex.ru/book/KFHDG3bp/#section", "KFHDG3bp"),
            ("books.yandex.ru/book/ABC", "ABC"),
        ],
    )
    def test_extracts_id(self, url, expected):
        assert cli.get_id_from_url(url) == expected

    @pytest.mark.parametrize("url", ["", None, "https://books.yandex.ru/"])
    def test_invalid_returns_none(self, url):
        assert cli.get_id_from_url(url) is None


class TestGetCookies:
    def test_uses_env_session_id(self, monkeypatch):
        monkeypatch.setenv("SESSION_ID", "sess123")
        chrome = MagicMock()
        monkeypatch.setattr(cli.rookiepy, "chrome", chrome)
        assert cli.get_cookies() == {"Session_id": "sess123"}
        chrome.assert_not_called()

    def test_uses_matching_rookiepy_cookie(self, monkeypatch):
        monkeypatch.delenv("SESSION_ID", raising=False)
        monkeypatch.setattr(
            cli.rookiepy,
            "chrome",
            lambda *a, **k: [{"name": "Session_id", "value": "v1"}],
        )
        assert cli.get_cookies() == {"Session_id": "v1"}

    def test_lowercase_sessionid_cookie(self, monkeypatch):
        monkeypatch.delenv("SESSION_ID", raising=False)
        monkeypatch.setattr(
            cli.rookiepy,
            "chrome",
            lambda *a, **k: [{"name": "sessionid", "value": "v2"}],
        )
        assert cli.get_cookies() == {"Session_id": "v2"}

    def test_no_match_falls_back_to_input(self, monkeypatch):
        monkeypatch.delenv("SESSION_ID", raising=False)
        monkeypatch.setattr(
            cli.rookiepy,
            "chrome",
            lambda *a, **k: [{"name": "other", "value": "x"}],
        )
        prompts = []
        monkeypatch.setattr(
            "builtins.input",
            lambda prompt: (prompts.append(prompt), "manual")[1],
        )
        assert cli.get_cookies() == {"Session_id": "manual"}
        assert prompts

    def test_cookie_without_name_falls_back_to_input(self, monkeypatch):
        monkeypatch.delenv("SESSION_ID", raising=False)
        monkeypatch.setattr(cli.rookiepy, "chrome", lambda *a, **k: [{"value": "x"}])
        prompts = []
        monkeypatch.setattr(
            "builtins.input",
            lambda prompt: (prompts.append(prompt), "manual")[1],
        )
        assert cli.get_cookies() == {"Session_id": "manual"}
        assert prompts

    def test_rookiepy_error_falls_back_to_input(self, monkeypatch):
        monkeypatch.delenv("SESSION_ID", raising=False)
        monkeypatch.setattr(
            cli.rookiepy,
            "chrome",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no chrome")),
        )
        prompts = []
        monkeypatch.setattr(
            "builtins.input",
            lambda prompt: (prompts.append(prompt), "manual")[1],
        )
        assert cli.get_cookies() == {"Session_id": "manual"}
        assert prompts


class TestColoramaFormatter:
    def test_levelname_is_colored(self):
        record = logging.LogRecord("t", logging.ERROR, "f.py", 1, "boom", (), None)
        formatted = cli.ColoramaFormatter("%(levelname)s %(message)s").format(record)
        assert formatted == f"{Fore.BLUE}ERROR{Style.RESET_ALL} boom"


class TestMain:
    def _book_info(self):
        return BookInfo(uuid="U", title="T")

    def _default_patches(self, monkeypatch, outdir, selects):
        _patch_questionary(monkeypatch, selects, [str(outdir)])
        monkeypatch.setattr(cli, "get_cookies", lambda: {"Session_id": "sess"})
        monkeypatch.setattr(
            cli, "get_book_info", MagicMock(return_value=self._book_info())
        )
        book_client = MagicMock()
        book = MagicMock()
        book_client.get_book.return_value = book
        monkeypatch.setattr(cli, "BookClient", MagicMock(return_value=book_client))
        return book_client, book

    def test_downloads_book(self, tmp_path, monkeypatch, caplog):
        book_client, book = self._default_patches(
            monkeypatch, tmp_path / "out", ["No", "No", "No", "yes"]
        )
        with caplog.at_level(logging.INFO, logger="yabk_dump.cli"):
            cli.main(["https://books.yandex.ru/book/ABC/"], None)

        cli.BookClient.assert_called_once_with(
            output_dir=str(tmp_path / "out"), cookies={"Session_id": "sess"}
        )
        book_client.get_book.assert_called_once_with(book_id="ABC")
        book.run.assert_called_once()
        book.clear_styles.assert_not_called()
        book.build_epub.assert_not_called()
        book.cleanup.assert_not_called()
        assert "Book(s) successfully downloaded!" in caplog.text

    def test_no_download_skips_processing(self, tmp_path, monkeypatch, caplog):
        self._default_patches(monkeypatch, tmp_path / "out", ["No", "No", "No", "no"])
        with caplog.at_level(logging.INFO, logger="yabk_dump.cli"):
            cli.main(["https://books.yandex.ru/book/ABC/"], None)
        cli.BookClient.assert_not_called()
        assert "Book(s) successfully downloaded!" not in caplog.text

    def test_invalid_url_skipped_silently(self, tmp_path, monkeypatch, caplog):
        self._default_patches(monkeypatch, tmp_path / "out", ["No", "No", "No"])
        monkeypatch.setattr(cli, "get_book_info", MagicMock())
        with caplog.at_level(logging.INFO, logger="yabk_dump.cli"):
            cli.main([""], None)
        cli.get_book_info.assert_not_called()
        cli.BookClient.assert_not_called()
        assert "Book(s) successfully downloaded!" not in caplog.text

    def test_all_post_processing_options(self, tmp_path, monkeypatch):
        _, book = self._default_patches(
            monkeypatch, tmp_path / "out", ["Yes", "Yes", "Yes", "yes"]
        )
        cli.main(["https://books.yandex.ru/book/ABC/"], None)
        book.run.assert_called_once()
        book.clear_styles.assert_called_once()
        book.build_epub.assert_called_once()
        book.cleanup.assert_called_once()

    def test_batch_skips_invalid_url(self, tmp_path, monkeypatch):
        book_client, book = self._default_patches(
            monkeypatch, tmp_path / "out", ["No", "No", "No", "yes", "yes"]
        )
        urls = [
            "https://books.yandex.ru/book/ABC/",
            "",
            "https://books.yandex.ru/book/DEF/",
        ]
        cli.main(urls, None)
        assert book_client.get_book.call_args_list == [
            call(book_id="ABC"),
            call(book_id="DEF"),
        ]
        assert book.run.call_count == 2


class TestRun:
    def test_search_not_found_exits(self, monkeypatch, capsys):
        _patch_run_setup(monkeypatch, ["Search"], ["query"])
        monkeypatch.setattr(cli, "search_book", lambda *a, **k: {})
        main_mock = MagicMock()
        monkeypatch.setattr(cli, "main", main_mock)
        with pytest.raises(SystemExit):
            cli.run()
        assert "Not found" in capsys.readouterr().out
        main_mock.assert_not_called()

    def test_search_selects_book_and_calls_main(self, monkeypatch):
        client = _patch_run_setup(monkeypatch, ["Search"], ["query"])
        monkeypatch.setattr(
            cli,
            "search_book",
            lambda *a, **k: {"Title": {"author": "A", "id": "ABC"}},
        )
        monkeypatch.setattr("builtins.input", lambda *a, **k: "0")
        main_mock = MagicMock()
        monkeypatch.setattr(cli, "main", main_mock)
        cli.run()
        main_mock.assert_called_once()
        assert main_mock.call_args.args[0] == ["books.yandex.ru/ABC"]
        assert main_mock.call_args.args[1] is client

    def test_search_non_numeric_input_logs_error(self, monkeypatch, caplog):
        _patch_run_setup(monkeypatch, ["Search"], ["query"])
        monkeypatch.setattr(
            cli,
            "search_book",
            lambda *a, **k: {"Title": {"author": "A", "id": "ABC"}},
        )
        monkeypatch.setattr("builtins.input", lambda *a, **k: "abc")
        with caplog.at_level(logging.ERROR, logger="yabk_dump.cli"):
            cli.run()
        assert "Please enter a number" in caplog.text

    def test_search_out_of_range_exits(self, monkeypatch, caplog):
        _patch_run_setup(monkeypatch, ["Search"], ["query"])
        monkeypatch.setattr(
            cli,
            "search_book",
            lambda *a, **k: {"Title": {"author": "A", "id": "ABC"}},
        )
        monkeypatch.setattr("builtins.input", lambda *a, **k: "5")
        with pytest.raises(SystemExit):
            cli.run()
        assert "Invalid selection" in caplog.text

    def test_download_action_calls_main(self, monkeypatch):
        client = _patch_run_setup(
            monkeypatch,
            ["Download"],
            ["https://books.yandex.ru/book/ABC, https://books.yandex.ru/book/DEF"],
        )
        main_mock = MagicMock()
        monkeypatch.setattr(cli, "main", main_mock)
        cli.run()
        main_mock.assert_called_once()
        assert main_mock.call_args.args[0] == [
            "https://books.yandex.ru/book/ABC",
            "https://books.yandex.ru/book/DEF",
        ]
        assert main_mock.call_args.args[1] is client

    def test_keyboard_interrupt_cancelled(self, monkeypatch, caplog):
        class _InterruptQ:
            def select(self, *args, **kwargs):
                raise KeyboardInterrupt

            def text(self, *args, **kwargs):
                raise AssertionError

        monkeypatch.setattr(cli, "questionary", _InterruptQ())
        monkeypatch.setattr(cli, "YandexBookClient", MagicMock())
        with caplog.at_level(logging.INFO, logger="yabk_dump.cli"):
            cli.run()
        assert "Cancelled." in caplog.text
