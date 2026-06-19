"""Shared test fixtures."""

import asyncio
from typing import Any

import pytest
from aiohttp import web

pytest_plugins = ("pytest_homeassistant_custom_component",)


@pytest.fixture
def bark_server_received():
    """Captures the last request received by the test server."""
    return {"requests": []}


@pytest.fixture
async def bark_server(aiohttp_server, bark_server_received, socket_enabled):
    """A mock bark-server that returns configurable responses.

    Defaults to a 200 success. Set ``bark_server_received["status"]`` and
    ``["body"]`` to change behavior, and ``["delay"]`` to simulate slowness.
    Inspect captured requests via ``bark_server_received["requests"]``.
    """

    async def handler(request: web.Request) -> web.Response:
        bark_server_received["method"] = request.method
        bark_server_received["path"] = request.path
        bark_server_received["headers"] = dict(request.headers)
        try:
            bark_server_received["json"] = await request.json()
        except Exception:
            bark_server_received["json"] = None
        bark_server_received["requests"].append(request.path)
        delay = bark_server_received.get("delay", 0)
        if delay:
            await asyncio.sleep(delay)
        status: int = bark_server_received.get("status", 200)
        body: Any = bark_server_received.get(
            "body", {"code": 200, "message": "success", "timestamp": 1700000000}
        )
        return web.json_response(body, status=status)

    app = web.Application()
    app.router.add_post("/{tail:.*}", handler)
    return await aiohttp_server(app)
