"""Entity identifiers owned by a HomePod Indoor Climate config entry."""

from __future__ import annotations

from collections.abc import Iterable

STATIC_ENTITY_KEYS = frozenset(
    {
        "average_temperature",
        "average_humidity",
        "minimum_temperature",
        "maximum_temperature",
        "temperature_spread",
        "fresh_room_count",
        "last_submission",
        "stale_readings",
        "refresh",
        "refresh_diagnostics",
    }
)


def expected_unique_ids(entry_id: str, room_keys: Iterable[str]) -> set[str]:
    """Return every entity unique ID that should exist for an entry."""
    keys = set(STATIC_ENTITY_KEYS)
    for room_key in room_keys:
        keys.add(f"{room_key}_temperature")
        keys.add(f"{room_key}_humidity")
    return {f"{entry_id}_{key}" for key in keys}


def stale_unique_ids(
    existing_unique_ids: Iterable[str], entry_id: str, room_keys: Iterable[str]
) -> set[str]:
    """Return registry unique IDs that are obsolete for the entry configuration."""
    return set(existing_unique_ids) - expected_unique_ids(entry_id, room_keys)
