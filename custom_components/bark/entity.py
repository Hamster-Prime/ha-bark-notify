"""Bark entities and device binding."""

from __future__ import annotations

import hashlib

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import CONF_DEVICE_KEY, DOMAIN


def _device_ident(device_key: str) -> str:
    """Stable, non-revealing device identifier (SHA-256 truncated)."""
    return hashlib.sha256(device_key.encode("utf-8")).hexdigest()[:16]


def build_device_info(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, _device_ident(entry.data[CONF_DEVICE_KEY]))},
        name=entry.data.get(CONF_NAME, "Bark"),
        manufacturer="Bark",
        model="Bark Device",
        sw_version="1.0.0",
    )


class BarkEntity(Entity):
    """Base entity that binds to a Bark device."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_device_info = build_device_info(entry)
