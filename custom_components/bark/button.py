"""Bark button platform (test push)."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .bark_api import BarkPayload
from .entity import BarkEntity
from .service import do_push


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Bark button platform."""
    async_add_entities([BarkTestPushButton(entry)])


class BarkTestPushButton(BarkEntity, ButtonEntity):
    """Button to send a test push."""

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_test_push"
        self._attr_translation_key = "test_push"
        self._attr_icon = "mdi:bell"

    async def async_press(self) -> None:
        """Send a test push."""
        await do_push(
            self.hass,
            self._entry.entry_id,
            BarkPayload(
                title=self._entry.data.get(CONF_NAME, "Bark"),
                body="Home Assistant 测试推送",
            ),
        )
