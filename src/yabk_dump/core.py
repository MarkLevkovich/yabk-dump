import os
import shutil
import array
import base64
import zipfile
import logging
from xml.etree import ElementTree as ET
import requests
from Crypto.Cipher import AES


SERVICE_DOMAIN = "books.yandex.ru"


class FileManager:
    def __init__(self, output_dir, cookies):
        self.output_dir = output_dir
        self.cookies = cookies

    @staticmethod
    def _list_to_bytes(values):
        assert isinstance(values, list)
        return array.array("B", values).tobytes()

    @staticmethod
    def _archive_directory(directory, archive):
        top = directory
        for root, _, files in os.walk(directory):
            for filename in files:
                if filename != "mimetype":
                    continue
                src = os.path.join(root, filename)
                archive.write(
                    filename=src,
                    arcname=os.path.relpath(src, top),
                    compress_type=zipfile.ZIP_STORED,
                )
        for root, _, files in os.walk(directory):
            for filename in files:
                if filename == "mimetype":
                    continue
                src = os.path.join(root, filename)
                archive.write(filename=src, arcname=os.path.relpath(src, top))

    def fetch_url(self, url):
        logging.debug("fetching %s", url)
        response = requests.get(url, cookies=self.cookies, timeout=30)
        logging.debug("status: %s", response)
        assert response.status_code == 200, response.status_code
        return response

    def write_file(self, content, name):
        file_path = os.path.join(self.output_dir, name)
        dir_path = os.path.dirname(file_path)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        with open(file_path, "wb") as f:
            f.write(content)

    def resolve_path(self, sub):
        return os.path.join(self.output_dir, sub)

    def build_epub(self):
        assert os.path.exists(self.output_dir), self.output_dir
        epub_path = self.output_dir + ".epub"
        with zipfile.ZipFile(epub_path, "w", zipfile.ZIP_DEFLATED) as archive:
            self._archive_directory(self.output_dir, archive)
        logging.info("ebook saved as %s", epub_path)
        logging.info(
            "We recommend https://calibre-ebook.com/ for book management and conversion"
        )

    def clear_styles(self):
        for root, _, files in os.walk(self.output_dir, topdown=False):
            for name in files:
                if name.lower().endswith(".css"):
                    with open(os.path.join(root, name), "w", encoding="UTF-8") as f:
                        f.write("")

    def cleanup(self):
        shutil.rmtree(self.output_dir)


class BookProcessor:
    def __init__(self, book_id, file_manager, encryption_key=None):
        self.book_id = book_id
        self.file_manager = file_manager
        self.encryption_key = (
            self.fetch_secret() if encryption_key is None else encryption_key
        )
        assert self.encryption_key is not None

    def fetch_secret(self):
        url = f"https://{SERVICE_DOMAIN}/reader/p/api/v5/metadata_secret?lang=ru"
        secret_response = self.file_manager.fetch_url(url).json()
        logging.debug("secret payload: %s", str(secret_response))
        key_value = secret_response["secret"]
        logging.debug("key: %s", key_value)
        return key_value

    def run(self):
        payload = self.fetch_metadata(self.book_id)
        manifest = self.decipher_metadata(payload, self.encryption_key)
        self.handle_metadata(manifest)

    def fetch_metadata(self, identifier):
        logging.debug("requesting metadata for %s", identifier)
        url = f"https://{SERVICE_DOMAIN}/p/api/v5/books/{identifier}/metadata/v4"
        response = self.file_manager.fetch_url(url)
        logging.debug("metadata chunk: %s ...", response.text[:40])
        return response.json()

    def decipher_metadata(self, payload, encryption_key):
        assert isinstance(payload, dict)
        manifest = {}
        for key, val in payload.items():
            if isinstance(val, list):
                manifest[key] = self.decipher(
                    encryption_key, FileManager._list_to_bytes(val)
                )
            else:
                manifest[key] = val
        return manifest

    def decipher(self, encryption_key, data):
        assert isinstance(encryption_key, str), type(encryption_key)
        decoded = base64.b64decode(encryption_key)
        plaintext = self.aes_decrypt(data[16:], decoded, data[:16])
        logging.debug("plain length: %s", len(plaintext))
        logging.debug("last byte: %s", plaintext[-1])
        pad_length = -1 * plaintext[-1]
        return plaintext[:pad_length]

    def aes_decrypt(self, ciphertext, decoded_key, iv):
        assert isinstance(ciphertext, bytes)
        assert isinstance(decoded_key, bytes)
        assert isinstance(iv, bytes)
        cipher = AES.new(decoded_key, AES.MODE_CBC, iv=iv)
        return cipher.decrypt(ciphertext)

    def handle_metadata(self, manifest):
        self.file_manager.write_file(b"application/epub+zip", "mimetype")
        self.file_manager.write_file(manifest["container"], "META-INF/container.xml")
        self.file_manager.write_file(manifest["opf"], "OEBPS/content.opf")
        self.parse_opf(manifest["document_uuid"])
        self.file_manager.write_file(manifest["ncx"], "OEBPS/toc.ncx")

    def parse_opf(self, document_id):
        opf_path = self.file_manager.resolve_path("OEBPS/content.opf")
        for event, elem in ET.iterparse(opf_path, events=["start"]):
            if event != "start":
                continue
            if not elem.tag.endswith("}item"):
                continue
            if "href" not in elem.attrib:
                continue
            file_name = elem.attrib["href"]
            if file_name == "toc.ncx":
                continue
            logging.debug("resource: %s", file_name)
            url = f"https://{SERVICE_DOMAIN}/p/a/4/d/{document_id}/contents/OEBPS/{file_name}"
            try:
                response = self.file_manager.fetch_url(url)
                self.file_manager.write_file(response.content, "OEBPS/" + file_name)
            except Exception:
                logging.warning("failed to fetch '%s'", url)

    def cleanup(self):
        self.file_manager.cleanup()

    def build_epub(self):
        self.file_manager.build_epub()

    def clear_styles(self):
        self.file_manager.clear_styles()


class BookClient:
    def __init__(self, output_dir, cookies):
        assert os.path.exists(output_dir), f"path {output_dir} does not exist"
        self.output_dir = output_dir
        assert cookies
        self.cookies = cookies

    def get_book(self, book_id):
        path = os.path.join(self.output_dir, book_id)
        file_manager = FileManager(output_dir=path, cookies=self.cookies)
        return BookProcessor(book_id=book_id, file_manager=file_manager)
