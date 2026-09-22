"""Runtime state and refresh scheduling."""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.storage import Store

from .const import (
    CONF_ROOMS,
    CONF_STALE_AFTER,
    CONF_UPDATE_INTERVAL,
    DEFAULT_STALE_AFTER,
    DEFAULT_UPDATE_INTERVAL,
    PULSE_SECONDS,
    RATE_LIMIT_REQUESTS,
    RATE_LIMIT_WINDOW_SECONDS,
    SIGNAL_UPDATE,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .models import (
    Reading,
    aggregate,
    fresh_readings,
    restore_readings,
    validate_reading,
)


class HomePodIndoorClimateRuntime:
    """Own readings, persistence, and the HomeKit refresh pulse."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.readings: dict[str, Reading] = {}
        self.refresh_active = False
        self.last_submission: datetime | None = None
        self._cancel_interval: CALLBACK_TYPE | None = None
        self._cancel_pulse: CALLBACK_TYPE | None = None
        self._cancel_initial: CALLBACK_TYPE | None = None
        self._request_times: dict[str, deque[float]] = defaultdict(deque)
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, STORAGE_KEY.format(entry_id=entry.entry_id)
        )

    @property
    def settings(self) -> dict[str, Any]:
        return {**self.entry.data, **self.entry.options}

    @property
    def rooms(self) -> list[dict[str, str]]:
        return list(self.settings[CONF_ROOMS])

    @property
    def room_keys(self) -> set[str]:
        return {room["key"] for room in self.rooms}

    @property
    def stale_after(self) -> int:
        return int(self.settings.get(CONF_STALE_AFTER, DEFAULT_STALE_AFTER))

    @property
    def signal(self) -> str:
        return f"{SIGNAL_UPDATE}_{self.entry.entry_id}"

    async def async_start(self) -> None:
        """Restore recent data and start periodic refresh requests."""
        saved = await self._store.async_load() or {}
        self.readings, storage_needs_cleanup = restore_readings(
            saved.get("readings", {}), self.room_keys
        )
        last = saved.get("last_submission")
        if last:
            try:
                self.last_submission = datetime.fromisoformat(last)
            except (TypeError, ValueError):
                storage_needs_cleanup = True

        if storage_needs_cleanup:
            await self._async_save_state()

        interval = int(self.settings.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL))
        self._cancel_interval = async_track_time_interval(
            self.hass, self._async_interval, timedelta(minutes=interval)
        )
        self._cancel_initial = async_call_later(self.hass, 10, self._async_initial_refresh)
        self._notify()

    async def async_stop(self) -> None:
        """Stop scheduled callbacks."""
        if self._cancel_interval:
            self._cancel_interval()
        if self._cancel_pulse:
            self._cancel_pulse()
        if self._cancel_initial:
            self._cancel_initial()

    async def async_ingest(self, payload: dict[str, Any]) -> int:
        """Validate and store a single reading or a batch."""
        raw_readings = payload.get("readings")
        if raw_readings is None:
            raw_readings = [payload]
        if not isinstance(raw_readings, list) or not raw_readings:
            raise ValueError("readings must be a non-empty list")

        accepted: list[Reading] = []
        for raw in raw_readings:
            if not isinstance(raw, dict):
                raise ValueError("Each reading must be an object")
            accepted.append(validate_reading(raw, self.room_keys))

        for reading in accepted:
            self.readings[reading.room] = reading
        self.last_submission = datetime.now(UTC)
        await self._async_save_state()
        self.async_end_refresh()
        self._notify()
        return len(accepted)

    async def _async_save_state(self) -> None:
        """Persist the current configured readings."""
        await self._store.async_save(
            {
                "last_submission": (
                    self.last_submission.isoformat() if self.last_submission else None
                ),
                "readings": {room: reading.as_dict() for room, reading in self.readings.items()},
            }
        )

    def fresh(self, now: datetime | None = None) -> list[Reading]:
        """Return fresh readings."""
        return fresh_readings(self.readings.values(), now or datetime.now(UTC), self.stale_after)

    def stats(self, now: datetime | None = None) -> dict[str, float | int | None]:
        """Return aggregate values for fresh readings."""
        return aggregate(self.fresh(now))

    @callback
    def allow_submission(self, source: str) -> bool:
        """Apply a small per-source sliding-window request limit."""
        current = monotonic()
        times = self._request_times[source]
        cutoff = current - RATE_LIMIT_WINDOW_SECONDS
        while times and times[0] <= cutoff:
            times.popleft()
        if len(times) >= RATE_LIMIT_REQUESTS:
            return False
        times.append(current)
        return True

    @callback
    def async_request_refresh(self) -> None:
        """Pulse the switch exposed to Apple Home."""
        if self._cancel_pulse:
            self._cancel_pulse()
        self.refresh_active = True
        self._notify()
        self._cancel_pulse = async_call_later(
            self.hass, PULSE_SECONDS, self._async_end_refresh_later
        )

    @callback
    def async_end_refresh(self) -> None:
        """End an active refresh pulse."""
        if self._cancel_pulse:
            self._cancel_pulse()
            self._cancel_pulse = None
        if self.refresh_active:
            self.refresh_active = False
            self._notify()

    @callback
    def _notify(self) -> None:
        async_dispatcher_send(self.hass, self.signal)

    async def _async_interval(self, _now: datetime) -> None:
        self.async_request_refresh()

    async def _async_initial_refresh(self, _now: datetime) -> None:
        self._cancel_initial = None
        self.async_request_refresh()

    async def _async_end_refresh_later(self, _now: datetime) -> None:
        self._cancel_pulse = None
        self.async_end_refresh()
