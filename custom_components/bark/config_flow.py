"""Config flow for the Bark integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from voluptuous import UNDEFINED
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .bark_api import (
    BarkClient,
    BarkEncryptionError,
    BarkError,
    BarkPayload,
    EncryptionAlgorithm,
)
from .const import (
    CONF_DEVICE_KEY,
    CONF_ENCRYPTION,
    CONF_ENCRYPTION_KEY,
    CONF_SERVER_URL,
    DEFAULT_SERVER_URL,
    DOMAIN,
    ENCRYPTION_AES_128_CBC,
    ENCRYPTION_NONE,
)

_ENCRYPTION_OPTIONS = {
    ENCRYPTION_NONE: "Off",
    ENCRYPTION_AES_128_CBC: "AES-128-CBC",
}


def _user_schema(user_input: dict[str, Any] | None = None) -> vol.Schema:
    user_input = user_input or {}
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=user_input.get(CONF_NAME)): str,
            vol.Required(
                CONF_SERVER_URL, default=user_input.get(CONF_SERVER_URL, DEFAULT_SERVER_URL)
            ): str,
            vol.Required(CONF_DEVICE_KEY, default=user_input.get(CONF_DEVICE_KEY)): str,
            vol.Required(
                CONF_ENCRYPTION, default=user_input.get(CONF_ENCRYPTION, ENCRYPTION_NONE)
            ): vol.In(_ENCRYPTION_OPTIONS),
            vol.Optional(
                CONF_ENCRYPTION_KEY, default=user_input.get(CONF_ENCRYPTION_KEY, UNDEFINED)
            ): str,
        }
    )


def _validate_encryption_key(user_input: dict[str, Any]) -> str | None:
    if user_input[CONF_ENCRYPTION] == ENCRYPTION_AES_128_CBC:
        key = user_input.get(CONF_ENCRYPTION_KEY) or ""
        if len(key) != 16:
            return "invalid_encryption_key"
    return None


async def _send_test_push(hass: HomeAssistant, user_input: dict[str, Any]) -> None:
    client = BarkClient(
        server_url=user_input[CONF_SERVER_URL],
        device_key=user_input[CONF_DEVICE_KEY],
        encryption=user_input[CONF_ENCRYPTION],
        encryption_key=user_input.get(CONF_ENCRYPTION_KEY),
        session=async_get_clientsession(hass),
    )
    try:
        await client.push(BarkPayload(title=user_input[CONF_NAME], body="Bark 已接入 Home Assistant"))
    finally:
        await client.async_close()


class BarkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Bark config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            err = _validate_encryption_key(user_input)
            if err is None:
                try:
                    await _send_test_push(self.hass, user_input)
                except BarkEncryptionError:
                    err = "invalid_encryption_key"
                except BarkError:
                    err = "test_push_failed"
            if err is None:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )
            errors["base"] = err
        return self.async_show_form(
            step_id="user", data_schema=_user_schema(user_input), errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Reconfigure an existing entry."""
        return await self.async_step_reconfigure_confirm(user_input)

    async def async_step_reconfigure_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            err = _validate_encryption_key(user_input)
            if err is None:
                try:
                    await _send_test_push(self.hass, user_input)
                except BarkEncryptionError:
                    err = "invalid_encryption_key"
                except BarkError:
                    err = "test_push_failed"
            if err is None:
                self.hass.config_entries.async_update_entry(
                    entry, data=user_input, title=user_input[CONF_NAME]
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reconfigure_successful")
            errors["base"] = err

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_user_schema(dict(entry.data)),
            errors=errors,
            description_placeholders={"name": entry.data.get(CONF_NAME, "")},
            last_step=True,
        )
