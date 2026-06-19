"""Tests for BarkClient."""

import aiohttp
import pytest

from custom_components.bark.bark_api import (
    BarkClient,
    BarkPayload,
    BarkResponse,
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
