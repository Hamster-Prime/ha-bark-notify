"""Tests for BarkClient."""

import base64
import json

import aiohttp
import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

from custom_components.bark.bark_api import (
    BarkAuthError,
    BarkClient,
    BarkConnectionError,
    BarkPayload,
    BarkPushError,
    BarkRateLimitError,
    BarkResponse,
    BarkServerError,
)


@pytest.fixture
async def client_to(bark_server):
    """Return a factory creating a BarkClient pointed at the test server."""
    def _make(**kwargs):
        defaults = {
            "server_url": str(bark_server.make_url("")),
            "device_key": "TESTKEY",
        }
        defaults.update(kwargs)
        return BarkClient(**defaults)
    return _make


async def test_push_success_returns_response(client_to, bark_server_received):
    async with aiohttp.ClientSession() as session:
        client = client_to(session=session)
        resp = await client.push(BarkPayload(body="hello"))
    assert isinstance(resp, BarkResponse)
    assert resp.code == 200
    assert resp.message == "success"
    assert resp.timestamp == 1700000000


async def test_push_posts_json_to_device_key_path(client_to, bark_server_received):
    async with aiohttp.ClientSession() as session:
        client = client_to(session=session)
        await client.push(BarkPayload(body="hello", title="t"))
    assert bark_server_received["method"] == "POST"
    assert bark_server_received["path"] == "/TESTKEY"
    assert bark_server_received["headers"]["Content-Type"] == "application/json"
    assert bark_server_received["json"] == {"body": "hello", "title": "t"}


async def test_push_400_raises_auth_error(client_to, bark_server_received):
    bark_server_received["status"] = 400
    bark_server_received["body"] = {"code": 400, "message": "bad key"}
    async with aiohttp.ClientSession() as session:
        client = client_to(session=session)
        with pytest.raises(BarkAuthError):
            await client.push(BarkPayload(body="x"))


async def test_push_401_raises_auth_error(client_to, bark_server_received):
    bark_server_received["status"] = 401
    bark_server_received["body"] = {"code": 401, "message": "unauthorized"}
    async with aiohttp.ClientSession() as session:
        client = client_to(session=session)
        with pytest.raises(BarkAuthError):
            await client.push(BarkPayload(body="x"))


async def test_push_429_raises_rate_limit_error(client_to, bark_server_received):
    bark_server_received["status"] = 429
    bark_server_received["body"] = {"code": 429, "message": "rate limited"}
    async with aiohttp.ClientSession() as session:
        client = client_to(session=session)
        with pytest.raises(BarkRateLimitError):
            await client.push(BarkPayload(body="x"))


async def test_push_500_raises_server_error(client_to, bark_server_received):
    bark_server_received["status"] = 500
    bark_server_received["body"] = {"code": 500, "message": "boom"}
    async with aiohttp.ClientSession() as session:
        client = client_to(session=session)
        with pytest.raises(BarkServerError):
            await client.push(BarkPayload(body="x"))


async def test_push_other_non_200_raises_push_error(client_to, bark_server_received):
    bark_server_received["status"] = 404
    bark_server_received["body"] = {"code": 404, "message": "not found"}
    async with aiohttp.ClientSession() as session:
        client = client_to(session=session)
        with pytest.raises(BarkPushError) as exc_info:
            await client.push(BarkPayload(body="x"))
        assert exc_info.value.code == 404


async def test_push_timeout_raises_connection_error(client_to, bark_server_received):
    bark_server_received["delay"] = 5
    async with aiohttp.ClientSession() as session:
        client = client_to(session=session, timeout=1)
        with pytest.raises(BarkConnectionError):
            await client.push(BarkPayload(body="x"))


ENC_KEY = "1234567890123456"


async def test_encrypted_push_sends_ciphertext_only(client_to, bark_server_received):
    async with aiohttp.ClientSession() as session:
        client = client_to(
            session=session, encryption="aes-128-cbc", encryption_key=ENC_KEY
        )
        await client.push(BarkPayload(body="secret", title="t"))
    sent = bark_server_received["json"]
    assert set(sent.keys()) == {"ciphertext", "iv"}
    # no plaintext fields leak
    assert "body" not in sent and "title" not in sent


async def test_encrypted_push_roundtrip_decrypts(client_to, bark_server_received):
    async with aiohttp.ClientSession() as session:
        client = client_to(
            session=session, encryption="aes-128-cbc", encryption_key=ENC_KEY
        )
        await client.push(BarkPayload(body="secret", title="t"))
    sent = bark_server_received["json"]
    # Bark wire format: iv is a raw 16-char ASCII string, not base64.
    assert len(sent["iv"]) == 16
    iv_bytes = sent["iv"].encode("utf-8")
    cipher = Cipher(algorithms.AES(ENC_KEY.encode("utf-8")), modes.CBC(iv_bytes))
    decryptor = cipher.decryptor()
    padded = decryptor.update(base64.b64decode(sent["ciphertext"])) + decryptor.finalize()
    unpadder = PKCS7(128).unpadder()
    plaintext = unpadder.update(padded) + unpadder.finalize()
    decoded = json.loads(plaintext.decode("utf-8"))
    assert decoded == {"body": "secret", "title": "t"}


async def test_encrypted_push_uses_random_iv(client_to, bark_server_received):
    async with aiohttp.ClientSession() as session:
        client = client_to(
            session=session, encryption="aes-128-cbc", encryption_key=ENC_KEY
        )
        await client.push(BarkPayload(body="a"))
        first_iv = bark_server_received["json"]["iv"]
        await client.push(BarkPayload(body="a"))
        second_iv = bark_server_received["json"]["iv"]
    assert first_iv != second_iv


async def test_no_encryption_when_disabled(client_to, bark_server_received):
    async with aiohttp.ClientSession() as session:
        client = client_to(session=session)  # encryption defaults to "none"
        await client.push(BarkPayload(body="plain"))
    sent = bark_server_received["json"]
    assert "ciphertext" not in sent and "iv" not in sent
    assert sent == {"body": "plain"}
