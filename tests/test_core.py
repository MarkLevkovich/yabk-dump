import base64
import logging
import zipfile
from unittest.mock import MagicMock, patch

import httpx
import pytest
from conftest import encrypt_bytes, manifest_payload, opf_with_items

from yabk_dump.core import (
    AESDecryptor,
    BookClient,
    BookProcessor,
    EpubBuilder,
    FileManager,
    YandexBooksAPI,
)
from yabk_dump.exc import InvalidInputError, UnauthorizedError


class TestAESDecryptor:
    def test_from_base64_decodes_key(self, aes_key):
        encoded = base64.b64encode(aes_key).decode()
        decryptor = AESDecryptor.from_base64(encoded)
        assert decryptor._key == aes_key

    def test_decrypt_roundtrip(self, aes_key):
        decryptor = AESDecryptor(aes_key)
        plaintext = b"hello world"
        assert decryptor.decrypt(encrypt_bytes(aes_key, plaintext)) == plaintext

    def test_decrypt_multiblock(self, aes_key):
        decryptor = AESDecryptor(aes_key)
        plaintext = b"A" * 100
        assert decryptor.decrypt(encrypt_bytes(aes_key, plaintext)) == plaintext

    def test_decrypt_strips_pkcs7_padding(self, aes_key):
        plaintext = b"x" * 33
        encrypted = encrypt_bytes(aes_key, plaintext)
        decrypted = AESDecryptor(aes_key).decrypt(encrypted)
        assert len(decrypted) == 33

    def test_decrypt_manifest_decrypts_lists_only(self, aes_key):
        decryptor = AESDecryptor(aes_key)
        secret = b"secret content"
        payload = {
            "container": list(encrypt_bytes(aes_key, secret)),
            "plain_str": "keep",
            "plain_int": 42,
            "nested": {"x": 1},
        }
        result = decryptor.decrypt_manifest(payload)
        assert result["container"] == secret
        assert result["plain_str"] == "keep"
        assert result["plain_int"] == 42
        assert result["nested"] == {"x": 1}

    def test_decrypt_manifest_empty(self, aes_key):
        assert AESDecryptor(aes_key).decrypt_manifest({}) == {}


class TestYandexBooksAPI:
    def _api(self):
        return YandexBooksAPI({"Session_id": "sess"})

    def _response(self, status_code, *, json=None, content=None):
        request = httpx.Request("GET", "https://books.yandex.ru/anything")
        if json is not None:
            return httpx.Response(status_code, json=json, request=request)
        return httpx.Response(status_code, content=content, request=request)

    def test_fetch_json_returns_payload(self):
        url = "https://books.yandex.ru/p/api/v5/books/x/metadata/v4"
        resp = self._response(200, json={"a": 1})
        with patch("yabk_dump.core.httpx.get", return_value=resp) as mock_get:
            result = self._api().fetch_json(url)
        assert result == {"a": 1}
        mock_get.assert_called_once_with(
            url, cookies={"Session_id": "sess"}, timeout=30
        )

    def test_fetch_json_raises_unauthorized_on_401(self):
        url = "https://books.yandex.ru/x"
        resp = self._response(401)
        with (
            patch("yabk_dump.core.httpx.get", return_value=resp),
            pytest.raises(UnauthorizedError),
        ):
            self._api().fetch_json(url)

    def test_fetch_json_raises_http_status_error(self):
        url = "https://books.yandex.ru/x"
        resp = self._response(500)
        with (
            patch("yabk_dump.core.httpx.get", return_value=resp),
            pytest.raises(httpx.HTTPStatusError),
        ):
            self._api().fetch_json(url)

    def test_fetch_bytes_returns_content(self):
        url = "https://books.yandex.ru/p/a/4/d/doc/contents/OEBPS/f.xhtml"
        resp = self._response(200, content=b"file-content")
        with patch("yabk_dump.core.httpx.get", return_value=resp) as mock_get:
            result = self._api().fetch_bytes(url)
        assert result == b"file-content"
        mock_get.assert_called_once_with(
            url, cookies={"Session_id": "sess"}, timeout=30
        )

    def test_fetch_bytes_raises_unauthorized_on_401(self):
        url = "https://books.yandex.ru/x"
        resp = self._response(401)
        with (
            patch("yabk_dump.core.httpx.get", return_value=resp),
            pytest.raises(UnauthorizedError),
        ):
            self._api().fetch_bytes(url)

    def test_fetch_bytes_raises_http_status_error(self):
        url = "https://books.yandex.ru/x"
        resp = self._response(404)
        with (
            patch("yabk_dump.core.httpx.get", return_value=resp),
            pytest.raises(httpx.HTTPStatusError),
        ):
            self._api().fetch_bytes(url)

    def test_raise_if_unauthorized_401(self):
        request = httpx.Request("GET", "https://books.yandex.ru/x")
        with pytest.raises(UnauthorizedError):
            YandexBooksAPI._raise_if_unauthorized(httpx.Response(401, request=request))

    def test_raise_if_unauthorized_ignores_other(self):
        request = httpx.Request("GET", "https://books.yandex.ru/x")
        assert (
            YandexBooksAPI._raise_if_unauthorized(httpx.Response(200, request=request))
            is None
        )


