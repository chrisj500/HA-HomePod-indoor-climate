"""Sensors for HomePod Indoor Climate."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.helpers.entity import EntityCategory

from . import HomePodIndoorClimateConfigEntry
from .entity import HomePodIndoorClimateEntity
from .runtime import HomePodIndoorClimateRuntime


async def async_setup_entry(
    _hass, entry: HomePodIndoorClimateConfigEntry, async_add_entities
) -> None:
    """Set up bridge sensors."""
    runtime = entry.runtime_data
    entities: list[SensorEntity] = []
    for room in runtime.rooms:
        entities.extend(
            (
                RoomTemperatureSensor(runtime, room["key"], room["name"]),
                RoomHumiditySensor(runtime, room["key"], room["name"]),
            )
        )
    entities.extend(
        (
            AggregateSensor(
                runtime,
                "average_temperature",
                "Average Temperature",
                "average_temperature_f",
                "temperature",
            ),
            AggregateSensor(
                runtime,
                "average_humidity",
                "Average Humidity",
                "average_humidity",
                "humidity",
            ),
            AggregateSensor(
                runtime,
                "minimum_temperature",
                "Minimum Temperature",
                "minimum_temperature_f",
                "temperature",
            ),
            AggregateSensor(
                runtime,
                "maximum_temperature",
                "Maximum Temperature",
                "maximum_temperature_f",
                "temperature",
            ),
            AggregateSensor(
                runtime,
                "temperature_spread",
                "Temperature Spread",
                "temperature_spread_f",
                "temperature",
            ),
            FreshRoomCountSensor(runtime),
            LastSubmissionSensor(runtime),
            RefreshDiagnosticsSensor(runtime),
        )
    )
    async_add_entities(entities)


class RoomSensor(HomePodIndoorClimateEntity, SensorEntity):
    """Base class for a configured room."""

    def __init__(
        self,
        runtime: HomePodIndoorClimateRuntime,
        room_key: str,
        room_name: str,
        kind: str,
    ) -> None:
        super().__init__(runtime, f"{room_key}_{kind}")
        self.room_key = room_key
        self._attr_name = f"{room_name} {kind.title()}"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_suggested_display_precision = 1

    @property
    def reading(self):
        return self.runtime.readings.get(self.room_key)

    @property
    def available(self) -> bool:
        reading = self.reading
        return reading is not None and reading in self.runtime.fresh()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        reading = self.reading
        if reading is None:
            return {"room_key": self.room_key, "fresh": False}
        return {
            "room_key": self.room_key,
            "last_received": reading.updated_at,
            "fresh": self.available,
            "source_temperature_c": round(reading.temperature_c, 3),
        }


class RoomTemperatureSensor(RoomSensor):
    """Fahrenheit temperature for one room."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT

    def __init__(
        self, runtime: HomePodIndoorClimateRuntime, room_key: str, room_name: str
    ) -> None:
        super().__init__(runtime, room_key, room_name, "temperature")

    @property
    def native_value(self) -> float | None:
        return round(self.reading.temperature_f, 2) if self.reading else None


class RoomHumiditySensor(RoomSensor):
    """Humidity for one room."""

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self, runtime: HomePodIndoorClimateRuntime, room_key: str, room_name: str
    ) -> None:
        super().__init__(runtime, room_key, room_name, "humidity")

    @property
    def native_value(self) -> float | None:
        return round(self.reading.humidity, 2) if self.reading else None


class AggregateSensor(HomePodIndoorClimateEntity, SensorEntity):
    """Fresh-room aggregate sensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        runtime: HomePodIndoorClimateRuntime,
        key: str,
        name: str,
        stat_key: str,
        kind: str,
    ) -> None:
        super().__init__(runtime, key)
        self._attr_name = name
        self.stat_key = stat_key
        if kind == "temperature":
            self._attr_device_class = SensorDeviceClass.TEMPERATURE
            self._attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
        else:
            self._attr_device_class = SensorDeviceClass.HUMIDITY
            self._attr_native_unit_of_measurement = PERCENTAGE

    @property
    def native_value(self) -> float | None:
        value = self.runtime.stats()[self.stat_key]
        return round(float(value), 2) if value is not None else None

    @property
    def available(self) -> bool:
        return bool(self.runtime.fresh())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        fresh = self.runtime.fresh()
        return {
            "contributing_rooms": [reading.room for reading in fresh],
            "fresh_room_count": len(fresh),
            "configured_room_count": len(self.runtime.rooms),
            "stale_after_minutes": self.runtime.stale_after,
        }


class FreshRoomCountSensor(HomePodIndoorClimateEntity, SensorEntity):
    """Number of rooms currently contributing to aggregates."""

    _attr_name = "Fresh Room Count"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, runtime: HomePodIndoorClimateRuntime) -> None:
        super().__init__(runtime, "fresh_room_count")

    @property
    def native_value(self) -> int:
        return len(self.runtime.fresh())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"configured_room_count": len(self.runtime.rooms)}


class LastSubmissionSensor(HomePodIndoorClimateEntity, SensorEntity):
    """Timestamp of the most recent accepted submission."""

    _attr_name = "Last Submission"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, runtime: HomePodIndoorClimateRuntime) -> None:
        super().__init__(runtime, "last_submission")

    @property
    def native_value(self) -> datetime | None:
        value = self.runtime.last_submission
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "submission_path": (
                f"/api/homepod_indoor_climate/{self.runtime.entry.entry_id}/readings"
            ),
            "accepted_room_keys": sorted(self.runtime.room_keys),
        }


class RefreshDiagnosticsSensor(HomePodIndoorClimateEntity, SensorEntity):
    """Summarize refresh and API diagnostics."""

    _attr_name = "Refresh Diagnostics"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, runtime: HomePodIndoorClimateRuntime) -> None:
        super().__init__(runtime, "refresh_diagnostics")

    @property
    def native_value(self) -> str:
        return self.runtime.last_refresh_result

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.runtime.diagnostics_snapshot()
