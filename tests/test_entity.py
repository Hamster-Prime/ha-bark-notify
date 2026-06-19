"""Tests for Bark entities."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
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
    sent_payload = pushed.await_args.args[0]
    assert sent_payload.title == "iPhone"
    assert sent_payload.body == "Home Assistant 测试推送"


async def test_sensors_created_with_unknown_initial_state(
    hass: HomeAssistant, enable_custom_integrations
):
    entry = await _setup(hass, enable_custom_integrations)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    status_id = registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{entry.entry_id}_last_push_status"
    )
    time_id = registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{entry.entry_id}_last_push_time"
    )
    assert status_id is not None
    assert time_id is not None
    assert hass.states.get(status_id).state == "unknown"


async def test_sensor_status_updates_to_success_after_send(
    hass: HomeAssistant, enable_custom_integrations
):
    entry = await _setup(hass, enable_custom_integrations)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    status_id = registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{entry.entry_id}_last_push_status"
    )
    client = hass.data[DOMAIN][DATA_CLIENTS][entry.entry_id]
    with patch.object(client, "push", new=AsyncMock()):
        await hass.services.async_call(
            DOMAIN,
            "send",
            {"message": "x", "target_entity": entry.entry_id},
            blocking=True,
        )
        await hass.async_block_till_done()
    assert hass.states.get(status_id).state == "success"


async def test_sensor_status_updates_to_failed_on_error(
    hass: HomeAssistant, enable_custom_integrations
):
    entry = await _setup(hass, enable_custom_integrations)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    status_id = registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{entry.entry_id}_last_push_status"
    )
    from custom_components.bark.bark_api import BarkAuthError

    client = hass.data[DOMAIN][DATA_CLIENTS][entry.entry_id]
    with patch.object(client, "push", new=AsyncMock(side_effect=BarkAuthError("bad"))):
        from homeassistant.exceptions import HomeAssistantError

        try:
            await hass.services.async_call(
                DOMAIN,
                "send",
                {"message": "x", "target_entity": entry.entry_id},
                blocking=True,
            )
        except HomeAssistantError:
            pass
        await hass.async_block_till_done()
    assert hass.states.get(status_id).state == "failed"
