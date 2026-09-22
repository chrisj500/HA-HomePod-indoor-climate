"""Tests for entity-registry reconciliation identifiers."""

import importlib.util
from pathlib import Path

MODULE_PATH = (
    Path(__file__).parents[1] / "custom_components" / "homepod_indoor_climate" / "entity_catalog.py"
)
SPEC = importlib.util.spec_from_file_location("homepod_indoor_climate_catalog", MODULE_PATH)
assert SPEC and SPEC.loader
catalog = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(catalog)


def test_expected_unique_ids_drop_removed_room_entities() -> None:
    before = catalog.expected_unique_ids("entry", {"living_room", "bedroom"})
    after = catalog.expected_unique_ids("entry", {"living_room"})

    assert "entry_bedroom_temperature" in before
    assert "entry_bedroom_humidity" in before
    assert "entry_bedroom_temperature" not in after
    assert "entry_bedroom_humidity" not in after
    assert "entry_living_room_temperature" in after
    assert "entry_average_temperature" in after
    assert "entry_stale_readings" in after
    assert "entry_refresh" in after
    assert "entry_refresh_diagnostics" in after


def test_stale_unique_ids_identifies_only_obsolete_entities() -> None:
    existing = {
        "entry_living_room_temperature",
        "entry_living_room_humidity",
        "entry_deleted_room_temperature",
        "entry_deleted_room_humidity",
        "entry_average_temperature",
        "entry_refresh",
        "entry_refresh_diagnostics",
    }

    assert catalog.stale_unique_ids(existing, "entry", {"living_room"}) == {
        "entry_deleted_room_temperature",
        "entry_deleted_room_humidity",
    }
