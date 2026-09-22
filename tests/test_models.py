"""Tests for pure data helpers."""

import importlib.util
import sys
"""Tests for pure data helpers."""

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

MODULE_PATH = (
    Path(__file__).parents[1] / "custom_components" / "homepod_indoor_climate" / "models.py"
)
SPEC = importlib.util.spec_from_file_location("homepod_indoor_climate_models", MODULE_PATH)
assert SPEC and SPEC.loader
models = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = models
SPEC.loader.exec_module(models)


def test_parse_rooms_and_slugify() -> None:
    assert models.parse_rooms("Living Room\nPrimary Bedroom") == [
        {"key": "living_room", "name": "Living Room"},
        {"key": "primary_bedroom", "name": "Primary Bedroom"},
    ]


def test_parse_rooms_rejects_duplicate_keys() -> None:
    try:
        models.parse_rooms("Living Room, living-room")
    except ValueError:
        pass
    else:
        raise AssertionError("Duplicate normalized room key was accepted")


def test_validate_and_convert_temperature() -> None:
    reading = models.validate_reading(
        {"room": "Living Room", "temperature_c": 20, "humidity": 45},
        {"living_room"},
    )
    assert reading.temperature_f == 68
    assert reading.humidity == 45

    apple_style = models.validate_reading(
        {"room": "living_room", "temperature_c": "20 °C", "humidity": "45%"},
        {"living_room"},
    )
    assert apple_style.temperature_f == 68


def test_rejects_unknown_room_and_bad_values() -> None:
    for payload in (
        {"room": "Garage", "temperature_c": 20, "humidity": 45},
        {"room": "Living Room", "temperature_c": 100, "humidity": 45},
        {"room": "Living Room", "temperature_c": 20, "humidity": 101},
    ):
        try:
            models.validate_reading(payload, {"living_room"})
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid payload was accepted")


def test_fresh_only_aggregate() -> None:
    now = datetime.now(UTC)
    fresh = models.Reading("living_room", 20, 40, now.isoformat())
    fresh_two = models.Reading("bedroom", 22, 50, now.isoformat())
    stale = models.Reading("office", 35, 90, (now - timedelta(minutes=30)).isoformat())
    values = models.fresh_readings([fresh, fresh_two, stale], now, 15)
    stats = models.aggregate(values)
    assert stats["count"] == 2
    assert stats["average_temperature_f"] == 69.8
    assert stats["average_humidity"] == 45
    assert round(stats["temperature_spread_f"], 1) == 3.6


def test_empty_aggregate_is_unavailable() -> None:
    stats = models.aggregate([])
    assert stats["count"] == 0
    assert stats["average_temperature_f"] is None
    assert stats["average_humidity"] is None


def test_restore_readings_prunes_removed_and_invalid_rooms() -> None:
    now = datetime.now(UTC).isoformat()
    restored, needs_cleanup = models.restore_readings(
        {
            "living_room": {
                "room": "living_room",
                "temperature_c": 21,
                "humidity": 45,
                "updated_at": now,
            },
            "deleted_room": {
                "room": "deleted_room",
                "temperature_c": 22,
                "humidity": 50,
                "updated_at": now,
            },
            "bedroom": {"not": "a reading"},
        },
        {"living_room", "bedroom"},
    )

    assert set(restored) == {"living_room"}
    assert needs_cleanup is True


def test_batch_ignores_removed_rooms_and_accepts_configured_rooms() -> None:
    accepted, ignored = models.validate_readings(
        [
            {"room": "Living Room", "temperature_c": 21, "humidity": 45},
            {"room": "Deleted Room", "temperature_c": 22, "humidity": 50},
        ],
        {"living_room"},
    )

    assert [reading.room for reading in accepted] == ["living_room"]
    assert ignored == ["deleted_room"]


def test_batch_with_only_removed_rooms_is_rejected() -> None:
    try:
        models.validate_readings(
            [{"room": "Deleted Room", "temperature_c": 22, "humidity": 50}],
            {"living_room"},
        )
    except ValueError as err:
        assert str(err) == "No configured room readings were provided"
    else:
        raise AssertionError("A batch without configured rooms was accepted")
from datetime import UTC, datetime, timedelta
from pathlib import Path

MODULE_PATH = (
    Path(__file__).parents[1] / "custom_components" / "homepod_indoor_climate" / "models.py"
)
SPEC = importlib.util.spec_from_file_location("homepod_indoor_climate_models", MODULE_PATH)
assert SPEC and SPEC.loader
models = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = models
SPEC.loader.exec_module(models)


def test_parse_rooms_and_slugify() -> None:
    assert models.parse_rooms("Living Room\nPrimary Bedroom") == [
        {"key": "living_room", "name": "Living Room"},
        {"key": "primary_bedroom", "name": "Primary Bedroom"},
    ]


def test_parse_rooms_rejects_duplicate_keys() -> None:
    try:
        models.parse_rooms("Living Room, living-room")
    except ValueError:
        pass
    else:
        raise AssertionError("Duplicate normalized room key was accepted")


def test_validate_and_convert_temperature() -> None:
    reading = models.validate_reading(
        {"room": "Living Room", "temperature_c": 20, "humidity": 45},
        {"living_room"},
    )
    assert reading.temperature_f == 68
    assert reading.humidity == 45

    apple_style = models.validate_reading(
        {"room": "living_room", "temperature_c": "20 °C", "humidity": "45%"},
        {"living_room"},
    )
    assert apple_style.temperature_f == 68


def test_rejects_unknown_room_and_bad_values() -> None:
    for payload in (
        {"room": "Garage", "temperature_c": 20, "humidity": 45},
        {"room": "Living Room", "temperature_c": 100, "humidity": 45},
        {"room": "Living Room", "temperature_c": 20, "humidity": 101},
    ):
        try:
            models.validate_reading(payload, {"living_room"})
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid payload was accepted")


def test_fresh_only_aggregate() -> None:
    now = datetime.now(UTC)
    fresh = models.Reading("living_room", 20, 40, now.isoformat())
    fresh_two = models.Reading("bedroom", 22, 50, now.isoformat())
    stale = models.Reading("office", 35, 90, (now - timedelta(minutes=30)).isoformat())
    values = models.fresh_readings([fresh, fresh_two, stale], now, 15)
    stats = models.aggregate(values)
    assert stats["count"] == 2
    assert stats["average_temperature_f"] == 69.8
    assert stats["average_humidity"] == 45
    assert round(stats["temperature_spread_f"], 1) == 3.6


def test_empty_aggregate_is_unavailable() -> None:
    stats = models.aggregate([])
    assert stats["count"] == 0
    assert stats["average_temperature_f"] is None
    assert stats["average_humidity"] is None


def test_restore_readings_prunes_removed_and_invalid_rooms() -> None:
    now = datetime.now(UTC).isoformat()
    restored, needs_cleanup = models.restore_readings(
        {
            "living_room": {
                "room": "living_room",
                "temperature_c": 21,
                "humidity": 45,
                "updated_at": now,
            },
            "deleted_room": {
                "room": "deleted_room",
                "temperature_c": 22,
                "humidity": 50,
                "updated_at": now,
            },
            "bedroom": {"not": "a reading"},
        },
        {"living_room", "bedroom"},
    )

    assert set(restored) == {"living_room"}
    assert needs_cleanup is True
