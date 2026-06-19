"""Tests for the Bark config flow."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.bark.const import (
    CONF_DEVICE_KEY,
    CONF_ENCRYPTION,
    CONF_ENCRYPTION_KEY,
    CONF_NAME,
    CONF_SERVER_URL,
    DOMAIN,
)

USER_INPUT = {
    CONF_NAME: "My iPhone",
    CONF_SERVER_URL: "https://api.day.app",
    CONF_DEVICE_KEY: "TESTKEY",
    CONF_ENCRYPTION: "none",
}


async def test_user_flow_success(hass: HomeAssistant, enable_custom_integrations):
    with patch(
        "custom_components.bark.config_flow.BarkClient.push",
        new=AsyncMock(return_value=None),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My iPhone"
    assert result["data"] == USER_INPUT


async def test_user_flow_test_push_fails_shows_error(
    hass: HomeAssistant, enable_custom_integrations
):
    from custom_components.bark.bark_api import BarkAuthError

    with patch(
        "custom_components.bark.config_flow.BarkClient.push",
        new=AsyncMock(side_effect=BarkAuthError("bad key")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "test_push_failed"


async def test_user_flow_encryption_key_required_when_enabled(
    hass: HomeAssistant, enable_custom_integrations
):
    with patch(
        "custom_components.bark.config_flow.BarkClient.push",
        new=AsyncMock(return_value=None),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                **USER_INPUT,
                CONF_ENCRYPTION: "aes-128-cbc",
                CONF_ENCRYPTION_KEY: "",
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_encryption_key"


async def test_user_flow_encryption_error_during_push(
    hass: HomeAssistant, enable_custom_integrations
):
    """Encryption key passes local validation but push raises BarkEncryptionError."""
    from custom_components.bark.bark_api import BarkEncryptionError

    with patch(
        "custom_components.bark.config_flow.BarkClient.push",
        new=AsyncMock(side_effect=BarkEncryptionError("crypto failed")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                **USER_INPUT,
                CONF_ENCRYPTION: "aes-128-cbc",
                CONF_ENCRYPTION_KEY: "1234567890123456",
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "invalid_encryption_key"
