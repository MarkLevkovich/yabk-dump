import shutil
import base64
import zipfile
import logging
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET
import requests
from Crypto.Cipher import AES


logger = logging.getLogger(__name__)

SERVICE_DOMAIN = "books.yandex.ru"


def _to_bytes(values: list[int]) -> bytes:
    return bytes(values)


class FileManager:
    def __init__(self, output_dir: str, cookies: dict[str, str]) -> None:
        self._output = Path(output_dir)
        self._cookies = cookies

    @staticmethod
    def _pack_directory(directory: str, archive: zipfile.ZipFile) -> None:
        base = Path(directory)
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

    def fetch_url(self, url: str) -> requests.Response:
        logger.debug("fetching %s", url)
        response = requests.get(url, cookies=self._cookies, timeout=30)
        response.raise_for_status()
        return response

    def write_file(self, content: bytes, name: str) -> None:
        path = self._output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def resolve_path(self, sub: str) -> str:
        return str(self._output / sub)

    def build_epub(self) -> None:
        epub_path = f"{self._output}.epub"
        with zipfile.ZipFile(epub_path, "w", zipfile.ZIP_DEFLATED) as archive:
            self._pack_directory(str(self._output), archive)
        logger.info("ebook saved as %s", epub_path)
        logger.info(
            "We recommend https://calibre-ebook.com/ for book management and conversion"
        )

    def clear_styles(self) -> None:
        for css_file in self._output.rglob("*.css"):
            css_file.write_text("", encoding="utf-8")

    def cleanup(self) -> None:
        shutil.rmtree(str(self._output))


class BookProcessor:
    def __init__(
        self,
        book_id: str,
        file_manager: FileManager,
        encryption_key: Optional[str] = None,
    ) -> None:
        self._book_id = book_id
        self._fm = file_manager
        self._key = (
            encryption_key if encryption_key is not None else self._fetch_secret()
        )

    def _fetch_secret(self) -> str:
        url = f"https://{SERVICE_DOMAIN}/reader/p/api/v5/metadata_secret?lang=ru"
        payload = self._fm.fetch_url(url).json()
        logger.debug("secret payload: %s", str(payload))
        key = payload["secret"]
        logger.debug("key: %s", key)
        return key

    def run(self) -> None:
        payload = self._fetch_metadata()
        manifest = self._decrypt_manifest(payload)
        self._write_manifest(manifest)

    def _fetch_metadata(self) -> dict:
        logger.debug("requesting metadata for %s", self._book_id)
        url = f"https://{SERVICE_DOMAIN}/p/api/v5/books/{self._book_id}/metadata/v4"
        response = self._fm.fetch_url(url)
        logger.debug("metadata chunk: %s ...", response.text[:40])
        return response.json()

    def _decrypt_manifest(self, payload: dict) -> dict:
        result = {}
        for key, val in payload.items():
            if isinstance(val, list):
                result[key] = self._decrypt(_to_bytes(val))
            else:
                result[key] = val
        return result

    def _decrypt(self, data: bytes) -> bytes:
        raw_key = base64.b64decode(self._key)
        iv, ciphertext = data[:16], data[16:]
        plaintext = AES.new(raw_key, AES.MODE_CBC, iv=iv).decrypt(ciphertext)
        return plaintext[: -plaintext[-1]]

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
                response = self._fm.fetch_url(url)
                self._fm.write_file(response.content, f"OEBPS/{file_name}")
            except requests.RequestException:
                logger.warning("failed to fetch '%s'", url)

    def cleanup(self) -> None:
        self._fm.cleanup()

    def build_epub(self) -> None:
        self._fm.build_epub()

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
        fm = FileManager(book_dir, self._cookies)
        return BookProcessor(book_id=book_id, file_manager=fm)
