"""Tests for Bark entities."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bark.const import (
    CONF_DEVICE_KEY,
    CONF_NAME,
    CONF_SERVER_URL,
    DATA_CLIENTS,
    DOMAIN,
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


async def _setup(hass: HomeAssistant, enable_custom_integrations):
    entry = _mock_entry()
    entry.add_to_hass(hass)
    with patch(
        "custom_components.bark.config_flow.BarkClient.push",
        new=AsyncMock(return_value=None),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_test_push_button_created_and_presses(
    hass: HomeAssistant, enable_custom_integrations
):
    entry = await _setup(hass, enable_custom_integrations)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    ent_id = registry.async_get_entity_id(
        BUTTON_DOMAIN, DOMAIN, f"{entry.entry_id}_test_push"
    )
    assert ent_id is not None

    client = hass.data[DOMAIN][DATA_CLIENTS][entry.entry_id]
    with patch.object(client, "push", new=AsyncMock()) as pushed:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            "press",
            {"entity_id": ent_id},
            blocking=True,
        )
        await hass.async_block_till_done()
    pushed.assert_awaited_once()
