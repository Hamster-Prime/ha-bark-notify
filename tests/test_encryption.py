"""Tests for Bark AES-128-CBC encryption."""

import base64

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

from custom_components.bark.bark_api import (
    BarkEncryptionError,
    encrypt_payload,
)

DOC_KEY = "1234567890123456"
DOC_IV = "1234567890123456"
DOC_PLAINTEXT = '{"body": "test", "sound": "birdsong"}'
DOC_EXPECTED_CIPHERTEXT = "+aPt5cwN9GbTLLSFri60l3h1X00u/9j1FENfWiTxhNHVLGU+XoJ15JJG5W/d/yf0"


def test_encryption_matches_bark_doc_example():
    """Hard constraint: our crypto must interoperate with Bark/openssl."""
    ciphertext, iv = encrypt_payload(DOC_PLAINTEXT, DOC_KEY, iv=DOC_IV.encode("utf-8"))
    assert ciphertext == DOC_EXPECTED_CIPHERTEXT
    assert iv == base64.b64encode(DOC_IV.encode("utf-8")).decode()


def test_random_iv_each_push():
    ct1, iv1 = encrypt_payload(DOC_PLAINTEXT, DOC_KEY)
    ct2, iv2 = encrypt_payload(DOC_PLAINTEXT, DOC_KEY)
    assert iv1 != iv2
    assert ct1 != ct2


def test_roundtrip_decrypt():
    ciphertext, iv = encrypt_payload(DOC_PLAINTEXT, DOC_KEY, iv=DOC_IV.encode("utf-8"))
    key_bytes = DOC_KEY.encode("utf-8")
    iv_bytes = base64.b64decode(iv)
    cipher = Cipher(algorithms.AES(key_bytes), modes.CBC(iv_bytes))
    decryptor = cipher.decryptor()
    padded = decryptor.update(base64.b64decode(ciphertext)) + decryptor.finalize()
    unpadder = PKCS7(128).unpadder()
    plaintext = unpadder.update(padded) + unpadder.finalize()
    assert plaintext.decode("utf-8") == DOC_PLAINTEXT


def test_invalid_key_length_raises():
    try:
        encrypt_payload(DOC_PLAINTEXT, "too-short")
    except BarkEncryptionError:
        return
    raise AssertionError("expected BarkEncryptionError for short key")
