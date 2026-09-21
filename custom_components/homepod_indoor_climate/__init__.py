"""HomePod Indoor Climate integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .api import HomePodIndoorClimateReadingsView
from .const import DOMAIN, PLATFORMS
from .runtime import HomePodIndoorClimateRuntime

type HomePodIndoorClimateConfigEntry = ConfigEntry[HomePodIndoorClimateRuntime]


async def async_setup(hass: HomeAssistant, _config: dict) -> bool:
    """Register the authenticated API endpoint once."""
    hass.data.setdefault(DOMAIN, {})
    hass.http.register_view(HomePodIndoorClimateReadingsView())
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: HomePodIndoorClimateConfigEntry
) -> bool:
    """Set up one bridge."""
    runtime = HomePodIndoorClimateRuntime(hass, entry)
    entry.runtime_data = runtime
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime
    await runtime.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: HomePodIndoorClimateConfigEntry
) -> bool:
    """Unload one bridge."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_stop()
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def _async_update_listener(
    hass: HomeAssistant, entry: HomePodIndoorClimateConfigEntry
) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
