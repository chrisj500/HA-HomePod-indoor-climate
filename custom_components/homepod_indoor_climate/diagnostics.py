"""Diagnostics support for HomePod Indoor Climate."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ALLOWED_USER_ID,
    CONF_LOCAL_ONLY,
    CONF_ROOMS,
    CONF_STALE_AFTER,
    CONF_UPDATE_INTERVAL,
    DEFAULT_LOCAL_ONLY,
    DEFAULT_STALE_AFTER,
    DEFAULT_UPDATE_INTERVAL,
)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry without exposing credentials."""
    runtime = entry.runtime_data
    settings = runtime.settings

    return {
        "config": {
            "room_keys": sorted(runtime.room_keys),
            "configured_room_count": len(settings.get(CONF_ROOMS, [])),
            "update_interval_minutes": int(
                settings.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
            ),
            "stale_after_minutes": int(
                settings.get(CONF_STALE_AFTER, DEFAULT_STALE_AFTER)
            ),
            "local_only": bool(settings.get(CONF_LOCAL_ONLY, DEFAULT_LOCAL_ONLY)),
            "allowed_user_restriction_enabled": bool(
                settings.get(CONF_ALLOWED_USER_ID)
            ),
        },
        "runtime": runtime.diagnostics_snapshot(),
        "note": (
            "The integration records requests before bearer-token validation so "
            "missing or invalid Authorization headers are observable without "
            "logging token contents."
        ),
    }
