"""Shared entity base for HomePod Indoor Climate."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .runtime import HomePodIndoorClimateRuntime


class HomePodIndoorClimateEntity(Entity):
    """Base entity backed by the bridge runtime."""

    _attr_has_entity_name = True

    def __init__(self, runtime: HomePodIndoorClimateRuntime, key: str) -> None:
        self.runtime = runtime
        self._attr_unique_id = f"{runtime.entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, runtime.entry.entry_id)},
            name="HomePod Indoor Climate",
            manufacturer="Home Assistant Community",
            model="Authenticated Apple Home bridge",
            configuration_url="https://github.com/chrisj500/HA-HomePod-indoor-climate",
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to runtime updates."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.runtime.signal, self.async_write_ha_state
            )
        )
