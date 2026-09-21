"""HomeKit-visible refresh trigger for HomePod Indoor Climate."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity

from . import HomePodIndoorClimateConfigEntry
from .entity import HomePodIndoorClimateEntity
from .runtime import HomePodIndoorClimateRuntime


async def async_setup_entry(
    _hass, entry: HomePodIndoorClimateConfigEntry, async_add_entities
) -> None:
    """Set up refresh switch."""
    async_add_entities([RefreshSwitch(entry.runtime_data)])


class RefreshSwitch(HomePodIndoorClimateEntity, SwitchEntity):
    """Pulse on to request a reading from Apple Home."""

    _attr_name = "Refresh"
    _attr_icon = "mdi:homepod"

    def __init__(self, runtime: HomePodIndoorClimateRuntime) -> None:
        super().__init__(runtime, "refresh")

    @property
    def is_on(self) -> bool:
        return self.runtime.refresh_active

    async def async_turn_on(self, **kwargs: Any) -> None:
        self.runtime.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self.runtime.async_end_refresh()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "submission_path": (
                f"/api/homepod_indoor_climate/{self.runtime.entry.entry_id}/readings"
            ),
            "accepted_room_keys": sorted(self.runtime.room_keys),
            "pulse_seconds": 8,
        }
