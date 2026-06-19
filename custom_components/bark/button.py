"""Bark button platform (test push)."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .bark_api import BarkPayload
from .const import DATA_CLIENTS, DOMAIN
from .entity import BarkEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Bark button platform."""
    async_add_entities([BarkTestPushButton(hass, entry)])


class BarkTestPushButton(BarkEntity, ButtonEntity):
    """Button to send a test push."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(entry)
        self._hass = hass
        self._attr_unique_id = f"{entry.entry_id}_test_push"
        self._attr_name = "Test push"
        self._attr_icon = "mdi:bell"

    async def async_press(self) -> None:
        """Send a test push."""
        from .service import _do_push

        await _do_push(
            self._hass,
            self._entry.entry_id,
            BarkPayload(
                title=self._entry.data.get(CONF_NAME, "Bark"),
                body="Home Assistant 测试推送",
            ),
        )
