import base64
import os

import pytest
from Crypto.Cipher import AES

from yabk_dump import core


def pad_pkcs7(data: bytes) -> bytes:
    pad_len = 16 - (len(data) % 16)
    return data + bytes([pad_len]) * pad_len


def encrypt_bytes(key: bytes, data: bytes) -> bytes:
    iv = os.urandom(16)
    cipher = AES.new(key, AES.MODE_CBC, iv=iv)
    return iv + cipher.encrypt(pad_pkcs7(data))


def manifest_payload(key: bytes, files: dict[str, bytes], document_uuid: str) -> dict:
    payload = {"document_uuid": document_uuid}
    for name, content in files.items():
        payload[name] = list(encrypt_bytes(key, content))
    return payload


def opf_with_items(items: list[str], namespaced: bool = True) -> bytes:
    xmlns = ' xmlns="http://www.idpf.org/2007/opf"' if namespaced else ""
    entries = "".join(f'<item href="{item}"/>' for item in items)
    opf = (
        f'<?xml version="1.0"?><package{xmlns}><manifest>{entries}</manifest></package>'
    )
    return opf.encode()


@pytest.fixture
def aes_key() -> bytes:
    return os.urandom(32)


@pytest.fixture
def aes_key_b64(aes_key: bytes) -> str:
    return base64.b64encode(aes_key).decode()


@pytest.fixture
def mock_tqdm(monkeypatch):
    monkeypatch.setattr(core, "tqdm", lambda iterable, **kwargs: iterable)
