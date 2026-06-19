"""Bark API client and data types."""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7


@dataclass
class BarkPayload:
    """Bark push payload (internal snake_case names)."""

    title: str | None = None
    subtitle: str | None = None
    body: str | None = None
    markdown: str | None = None
    level: str | None = None
    volume: int | None = None
    badge: int | None = None
    call: bool | None = None
    auto_copy: bool | None = None
    copy: str | None = None
    sound: str | None = None
    icon: str | None = None
    image: str | None = None
    group: str | None = None
    is_archive: bool | None = None
    ttl: int | None = None
    url: str | None = None
    action: str | None = None
    id: str | None = None
    delete: bool | None = None

    def to_bark_dict(self) -> dict[str, Any]:
        """Convert to Bark wire-format dict (camelCase, bools as '1')."""
        data: dict[str, Any] = {}
        if self.markdown:
            data["markdown"] = self.markdown
        elif self.body is not None:
            data["body"] = self.body
        if self.title is not None:
            data["title"] = self.title
        if self.subtitle is not None:
            data["subtitle"] = self.subtitle
        if self.level is not None:
            data["level"] = self.level
            if self.level == "critical" and self.volume is not None:
                data["volume"] = self.volume
        if self.badge is not None:
            data["badge"] = self.badge
        if self.call:
            data["call"] = "1"
        if self.auto_copy:
            data["autoCopy"] = "1"
        if self.copy is not None:
            data["copy"] = self.copy
        if self.sound is not None:
            data["sound"] = self.sound
        if self.icon is not None:
            data["icon"] = self.icon
        if self.image is not None:
            data["image"] = self.image
        if self.group is not None:
            data["group"] = self.group
        if self.is_archive:
            data["isArchive"] = "1"
        if self.ttl is not None:
            data["ttl"] = self.ttl
        if self.url is not None:
            data["url"] = self.url
        if self.action is not None:
            data["action"] = self.action
        if self.id is not None:
            data["id"] = self.id
        if self.delete:
            data["delete"] = "1"
        return data


class BarkError(Exception):
    """Base class for Bark errors."""


class BarkConnectionError(BarkError):
    """Network / DNS / timeout / unreachable server."""


class BarkAuthError(BarkError):
    """HTTP 400/401 — typically a bad device key."""


class BarkRateLimitError(BarkError):
    """HTTP 429 — rate limited / banned by server."""


class BarkServerError(BarkError):
    """HTTP 5xx — server-side error."""


class BarkPushError(BarkError):
    """Other non-200 responses. Carries the server code and message."""

    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"Bark push failed ({code}): {message}")


class BarkEncryptionError(BarkError):
    """Invalid encryption parameters."""


class EncryptionAlgorithm(str, Enum):
    NONE = "none"
    AES_128_CBC = "aes-128-cbc"


def encrypt_payload(
    payload_json: str,
    key: str,
    iv: bytes | None = None,
) -> tuple[str, str]:
    """Encrypt payload_json with AES-128-CBC.

    Args:
        payload_json: plaintext JSON string to encrypt.
        key: 16-character ASCII key (AES-128).
        iv: optional fixed IV (for testing interop). Random if omitted.

    Returns:
        Tuple of (ciphertext_b64, iv_b64).
    """
    if len(key) != 16:
        raise BarkEncryptionError("encryption key must be exactly 16 characters")
    key_bytes = key.encode("utf-8")
    if iv is None:
        iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(key_bytes), modes.CBC(iv))
    encryptor = cipher.encryptor()
    padder = PKCS7(algorithms.AES.block_size).padder()
    padded = padder.update(payload_json.encode("utf-8")) + padder.finalize()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return (
        base64.b64encode(ciphertext).decode(),
        base64.b64encode(iv).decode(),
    )
