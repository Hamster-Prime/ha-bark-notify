"""Tests for Bark AES-128-CBC encryption."""

import base64

import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

from custom_components.bark.bark_api import (
    BarkEncryptionError,
    encrypt_payload,
)

# Vectors from the official Bark documentation.
DOC_KEY = "1234567890123456"
DOC_IV = "1234567890123456"
DOC_PLAINTEXT = '{"body": "test", "sound": "birdsong"}'
DOC_EXPECTED_CIPHERTEXT = "+aPt5cwN9GbTLLSFri60l3h1X00u/9j1FENfWiTxhNHVLGU+XoJ15JJG5W/d/yf0"

# Vectors reproduced from a real Bark iOS app's generated encryption script
# (`openssl enc -aes-128-cbc` with ASCII key/iv hex-encoded for openssl).
# These pin the exact wire format the Bark app expects: the IV is transmitted
# as the raw 16-character ASCII string, NOT base64-encoded.
APP_KEY = "czWfhuP3xIu5Zb6R"
APP_IV = "ORv7kkSmTsg6cjfh"
APP_PLAINTEXT = '{"body": "test", "sound": "birdsong"}'
APP_EXPECTED_CIPHERTEXT = "8ODIz/s3e8fOtZvVVpbuwKmggx5ISWbnbZOsilwxQ0PaW8412uNO9kCq3XM9hX+1"


def test_encryption_matches_bark_doc_example():
    """Hard constraint: our crypto must interoperate with Bark/openssl."""
    ciphertext, iv = encrypt_payload(DOC_PLAINTEXT, DOC_KEY, iv=DOC_IV)
    assert ciphertext == DOC_EXPECTED_CIPHERTEXT
    assert iv == DOC_IV  # raw ASCII string, not base64


def test_encryption_matches_real_bark_app_script():
    """Second hard constraint: ciphertext matches a real Bark app's script."""
    ciphertext, iv = encrypt_payload(APP_PLAINTEXT, APP_KEY, iv=APP_IV)
    assert ciphertext == APP_EXPECTED_CIPHERTEXT
    assert iv == APP_IV  # raw ASCII string returned as-is


def test_iv_returned_as_raw_ascii_not_base64():
    """The Bark app decodes `iv` as the literal IV string, so we must transmit
    a 16-character ASCII string. Base64 of 16 bytes is 24 chars and breaks
    decryption (the app uses it directly as IV bytes, wrong length for AES)."""
    _, iv = encrypt_payload(DOC_PLAINTEXT, DOC_KEY)
    assert len(iv) == 16
    assert iv.isascii()
    assert iv.isprintable()
    # Not 24 chars (= base64 of 16 bytes) — that's the bug we fixed.
    assert len(iv) != 24


def test_random_iv_each_push():
    ct1, iv1 = encrypt_payload(DOC_PLAINTEXT, DOC_KEY)
    ct2, iv2 = encrypt_payload(DOC_PLAINTEXT, DOC_KEY)
    assert iv1 != iv2
    assert ct1 != ct2
    assert len(iv1) == 16 and len(iv2) == 16


def test_roundtrip_decrypt():
    ciphertext, iv = encrypt_payload(DOC_PLAINTEXT, DOC_KEY, iv=DOC_IV)
    key_bytes = DOC_KEY.encode("utf-8")
    iv_bytes = iv.encode("utf-8")  # ASCII string -> bytes
    cipher = Cipher(algorithms.AES(key_bytes), modes.CBC(iv_bytes))
    decryptor = cipher.decryptor()
    padded = decryptor.update(base64.b64decode(ciphertext)) + decryptor.finalize()
    unpadder = PKCS7(128).unpadder()
    plaintext = unpadder.update(padded) + unpadder.finalize()
    assert plaintext.decode("utf-8") == DOC_PLAINTEXT


@pytest.mark.parametrize("bad_key", ["too-short", "12345678901234567"])
def test_invalid_key_length_raises(bad_key):
    with pytest.raises(BarkEncryptionError):
        encrypt_payload(DOC_PLAINTEXT, bad_key)
