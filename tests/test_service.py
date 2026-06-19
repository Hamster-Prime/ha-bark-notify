"""Tests for the bark.send service."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bark.bark_api import BarkAuthError, BarkPayload
from custom_components.bark.const import (
    CONF_DEVICE_KEY,
    CONF_NAME,
    CONF_SERVER_URL,
    DATA_CLIENTS,
    DOMAIN,
)
from custom_components.bark.service import SERVICE_SCHEMA, build_payload


def _mock_entry(unique="TESTKEY"):
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_NAME: "iPhone",
            CONF_SERVER_URL: "https://api.day.app",
            CONF_DEVICE_KEY: unique,
        },
        unique_id=unique,
    )


def test_build_payload_basic():
    payload = build_payload({"message": "hi", "title": "t"})
    assert payload.title == "t"
    assert payload.body == "hi"


def test_build_payload_markdown_overrides_message():
    payload = build_payload({"message": "hi", "markdown": "# md"})
    assert payload.body is None
    assert payload.markdown == "# md"


def test_build_payload_all_fields():
    payload = build_payload(
        {
            "message": "b",
            "title": "t",
            "subtitle": "st",
            "markdown": "",
            "level": "critical",
            "volume": 9,
            "badge": 2,
            "call": True,
            "auto_copy": True,
            "copy": "c",
            "sound": "minuet",
            "icon": "https://e/i",
            "image": "https://e/img",
            "group": "g",
            "is_archive": True,
            "ttl": 30,
            "url": "https://e",
            "action": "alert",
            "id": "id1",
            "delete": False,
        }
    )
    assert payload.level == "critical" and payload.volume == 9
    assert payload.call is True
    assert payload.auto_copy is True
    assert payload.is_archive is True


async def _setup_entry(hass: HomeAssistant, enable_custom_integrations):
    entry = _mock_entry()
    entry.add_to_hass(hass)
    with patch(
        "custom_components.bark.config_flow.BarkClient.push",
        new=AsyncMock(return_value=None),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_service_send_calls_client_push(
    hass: HomeAssistant, enable_custom_integrations
):
    entry = await _setup_entry(hass, enable_custom_integrations)
    client = hass.data[DOMAIN][DATA_CLIENTS][entry.entry_id]
    with patch.object(client, "push", new=AsyncMock()) as pushed:
        await hass.services.async_call(
            DOMAIN,
            "send",
            {
                "message": "hello",
                "target_entity": entry.entry_id,
            },
            blocking=True,
        )
    pushed.assert_awaited_once()
    sent_payload: BarkPayload = pushed.await_args.args[0]
    assert sent_payload.body == "hello"


async def test_service_send_propagates_error(
    hass: HomeAssistant, enable_custom_integrations
):
    entry = await _setup_entry(hass, enable_custom_integrations)
    client = hass.data[DOMAIN][DATA_CLIENTS][entry.entry_id]
    with patch.object(
        client, "push", new=AsyncMock(side_effect=BarkAuthError("bad"))
    ):
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                DOMAIN,
                "send",
                {"message": "hello", "target_entity": entry.entry_id},
                blocking=True,
            )
