"""Configuration flow for HomePod Indoor Climate."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    CONF_ALLOWED_USER_ID,
    CONF_LOCAL_ONLY,
    CONF_ROOMS,
    CONF_STALE_AFTER,
    CONF_UPDATE_INTERVAL,
    DEFAULT_LOCAL_ONLY,
    DEFAULT_STALE_AFTER,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)
from .models import parse_rooms


ROOMS_SELECTOR = selector.TextSelector(
    selector.TextSelectorConfig(multiline=True)
)
MINUTES_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=1,
        max=120,
        step=1,
        mode=selector.NumberSelectorMode.BOX,
        unit_of_measurement="minutes",
    )
)


def _schema(
    current: dict[str, Any] | None = None,
    users: list[dict[str, str]] | None = None,
) -> vol.Schema:
    """Build the setup/options schema."""
    current = current or {}
    rooms = current.get(CONF_ROOMS, [])
    room_text = "\n".join(room["name"] for room in rooms)
    allowed_user = current.get(CONF_ALLOWED_USER_ID)

    fields: dict[vol.Marker, Any] = {
        vol.Required(
            CONF_ROOMS,
            default=room_text or "Living Room\nBedroom",
        ): ROOMS_SELECTOR,
        vol.Required(
            CONF_UPDATE_INTERVAL,
            default=int(current.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)),
        ): MINUTES_SELECTOR,
        vol.Required(
            CONF_STALE_AFTER,
            default=int(current.get(CONF_STALE_AFTER, DEFAULT_STALE_AFTER)),
        ): MINUTES_SELECTOR,
        vol.Required(
            CONF_LOCAL_ONLY,
            default=bool(current.get(CONF_LOCAL_ONLY, DEFAULT_LOCAL_ONLY)),
        ): bool,
    }
    user_marker = vol.Optional(CONF_ALLOWED_USER_ID)
    if allowed_user:
        user_marker = vol.Optional(CONF_ALLOWED_USER_ID, default=allowed_user)
    fields[user_marker] = selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=users or [], mode=selector.SelectSelectorMode.DROPDOWN
        )
    )
    return vol.Schema(fields)


def _normalize(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize user input for storage."""
    normalized = dict(user_input)
    normalized[CONF_ROOMS] = parse_rooms(user_input[CONF_ROOMS])
    normalized[CONF_UPDATE_INTERVAL] = int(user_input[CONF_UPDATE_INTERVAL])
    normalized[CONF_STALE_AFTER] = int(user_input[CONF_STALE_AFTER])
    if not normalized.get(CONF_ALLOWED_USER_ID):
        normalized.pop(CONF_ALLOWED_USER_ID, None)
    return normalized


class HomePodIndoorClimateConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle initial configuration."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Configure the bridge."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                data = _normalize(user_input)
            except ValueError:
                errors[CONF_ROOMS] = "invalid_rooms"
            else:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="HomePod Indoor Climate", data=data
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(users=await self._async_user_options()),
            errors=errors,
        )

    async def _async_user_options(self) -> list[dict[str, str]]:
        """Return active, human users for the restriction selector."""
        users = await self.hass.auth.async_get_users()
        return [
            {
                "value": user.id,
                "label": f"{user.name}{' (administrator)' if user.is_admin else ''}",
            }
            for user in users
            if user.is_active and not user.system_generated
        ]

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> HomePodIndoorClimateOptionsFlow:
        """Return the options flow."""
        return HomePodIndoorClimateOptionsFlow(config_entry)


class HomePodIndoorClimateOptionsFlow(config_entries.OptionsFlow):
    """Edit bridge settings."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Edit settings."""
        errors: dict[str, str] = {}
        current = {**self._entry.data, **self._entry.options}
        if user_input is not None:
            try:
                data = _normalize(user_input)
            except ValueError:
                errors[CONF_ROOMS] = "invalid_rooms"
            else:
                return self.async_create_entry(title="", data=data)

        users = await self.hass.auth.async_get_users()
        user_options = [
            {
                "value": user.id,
                "label": f"{user.name}{' (administrator)' if user.is_admin else ''}",
            }
            for user in users
            if user.is_active and not user.system_generated
        ]
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(current, user_options),
            errors=errors,
        )
