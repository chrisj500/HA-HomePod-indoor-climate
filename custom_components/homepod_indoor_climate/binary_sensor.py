"""Freshness status for HomePod Indoor Climate."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.helpers.entity import EntityCategory

from . import HomePodIndoorClimateConfigEntry
from .entity import HomePodIndoorClimateEntity
from .runtime import HomePodIndoorClimateRuntime


async def async_setup_entry(
    _hass, entry: HomePodIndoorClimateConfigEntry, async_add_entities
) -> None:
    """Set up bridge binary sensors."""
    async_add_entities([StaleReadingsSensor(entry.runtime_data)])


class StaleReadingsSensor(HomePodIndoorClimateEntity, BinarySensorEntity):
    """Report missing or stale room data as a problem."""

    _attr_name = "Stale Readings"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, runtime: HomePodIndoorClimateRuntime) -> None:
        super().__init__(runtime, "stale_readings")

    @property
    def is_on(self) -> bool:
        return len(self.runtime.fresh()) < len(self.runtime.rooms)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        fresh_keys = {reading.room for reading in self.runtime.fresh()}
        return {
            "fresh_rooms": sorted(fresh_keys),
            "stale_or_missing_rooms": sorted(self.runtime.room_keys - fresh_keys),
            "stale_after_minutes": self.runtime.stale_after,
        }
