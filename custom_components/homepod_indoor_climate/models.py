"""Pure data and validation helpers for HomePod Indoor Climate."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_NUMBER_RE = re.compile(r"^\s*(-?(?:\d+(?:\.\d*)?|\.\d+))\s*([^\d]*)$")


def slugify_room(value: str) -> str:
    """Return a stable ASCII room key."""
    slug = _SLUG_RE.sub("_", value.strip().lower()).strip("_")
    if not slug:
        raise ValueError("Room names must contain letters or numbers")
    return slug


def parse_rooms(value: str | Iterable[str]) -> list[dict[str, str]]:
    """Parse comma/newline-separated rooms and reject duplicate keys."""
    raw = re.split(r"[,\n]", value) if isinstance(value, str) else list(value)
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw:
        name = str(item).strip()
        if not name:
            continue
        key = slugify_room(name)
        if key in seen:
            raise ValueError(f"Duplicate room: {name}")
        seen.add(key)
        result.append({"key": key, "name": name})
    if not result:
        raise ValueError("Enter at least one room")
    return result


@dataclass(slots=True)
class Reading:
    """One HomePod environmental reading."""

    room: str
    temperature_c: float
    humidity: float
    updated_at: str

    @property
    def temperature_f(self) -> float:
        return self.temperature_c * 9.0 / 5.0 + 32.0

    @property
    def timestamp(self) -> datetime:
        return datetime.fromisoformat(self.updated_at)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class UnknownRoomError(ValueError):
    """A submitted reading belongs to a room that is no longer configured."""

    def __init__(self, room: str) -> None:
        super().__init__(f"Unknown room: {room}")
        self.room = room


def restore_readings(raw_readings: Any, allowed_rooms: set[str]) -> tuple[dict[str, Reading], bool]:
    """Restore valid configured readings and report whether storage needs pruning."""
    if not isinstance(raw_readings, dict):
        return {}, raw_readings not in (None, {})

    restored: dict[str, Reading] = {}
    needs_cleanup = False
    for stored_room, data in raw_readings.items():
        if stored_room not in allowed_rooms or not isinstance(data, dict):
            needs_cleanup = True
            continue
        try:
            reading = Reading(**data)
        except (TypeError, ValueError):
            needs_cleanup = True
            continue
        if reading.room != stored_room or reading.room not in allowed_rooms:
            needs_cleanup = True
            continue
        restored[stored_room] = reading
    return restored, needs_cleanup


def validate_readings(
    raw_readings: Any, allowed_rooms: set[str]
) -> tuple[list[Reading], list[str]]:
    """Validate a batch while ignoring rooms removed from configuration."""
    if not isinstance(raw_readings, list) or not raw_readings:
        raise ValueError("readings must be a non-empty list")

    accepted: list[Reading] = []
    ignored_rooms: set[str] = set()
    for raw in raw_readings:
        if not isinstance(raw, dict):
            raise ValueError("Each reading must be an object")
        try:
            accepted.append(validate_reading(raw, allowed_rooms))
        except UnknownRoomError as err:
            ignored_rooms.add(err.room)

    if not accepted:
        raise ValueError("No configured room readings were provided")
    return accepted, sorted(ignored_rooms)


def validate_reading(payload: dict[str, Any], allowed_rooms: set[str]) -> Reading:
    """Validate one request record and normalize its values."""
    try:
        room = slugify_room(str(payload["room"]))
        temperature_c = _coerce_measurement(
            payload["temperature_c"], allowed_suffixes=("", "c", "°c")
        )
        humidity = _coerce_measurement(payload["humidity"], allowed_suffixes=("", "%"))
    except (KeyError, TypeError, ValueError) as err:
        raise ValueError("room, temperature_c, and humidity are required") from err

    if room not in allowed_rooms:
        raise UnknownRoomError(room)
    if not math.isfinite(temperature_c) or not -40.0 <= temperature_c <= 60.0:
        raise ValueError("temperature_c must be between -40 and 60")
    if not math.isfinite(humidity) or not 0.0 <= humidity <= 100.0:
        raise ValueError("humidity must be between 0 and 100")

    return Reading(
        room=room,
        temperature_c=temperature_c,
        humidity=humidity,
        updated_at=datetime.now(UTC).isoformat(),
    )


def _coerce_measurement(value: Any, allowed_suffixes: tuple[str, ...]) -> float:
    """Accept JSON numbers and the unit-bearing strings Apple may emit."""
    if isinstance(value, bool):
        raise ValueError("Boolean is not a measurement")
    if isinstance(value, (int, float)):
        return float(value)
    match = _NUMBER_RE.match(str(value))
    if not match or match.group(2).strip().lower() not in allowed_suffixes:
        raise ValueError("Invalid measurement")
    return float(match.group(1))


def fresh_readings(
    readings: Iterable[Reading], now: datetime, stale_after_minutes: int
) -> list[Reading]:
    """Return readings inside the configured freshness window."""
    threshold = now - timedelta(minutes=stale_after_minutes)
    return [reading for reading in readings if reading.timestamp >= threshold]


def aggregate(readings: Iterable[Reading]) -> dict[str, float | int | None]:
    """Calculate room-weighted environmental statistics."""
    values = list(readings)
    if not values:
        return {
            "count": 0,
            "average_temperature_f": None,
            "average_humidity": None,
            "minimum_temperature_f": None,
            "maximum_temperature_f": None,
            "temperature_spread_f": None,
        }
    temperatures = [reading.temperature_f for reading in values]
    humidities = [reading.humidity for reading in values]
    minimum = min(temperatures)
    maximum = max(temperatures)
    return {
        "count": len(values),
        "average_temperature_f": sum(temperatures) / len(temperatures),
        "average_humidity": sum(humidities) / len(humidities),
        "minimum_temperature_f": minimum,
        "maximum_temperature_f": maximum,
        "temperature_spread_f": maximum - minimum,
    }