class TestFileManager:
    def test_write_file_creates_nested_dirs(self, tmp_path):
        fm = FileManager(str(tmp_path / "book"))
        fm.write_file(b"content", "OEBPS/chapter1.xhtml")
        assert (tmp_path / "book" / "OEBPS" / "chapter1.xhtml").read_bytes() == (
            b"content"
        )

    def test_output_dir_property(self, tmp_path):
        fm = FileManager(str(tmp_path / "book"))
        assert fm.output_dir == tmp_path / "book"

    def test_resolve_path(self, tmp_path):
        fm = FileManager(str(tmp_path / "book"))
        assert fm.resolve_path("OEBPS/x") == str(tmp_path / "book" / "OEBPS" / "x")

    def test_clear_styles_empties_only_css(self, tmp_path):
        fm = FileManager(str(tmp_path / "book"))
        fm.write_file(b"body{}", "OEBPS/style.css")
        fm.write_file(b"body{}", "OEBPS/sub/nested.css")
        fm.write_file(b"keep", "OEBPS/content.xhtml")
        fm.clear_styles()
        assert (tmp_path / "book" / "OEBPS" / "style.css").read_text() == ""
        assert (tmp_path / "book" / "OEBPS" / "sub" / "nested.css").read_text() == ""
        assert (tmp_path / "book" / "OEBPS" / "content.xhtml").read_bytes() == (b"keep")

    def test_cleanup_removes_output(self, tmp_path):
        fm = FileManager(str(tmp_path / "book"))
        fm.write_file(b"x", "a.txt")
        fm.cleanup()
        assert not (tmp_path / "book").exists()


class TestEpubBuilder:
    def _build_source(self, tmp_path, with_mimetype=True):
        src = tmp_path / "src"
        (src / "META-INF").mkdir(parents=True)
        (src / "OEBPS").mkdir()
        if with_mimetype:
            (src / "mimetype").write_bytes(b"application/epub+zip")
        (src / "META-INF" / "container.xml").write_bytes(b"<container/>")
        (src / "OEBPS" / "content.opf").write_bytes(b"<opf/>")
        return src

    def test_build_creates_valid_zip(self, tmp_path):
        src = self._build_source(tmp_path)
        epub_path = EpubBuilder.build(str(src))
        assert epub_path == f"{src}.epub"
        assert (tmp_path / "src.epub").exists()
        with zipfile.ZipFile(epub_path) as archive:
            names = archive.namelist()
            assert names[0] == "mimetype"
            assert archive.getinfo("mimetype").compress_type == (zipfile.ZIP_STORED)
            for name in names[1:]:
                assert archive.getinfo(name).compress_type == (zipfile.ZIP_DEFLATED)
            assert archive.read("mimetype") == b"application/epub+zip"
            assert archive.read("META-INF/container.xml") == b"<container/>"
            assert archive.read("OEBPS/content.opf") == b"<opf/>"

    def test_build_without_mimetype(self, tmp_path):
        src = self._build_source(tmp_path, with_mimetype=False)
        epub_path = EpubBuilder.build(str(src))
        with zipfile.ZipFile(epub_path) as archive:
            names = archive.namelist()
            assert "mimetype" not in names
            assert all(
                archive.getinfo(name).compress_type == zipfile.ZIP_DEFLATED
                for name in names
            )


