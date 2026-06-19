"""Tests for Bark integration setup."""

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bark import async_unload_entry
from custom_components.bark.bark_api import BarkClient
from custom_components.bark.const import (
    CONF_DEVICE_KEY,
    CONF_NAME,
    CONF_SERVER_URL,
    DATA_CLIENTS,
    DATA_RUNTIME,
    DOMAIN,
    RUNTIME_STATUS,
    RUNTIME_TIME,
    STATUS_UNKNOWN,
)


def _mock_entry():
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_NAME: "iPhone",
            CONF_SERVER_URL: "https://api.day.app",
            CONF_DEVICE_KEY: "TESTKEY",
        },
        unique_id="TESTKEY",
    )


async def test_setup_entry_creates_client_and_runtime(
    hass: HomeAssistant, enable_custom_integrations
):
    entry = _mock_entry()
    entry.add_to_hass(hass)
    with patch(
        "custom_components.bark.config_flow.BarkClient.push",
        new=AsyncMock(return_value=None),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert DOMAIN in hass.data
    assert entry.entry_id in hass.data[DOMAIN][DATA_CLIENTS]
    assert isinstance(
        hass.data[DOMAIN][DATA_CLIENTS][entry.entry_id], BarkClient
    )
    runtime = hass.data[DOMAIN][DATA_RUNTIME][entry.entry_id]
    assert runtime[RUNTIME_STATUS] == STATUS_UNKNOWN
    assert runtime[RUNTIME_TIME] is None


async def test_unload_entry_closes_client(
    hass: HomeAssistant, enable_custom_integrations
):
    entry = _mock_entry()
    entry.add_to_hass(hass)
    with patch(
        "custom_components.bark.config_flow.BarkClient.push",
        new=AsyncMock(return_value=None),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    client = hass.data[DOMAIN][DATA_CLIENTS][entry.entry_id]
    with patch.object(client, "async_close", new=AsyncMock()) as closed:
        ok = await async_unload_entry(hass, entry)
        await hass.async_block_till_done()
    assert ok
    closed.assert_awaited_once()
    assert entry.entry_id not in hass.data[DOMAIN][DATA_CLIENTS]
    assert entry.entry_id not in hass.data[DOMAIN][DATA_RUNTIME]
