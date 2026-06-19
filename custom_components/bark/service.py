"""The bark.send service."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er

from .bark_api import BarkError, BarkPayload
from .const import (
    DATA_CLIENTS,
    DATA_RUNTIME,
    DOMAIN,
    EVENT_PUSH_UPDATE,
    RUNTIME_STATUS,
    RUNTIME_TIME,
    STATUS_FAILED,
    STATUS_SUCCESS,
)
from .entity import redact_key

_LOGGER = logging.getLogger(__name__)

FIELD_MESSAGE = "message"

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_MESSAGE): cv.string,
        vol.Optional("title"): cv.string,
        vol.Optional("subtitle"): cv.string,
        vol.Optional("markdown"): cv.string,
        vol.Optional("level"): vol.In(
            ["critical", "active", "timeSensitive", "passive"]
        ),
        vol.Optional("volume"): vol.All(vol.Coerce(int), vol.Range(min=0, max=10)),
        vol.Optional("badge"): vol.Coerce(int),
        vol.Optional("call"): cv.boolean,
        vol.Optional("auto_copy"): cv.boolean,
        vol.Optional("copy"): cv.string,
        vol.Optional("sound"): cv.string,
        vol.Optional("icon"): cv.string,
        vol.Optional("image"): cv.string,
        vol.Optional("group"): cv.string,
        vol.Optional("is_archive"): cv.boolean,
        vol.Optional("ttl"): vol.Coerce(int),
        vol.Optional("url"): cv.string,
        vol.Optional("action"): vol.In(["alert"]),
        vol.Optional("id"): cv.string,
        vol.Optional("delete"): cv.boolean,
        vol.Optional("target_entity"): cv.string,
        **cv.ENTITY_SERVICE_FIELDS,
    },
    extra=vol.ALLOW_EXTRA,
)


def build_payload(data: dict[str, Any]) -> BarkPayload:
    """Build a BarkPayload from service data."""
    markdown = data.get("markdown") or None
    return BarkPayload(
        body=None if markdown else data.get(FIELD_MESSAGE),
        title=data.get("title"),
        subtitle=data.get("subtitle"),
        markdown=markdown,
        level=data.get("level"),
        volume=data.get("volume"),
        badge=data.get("badge"),
        call=data.get("call"),
        auto_copy=data.get("auto_copy"),
        copy=data.get("copy"),
        sound=data.get("sound"),
        icon=data.get("icon"),
        image=data.get("image"),
        group=data.get("group"),
        is_archive=data.get("is_archive"),
        ttl=data.get("ttl"),
        url=data.get("url"),
        action=data.get("action"),
        id=data.get("id"),
        delete=data.get("delete"),
    )


def _resolve_entry_ids(hass: HomeAssistant, data: dict[str, Any]) -> list[str]:
    """Resolve service target to config entry ids."""
    entry_ids: list[str] = []

    target = data.get("target_entity")
    if target and target in hass.data[DOMAIN][DATA_CLIENTS]:
        entry_ids.append(target)

    registry = er.async_get(hass)
    entity_ids: list[str] = list(data.get(ATTR_ENTITY_ID) or [])
    for eid in entity_ids:
        ent = registry.async_get(eid)
        if ent and ent.config_entry_id in hass.data[DOMAIN][DATA_CLIENTS]:
            entry_ids.append(ent.config_entry_id)

    device_ids = data.get(ATTR_DEVICE_ID) or []
    if device_ids:
        from homeassistant.helpers import device_registry as dr

        dreg = dr.async_get(hass)
        for did in device_ids:
            dev = dreg.devices.get(did)
            if not dev:
                continue
            for ceid in dev.config_entries:
                if ceid in hass.data[DOMAIN][DATA_CLIENTS]:
                    entry_ids.append(ceid)

    seen: set[str] = set()
    unique: list[str] = []
    for eid in entry_ids:
        if eid not in seen:
            seen.add(eid)
            unique.append(eid)
    return unique


async def do_push(hass: HomeAssistant, entry_id: str, payload: BarkPayload) -> None:
    """Execute a push for one entry and update runtime state."""
    client = hass.data[DOMAIN][DATA_CLIENTS][entry_id]
    runtime = hass.data[DOMAIN][DATA_RUNTIME][entry_id]
    now = datetime.now(timezone.utc).isoformat()
    try:
        await client.push(payload)
    except BarkError as err:
        runtime[RUNTIME_STATUS] = STATUS_FAILED
        runtime[RUNTIME_TIME] = now
        hass.bus.async_fire(
            EVENT_PUSH_UPDATE,
            {DOMAIN: {entry_id: {RUNTIME_STATUS: STATUS_FAILED, RUNTIME_TIME: now}}},
        )
        _LOGGER.debug(
            "bark push failed for entry %s (key=%s): %s",
            entry_id,
            redact_key(hass.data[DOMAIN][DATA_CLIENTS][entry_id]._device_key),
            err,
        )
        raise HomeAssistantError(f"Bark 推送失败: {err}") from err
    runtime[RUNTIME_STATUS] = STATUS_SUCCESS
    runtime[RUNTIME_TIME] = now
    hass.bus.async_fire(
        EVENT_PUSH_UPDATE,
        {DOMAIN: {entry_id: {RUNTIME_STATUS: STATUS_SUCCESS, RUNTIME_TIME: now}}},
    )


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register bark.send (idempotent)."""
    if hass.services.has_service(DOMAIN, "send"):
        return

    async def handle_send(call: ServiceCall) -> None:
        data = dict(call.data)
        entry_ids = _resolve_entry_ids(hass, data)
        if not entry_ids:
            raise HomeAssistantError(
                "bark.send 需要指定目标 Bark 设备（target_entity / entity_id / device_id）"
            )
        payload = build_payload(data)
        for entry_id in entry_ids:
            await do_push(hass, entry_id, payload)

    hass.services.async_register(
        DOMAIN, "send", handle_send, schema=SERVICE_SCHEMA, supports_response=False
    )
