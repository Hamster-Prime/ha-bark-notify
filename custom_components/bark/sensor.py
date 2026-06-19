"""Bark sensor platform (diagnostic sensors)."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DATA_RUNTIME, DOMAIN, EVENT_PUSH_UPDATE, RUNTIME_STATUS, RUNTIME_TIME
from .entity import BarkEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Bark sensor platform."""
    async_add_entities(
        [BarkLastPushStatusSensor(entry), BarkLastPushTimeSensor(entry)]
    )


class _BarkSensorBase(BarkEntity, SensorEntity):
    """Base for Bark diagnostic sensors."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: ConfigEntry, suffix: str) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_{suffix}"

    @property
    def _runtime(self) -> dict:
        return self.hass.data[DOMAIN][DATA_RUNTIME][self._entry.entry_id]

    async def async_added_to_hass(self) -> None:
        """Subscribe to push-update events."""
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_PUSH_UPDATE, self._on_push_update)
        )

    @callback
    def _on_push_update(self, event: Event) -> None:
        payload = event.data.get(DOMAIN, {})
        if self._entry.entry_id not in payload:
            return
        self.async_write_ha_state()


class BarkLastPushStatusSensor(_BarkSensorBase):
    """Sensor showing the result of the last push."""

    _attr_icon = "mdi:check-circle-outline"

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry, "last_push_status")
        self._attr_name = "Last push status"

    @property
    def native_value(self) -> str | None:
        return self._runtime.get(RUNTIME_STATUS)


class BarkLastPushTimeSensor(_BarkSensorBase):
    """Sensor showing the timestamp of the last push."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry, "last_push_time")
        self._attr_name = "Last push time"
        self._attr_icon = "mdi:clock-outline"

    @property
    def native_value(self) -> datetime | None:
        value = self._runtime.get(RUNTIME_TIME)
        if value is None:
            return None
        return dt_util.parse_datetime(value)
