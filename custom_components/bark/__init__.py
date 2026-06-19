"""The Bark integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .bark_api import BarkClient
from .const import (
    CONF_DEVICE_KEY,
    CONF_ENCRYPTION,
    CONF_ENCRYPTION_KEY,
    CONF_SERVER_URL,
    DATA_CLIENTS,
    DATA_RUNTIME,
    DOMAIN,
    PLATFORMS,
    RUNTIME_STATUS,
    RUNTIME_TIME,
    STATUS_UNKNOWN,
)
from .service import async_setup_services

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Bark config entry."""
    client = BarkClient(
        server_url=entry.data[CONF_SERVER_URL],
        device_key=entry.data[CONF_DEVICE_KEY],
        encryption=entry.data.get(CONF_ENCRYPTION, "none"),
        encryption_key=entry.data.get(CONF_ENCRYPTION_KEY),
        session=async_get_clientsession(hass),
    )
    domain_data = hass.data.setdefault(DOMAIN, {})
    clients = domain_data.setdefault(DATA_CLIENTS, {})
    clients[entry.entry_id] = client
    domain_data.setdefault(DATA_RUNTIME, {})[entry.entry_id] = {
        RUNTIME_STATUS: STATUS_UNKNOWN,
        RUNTIME_TIME: None,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await async_setup_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Bark config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    clients = hass.data.get(DOMAIN, {}).get(DATA_CLIENTS, {})
    client: BarkClient | None = clients.pop(entry.entry_id, None)
    if client is not None:
        await client.async_close()
    runtime = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME, {})
    runtime.pop(entry.entry_id, None)
    return unload_ok