class TestBookProcessor:
    def _make_processor(self, api, fm, key_b64=None, book_id="BOOK-1"):
        return BookProcessor(book_id, api, fm, encryption_key=key_b64)

    def _manifest(self, key, document_uuid="doc-1"):
        files = {
            "container": b"<container/>",
            "opf": opf_with_items(["chapter1.xhtml", "toc.ncx"]),
            "ncx": b"<ncx/>",
        }
        return manifest_payload(key, files, document_uuid), files

    def test_run_downloads_and_writes_all_files(
        self, tmp_path, aes_key, aes_key_b64, mock_tqdm
    ):
        payload, files = self._manifest(aes_key)
        api = MagicMock()
        api.fetch_json.return_value = payload
        resources = {"chapter1.xhtml": b"<html/>"}
        api.fetch_bytes.side_effect = lambda url: resources[url.split("/")[-1]]

        fm = FileManager(str(tmp_path / "book"))
        self._make_processor(api, fm, key_b64=aes_key_b64).run()

        out = fm.output_dir
        assert (out / "mimetype").read_bytes() == b"application/epub+zip"
        assert (out / "META-INF" / "container.xml").read_bytes() == files["container"]
        assert (out / "OEBPS" / "content.opf").read_bytes() == files["opf"]
        assert (out / "OEBPS" / "toc.ncx").read_bytes() == files["ncx"]
        assert (out / "OEBPS" / "chapter1.xhtml").read_bytes() == b"<html/>"
        assert api.fetch_json.call_count == 1

    def test_toc_ncx_never_downloaded_as_resource(
        self, tmp_path, aes_key, aes_key_b64, mock_tqdm
    ):
        payload, _ = self._manifest(aes_key)
        api = MagicMock()
        api.fetch_json.return_value = payload
        api.fetch_bytes.return_value = b"x"

        fm = FileManager(str(tmp_path / "book"))
        self._make_processor(api, fm, key_b64=aes_key_b64).run()

        for call in api.fetch_bytes.call_args_list:
            assert "toc.ncx" not in call.args[0]

    def test_ensure_decryptor_fetches_remote_secret(self, aes_key, aes_key_b64):
        api = MagicMock()
        api.fetch_json.return_value = {"secret": aes_key_b64}
        fm = FileManager("/tmp/nowhere")
        processor = self._make_processor(api, fm)

        decryptor = processor._ensure_decryptor()
        assert decryptor.decrypt(encrypt_bytes(aes_key, b"data")) == b"data"
        url = api.fetch_json.call_args.args[0]
        assert "metadata_secret" in url

    def test_ensure_decryptor_caches(self, aes_key, aes_key_b64):
        api = MagicMock()
        api.fetch_json.return_value = {"secret": aes_key_b64}
        fm = FileManager("/tmp/nowhere")
        processor = self._make_processor(api, fm)
        processor._ensure_decryptor()
        processor._ensure_decryptor()
        assert api.fetch_json.call_count == 1

    def test_download_resources_tolerates_http_error(
        self, tmp_path, aes_key, aes_key_b64, mock_tqdm, caplog
    ):
        payload = manifest_payload(
            aes_key,
            {
                "container": b"<container/>",
                "opf": opf_with_items(["bad.xhtml", "good.xhtml"]),
                "ncx": b"<ncx/>",
            },
            "doc-1",
        )
        api = MagicMock()
        api.fetch_json.return_value = payload

        def fake_fetch(url):
            name = url.split("/")[-1]
            if name == "bad.xhtml":
                raise httpx.ConnectError("boom", request=httpx.Request("GET", url))
            return b"good"

        api.fetch_bytes.side_effect = fake_fetch

        fm = FileManager(str(tmp_path / "book"))
        with caplog.at_level(logging.WARNING, logger="yabk_dump.core"):
            self._make_processor(api, fm, key_b64=aes_key_b64).run()

        out = fm.output_dir
        assert (out / "OEBPS" / "good.xhtml").read_bytes() == b"good"
        assert not (out / "OEBPS" / "bad.xhtml").exists()
        assert "failed to fetch" in caplog.text

    def test_download_resources_plain_opf_downloads_items(
        self, tmp_path, aes_key, aes_key_b64, mock_tqdm
    ):
        payload = manifest_payload(
            aes_key,
            {
                "container": b"<container/>",
                "opf": opf_with_items(["chapter1.xhtml"], namespaced=False),
                "ncx": b"<ncx/>",
            },
            "doc-1",
        )
        api = MagicMock()
        api.fetch_json.return_value = payload
        api.fetch_bytes.return_value = b"plain"

        fm = FileManager(str(tmp_path / "book"))
        self._make_processor(api, fm, key_b64=aes_key_b64).run()

        assert (fm.output_dir / "OEBPS" / "chapter1.xhtml").read_bytes() == (b"plain")

    def test_build_epub_creates_file(self, tmp_path, aes_key, aes_key_b64):
        fm = FileManager(str(tmp_path / "book"))
        fm.write_file(b"application/epub+zip", "mimetype")
        api = MagicMock()
        processor = self._make_processor(api, fm, key_b64=aes_key_b64)
        processor.build_epub()
        assert (tmp_path / "book.epub").exists()

    def test_clear_styles_delegates(self, tmp_path, aes_key, aes_key_b64):
        fm = FileManager(str(tmp_path / "book"))
        fm.write_file(b"body{}", "OEBPS/style.css")
        api = MagicMock()
        processor = self._make_processor(api, fm, key_b64=aes_key_b64)
        processor.clear_styles()
        assert (tmp_path / "book" / "OEBPS" / "style.css").read_text() == ""

    def test_cleanup_removes_dir(self, tmp_path, aes_key, aes_key_b64):
        fm = FileManager(str(tmp_path / "book"))
        fm.write_file(b"x", "a.txt")
        api = MagicMock()
        processor = self._make_processor(api, fm, key_b64=aes_key_b64)
        processor.cleanup()
        assert not fm.output_dir.exists()


class TestBookClient:
    def test_missing_output_dir_raises(self, tmp_path):
        with pytest.raises(InvalidInputError, match="does not exist"):
            BookClient(str(tmp_path / "missing"), {"Session_id": "s"})

    def test_empty_cookies_raises(self, tmp_path):
        target = tmp_path / "out"
        target.mkdir()
        with pytest.raises(InvalidInputError, match="cookies"):
            BookClient(str(target), {})

    def test_none_cookies_raises(self, tmp_path):
        target = tmp_path / "out"
        target.mkdir()
        with pytest.raises(InvalidInputError, match="cookies"):
            BookClient(str(target), None)

    def test_get_book_wires_processor(self, tmp_path):
        target = tmp_path / "out"
        target.mkdir()
        client = BookClient(str(target), {"Session_id": "s"})
        processor = client.get_book("BOOK-42")
        assert processor._book_id == "BOOK-42"
        assert processor._fm.output_dir == target / "BOOK-42"
        assert processor._api._cookies == {"Session_id": "s"}
