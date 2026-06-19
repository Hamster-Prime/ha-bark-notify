"""Bark API client and data types."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any

import aiohttp
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
    key_bytes = key.encode("utf-8")
    if len(key_bytes) != 16:
        raise BarkEncryptionError("encryption key must encode to exactly 16 bytes (AES-128)")
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


@dataclass
class BarkResponse:
    """Bark server response."""

    code: int
    message: str
    timestamp: int | None = None


class BarkClient:
    """Async Bark push client."""

    def __init__(
        self,
        server_url: str,
        device_key: str,
        encryption: str = "none",
        encryption_key: str | None = None,
        session: aiohttp.ClientSession | None = None,
        timeout: int = 10,
    ) -> None:
        self._server_url = server_url.rstrip("/")
        self._device_key = device_key
        self._encryption = encryption
        self._encryption_key = encryption_key
        self._timeout = timeout
        self._session = session
        self._owns_session = session is None

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def async_close(self) -> None:
        if self._session is not None and self._owns_session:
            await self._session.close()
            self._session = None

    async def push(self, payload: BarkPayload) -> BarkResponse:
        body = payload.to_bark_dict()
        if self._encryption == EncryptionAlgorithm.AES_128_CBC.value:
            payload_json = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
            ciphertext, iv = encrypt_payload(payload_json, self._encryption_key or "")
            body = {"ciphertext": ciphertext, "iv": iv}
        url = f"{self._server_url}/{self._device_key}"
        session = self._get_session()
        try:
            async with session.post(
                url,
                json=body,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=self._timeout),
            ) as resp:
                text = await resp.text()
        except aiohttp.ClientError as err:
            raise BarkConnectionError(f"failed to reach bark server: {err}") from err
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = {}
        code = int(data.get("code", resp.status))
        message = data.get("message", "")
        timestamp = data.get("timestamp")
        if resp.status == 200 and code == 200:
            return BarkResponse(code=code, message=message, timestamp=timestamp)
        raise BarkPushError(code, message or text)
