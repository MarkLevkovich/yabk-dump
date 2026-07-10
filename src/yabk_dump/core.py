import shutil
import base64
import zipfile
import logging
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET
import httpx
from Crypto.Cipher import AES


logger = logging.getLogger(__name__)

SERVICE_DOMAIN = "books.yandex.ru"


class UnauthorizedError(Exception):
    pass


class AESDecryptor:
    def __init__(self, key: bytes) -> None:
        self._key = key

    @classmethod
    def from_base64(cls, encoded: str) -> "AESDecryptor":
        return cls(base64.b64decode(encoded))

    def decrypt(self, data: bytes) -> bytes:
        iv, ciphertext = data[:16], data[16:]
        plaintext = AES.new(self._key, AES.MODE_CBC, iv=iv).decrypt(ciphertext)
        return plaintext[: -plaintext[-1]]

    def decrypt_manifest(self, payload: dict) -> dict:
        result = {}
        for key, val in payload.items():
            if isinstance(val, list):
                result[key] = self.decrypt(bytes(val))
            else:
                result[key] = val
        return result


class YandexBooksAPI:
    def __init__(self, cookies: dict[str, str]) -> None:
        self._cookies = cookies

    def fetch_json(self, url: str) -> dict:
        logger.debug("fetching %s", url)
        response = httpx.get(url, cookies=self._cookies, timeout=30)
        self._raise_if_unauthorized(response)
        response.raise_for_status()
        return response.json()

    def fetch_bytes(self, url: str) -> bytes:
        logger.debug("fetching %s", url)
        response = httpx.get(url, cookies=self._cookies, timeout=30)
        self._raise_if_unauthorized(response)
        response.raise_for_status()
        return response.content

    @staticmethod
    def _raise_if_unauthorized(response: httpx.Response) -> None:
        if response.status_code == 401:
            raise UnauthorizedError(
                "Session_id cookie is invalid or expired. "
                "Please refresh it in your browser and try again."
            )


class FileManager:
    def __init__(self, output_dir: str) -> None:
        self._output = Path(output_dir)

    @property
    def output_dir(self) -> Path:
        return self._output

    def write_file(self, content: bytes, name: str) -> None:
        path = self._output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def resolve_path(self, sub: str) -> str:
        return str(self._output / sub)

    def clear_styles(self) -> None:
        for css_file in self._output.rglob("*.css"):
            css_file.write_text("", encoding="utf-8")

    def cleanup(self) -> None:
        shutil.rmtree(str(self._output))


class EpubBuilder:
    @staticmethod
    def build(source_dir: str) -> str:
        source = Path(source_dir)
        epub_path = f"{source}.epub"
        with zipfile.ZipFile(epub_path, "w", zipfile.ZIP_DEFLATED) as archive:
            EpubBuilder._pack_directory(source, archive)
        return epub_path

    @staticmethod
    def _pack_directory(base: Path, archive: zipfile.ZipFile) -> None:
        mimetype_path = base / "mimetype"
        if mimetype_path.is_file():
            archive.write(
                str(mimetype_path),
                "mimetype",
                compress_type=zipfile.ZIP_STORED,
            )
        for entry in sorted(base.rglob("*")):
            if not entry.is_file() or entry == mimetype_path:
                continue
            archive.write(
                str(entry),
                str(entry.relative_to(base)),
                compress_type=zipfile.ZIP_DEFLATED,
            )


class BookProcessor:
    def __init__(
        self,
        book_id: str,
        api: YandexBooksAPI,
        file_manager: FileManager,
        encryption_key: Optional[str] = None,
    ) -> None:
        self._book_id = book_id
        self._api = api
        self._fm = file_manager
        self._decryptor: Optional[AESDecryptor] = (
            AESDecryptor.from_base64(encryption_key)
            if encryption_key is not None
            else None
        )

    def _ensure_decryptor(self) -> AESDecryptor:
        if self._decryptor is None:
            url = f"https://{SERVICE_DOMAIN}/reader/p/api/v5/metadata_secret?lang=ru"
            payload = self._api.fetch_json(url)
            self._decryptor = AESDecryptor.from_base64(payload["secret"])
            logger.debug("decryptor initialized from remote secret")
        return self._decryptor

    def run(self) -> None:
        payload = self._fetch_metadata()
        manifest = self._ensure_decryptor().decrypt_manifest(payload)
        self._write_manifest(manifest)

    def _fetch_metadata(self) -> dict:
        logger.debug("requesting metadata for %s", self._book_id)
        url = f"https://{SERVICE_DOMAIN}/p/api/v5/books/{self._book_id}/metadata/v4"
        meta = self._api.fetch_json(url)
        logger.debug("metadata received for %s", self._book_id)
        return meta

    def _write_manifest(self, manifest: dict) -> None:
        self._fm.write_file(b"application/epub+zip", "mimetype")
        self._fm.write_file(manifest["container"], "META-INF/container.xml")
        self._fm.write_file(manifest["opf"], "OEBPS/content.opf")
        self._download_resources(manifest["document_uuid"])
        self._fm.write_file(manifest["ncx"], "OEBPS/toc.ncx")

    def _download_resources(self, document_id: str) -> None:
        opf_path = self._fm.resolve_path("OEBPS/content.opf")
        for _event, elem in ET.iterparse(opf_path, events=["start"]):
            if not (elem.tag.endswith("}item") and "href" in elem.attrib):
                continue
            file_name = elem.attrib["href"]
            if file_name == "toc.ncx":
                continue
            url = (
                f"https://{SERVICE_DOMAIN}/p/a/4/d/{document_id}"
                f"/contents/OEBPS/{file_name}"
            )
            try:
                content = self._api.fetch_bytes(url)
                self._fm.write_file(content, f"OEBPS/{file_name}")
            except httpx.RequestException:
                logger.warning("failed to fetch '%s'", url)

    def cleanup(self) -> None:
        self._fm.cleanup()

    def build_epub(self) -> None:
        epub_path = EpubBuilder.build(str(self._fm.output_dir))
        logger.info("ebook saved as %s", epub_path)
        logger.info(
            "We recommend https://calibre-ebook.com/ for book management and conversion"
        )

    def clear_styles(self) -> None:
        self._fm.clear_styles()


class BookClient:
    def __init__(self, output_dir: str, cookies: dict[str, str]) -> None:
        self._output = Path(output_dir)
        if not self._output.exists():
            raise FileNotFoundError(f"path {output_dir} does not exist")
        if not cookies:
            raise ValueError("cookies must not be empty")
        self._cookies = cookies

    def get_book(self, book_id: str) -> BookProcessor:
        book_dir = str(self._output / book_id)
        api = YandexBooksAPI(self._cookies)
        fm = FileManager(book_dir)
        return BookProcessor(book_id=book_id, api=api, file_manager=fm)
