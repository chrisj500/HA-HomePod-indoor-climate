"""Runtime state, refresh scheduling, and diagnostics."""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
import logging
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
    validate_readings,
)

_LOGGER = logging.getLogger(__name__)


def _isoformat(value: datetime | None) -> str | None:
    """Return an ISO timestamp for diagnostics."""
    return value.isoformat() if value else None


class HomePodIndoorClimateRuntime:
    """Own readings, persistence, refresh scheduling, and diagnostics."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.readings: dict[str, Reading] = {}
        self.refresh_active = False
        self.last_submission: datetime | None = None

        self.refresh_sequence = 0
        self.refresh_request_count = 0
        self.refresh_timeout_count = 0
        self.refresh_submission_count = 0
        self.refresh_manual_end_count = 0
        self.refresh_superseded_count = 0
        self.current_refresh_sequence: int | None = None
        self.current_refresh_source: str | None = None
        self.current_refresh_started_at: datetime | None = None
        self.current_refresh_deadline: datetime | None = None
        self.last_refresh_sequence: int | None = None
        self.last_refresh_source: str | None = None
        self.last_refresh_requested_at: datetime | None = None
        self.last_refresh_completed_at: datetime | None = None
        self.last_refresh_result = "never"
        self.last_refresh_latency_ms: int | None = None

        self.api_request_count = 0
        self.api_authenticated_count = 0
        self.api_auth_failure_count = 0
        self.api_accepted_count = 0
        self.api_rejected_count = 0
        self.last_api_request_at: datetime | None = None
        self.last_api_result = "never"
        self.last_api_auth_result = "never"
        self.last_api_authorization_header_present = False
        self.last_api_private_source = False
        self.last_api_request_during_refresh = False
        self.last_api_refresh_sequence: int | None = None
        self.last_api_accepted_rooms = 0
        self.last_api_ignored_rooms: list[str] = []

        self._cancel_interval: CALLBACK_TYPE | None = None
        self._cancel_pulse: CALLBACK_TYPE | None = None
        self._cancel_initial: CALLBACK_TYPE | None = None
        self._request_times: dict[str, deque[float]] = defaultdict(deque)
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, STORAGE_KEY.format(entry_id=entry.entry_id)
        )

    @property
    def settings(self) -> dict[str, Any]:
        """Return merged config-entry settings."""
        return {**self.entry.data, **self.entry.options}

    @property
    def rooms(self) -> list[dict[str, str]]:
        """Return configured rooms."""
        return list(self.settings[CONF_ROOMS])

    @property
    def room_keys(self) -> set[str]:
        """Return configured room keys."""
        return {room["key"] for room in self.rooms}

    @property
    def stale_after(self) -> int:
        """Return freshness threshold in minutes."""
        return int(self.settings.get(CONF_STALE_AFTER, DEFAULT_STALE_AFTER))

    @property
    def signal(self) -> str:
        """Return dispatcher signal for this config entry."""
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
        self._cancel_initial = async_call_later(
            self.hass, 10, self._async_initial_refresh
        )
        self._notify()

    async def async_stop(self) -> None:
        """Stop scheduled callbacks."""
        if self._cancel_interval:
            self._cancel_interval()
        if self._cancel_pulse:
            self._cancel_pulse()
        if self._cancel_initial:
            self._cancel_initial()

    async def async_ingest(self, payload: dict[str, Any]) -> tuple[int, list[str]]:
        """Validate and store a single reading or a batch."""
        raw_readings = payload.get("readings")
        if raw_readings is None:
            raw_readings = [payload]
        accepted, ignored_rooms = validate_readings(raw_readings, self.room_keys)

        for reading in accepted:
            self.readings[reading.room] = reading
        self.last_submission = datetime.now(UTC)
        await self._async_save_state()

        ended_refresh = self.async_end_refresh("submission")
        if not ended_refresh:
            self._notify()
        return len(accepted), ignored_rooms

    async def _async_save_state(self) -> None:
        """Persist current configured readings."""
        await self._store.async_save(
            {
                "last_submission": (
                    self.last_submission.isoformat() if self.last_submission else None
                ),
                "readings": {
                    room: reading.as_dict()
                    for room, reading in self.readings.items()
                },
            }
        )

    def fresh(self, now: datetime | None = None) -> list[Reading]:
        """Return fresh readings."""
        return fresh_readings(
            self.readings.values(), now or datetime.now(UTC), self.stale_after
        )

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
    def record_api_request(
        self, *, authorization_header_present: bool, private_source: bool
    ) -> None:
        """Record every HTTP request that reaches the integration route."""
        self.api_request_count += 1
        self.last_api_request_at = datetime.now(UTC)
        self.last_api_result = "received"
        self.last_api_auth_result = "pending"
        self.last_api_authorization_header_present = authorization_header_present
        self.last_api_private_source = private_source
        self.last_api_request_during_refresh = self.refresh_active
        self.last_api_refresh_sequence = self.current_refresh_sequence
        self._notify()

    @callback
    def record_api_authenticated(self) -> None:
        """Record successful Home Assistant bearer authentication."""
        self.api_authenticated_count += 1
        self.last_api_auth_result = "authenticated"
        self._notify()

    @callback
    def record_api_auth_failure(self, reason: str) -> None:
        """Record a request that reached the route but failed HA authentication."""
        self.api_auth_failure_count += 1
        self.api_rejected_count += 1
        self.last_api_auth_result = reason
        self.last_api_result = reason
        self.last_api_accepted_rooms = 0
        self.last_api_ignored_rooms = []
        self._notify()

    @callback
    def record_api_rejection(self, reason: str) -> None:
        """Record an authenticated API request rejected by integration policy."""
        self.api_rejected_count += 1
        self.last_api_result = reason
        self.last_api_accepted_rooms = 0
        self.last_api_ignored_rooms = []
        self._notify()

    @callback
    def record_api_accept(self, accepted: int, ignored_rooms: list[str]) -> None:
        """Record a successful API submission."""
        self.api_accepted_count += 1
        self.last_api_result = "accepted"
        self.last_api_accepted_rooms = accepted
        self.last_api_ignored_rooms = list(ignored_rooms)
        self._notify()

    @callback
    def async_request_refresh(self, source: str = "manual") -> None:
        """Pulse the HomeKit-visible switch and record request diagnostics."""
        now = datetime.now(UTC)

        if self.refresh_active:
            self._complete_refresh("superseded", now, notify=False)

        if self._cancel_pulse:
            self._cancel_pulse()
            self._cancel_pulse = None

        self.refresh_sequence += 1
        self.refresh_request_count += 1
        self.current_refresh_sequence = self.refresh_sequence
        self.current_refresh_source = source
        self.current_refresh_started_at = now
        self.current_refresh_deadline = now + timedelta(seconds=PULSE_SECONDS)
        self.last_refresh_sequence = self.refresh_sequence
        self.last_refresh_source = source
        self.last_refresh_requested_at = now
        self.last_refresh_result = "pending"
        self.last_refresh_latency_ms = None
        self.refresh_active = True

        _LOGGER.debug(
            "Refresh %s requested (%s)",
            self.current_refresh_sequence,
            source,
        )
        self._notify()
        self._cancel_pulse = async_call_later(
            self.hass, PULSE_SECONDS, self._async_end_refresh_later
        )

    @callback
    def async_end_refresh(self, reason: str = "manual_off") -> bool:
        """End an active refresh pulse and record why it ended."""
        if not self.refresh_active:
            return False

        if self._cancel_pulse:
            self._cancel_pulse()
            self._cancel_pulse = None

        self._complete_refresh(reason, datetime.now(UTC), notify=True)
        return True

    @callback
    def _complete_refresh(
        self, reason: str, completed_at: datetime, *, notify: bool
    ) -> None:
        """Finalize diagnostics for the current refresh."""
        started_at = self.current_refresh_started_at
        sequence = self.current_refresh_sequence

        self.refresh_active = False
        self.last_refresh_completed_at = completed_at
        self.last_refresh_result = reason
        if started_at is not None:
            self.last_refresh_latency_ms = round(
                (completed_at - started_at).total_seconds() * 1000
            )

        if reason == "timeout":
            self.refresh_timeout_count += 1
        elif reason == "submission":
            self.refresh_submission_count += 1
        elif reason == "manual_off":
            self.refresh_manual_end_count += 1
        elif reason == "superseded":
            self.refresh_superseded_count += 1

        _LOGGER.debug(
            "Refresh %s completed (%s) after %sms",
            sequence,
            reason,
            self.last_refresh_latency_ms,
        )

        self.current_refresh_sequence = None
        self.current_refresh_source = None
        self.current_refresh_started_at = None
        self.current_refresh_deadline = None

        if notify:
            self._notify()

    @callback
    def diagnostics_snapshot(self) -> dict[str, Any]:
        """Return JSON-serializable runtime diagnostics."""
        now = datetime.now(UTC)
        current_age_seconds: float | None = None
        if self.current_refresh_started_at is not None:
            current_age_seconds = round(
                (now - self.current_refresh_started_at).total_seconds(), 3
            )

        return {
            "refresh": {
                "active": self.refresh_active,
                "sequence": self.refresh_sequence,
                "request_count": self.refresh_request_count,
                "timeout_count": self.refresh_timeout_count,
                "submission_count": self.refresh_submission_count,
                "manual_end_count": self.refresh_manual_end_count,
                "superseded_count": self.refresh_superseded_count,
                "current_sequence": self.current_refresh_sequence,
                "current_source": self.current_refresh_source,
                "current_started_at": _isoformat(self.current_refresh_started_at),
                "current_deadline": _isoformat(self.current_refresh_deadline),
                "current_age_seconds": current_age_seconds,
                "last_sequence": self.last_refresh_sequence,
                "last_source": self.last_refresh_source,
                "last_requested_at": _isoformat(self.last_refresh_requested_at),
                "last_completed_at": _isoformat(self.last_refresh_completed_at),
                "last_result": self.last_refresh_result,
                "last_latency_ms": self.last_refresh_latency_ms,
                "pulse_seconds": PULSE_SECONDS,
            },
            "api": {
                "request_count": self.api_request_count,
                "authenticated_count": self.api_authenticated_count,
                "auth_failure_count": self.api_auth_failure_count,
                "accepted_count": self.api_accepted_count,
                "rejected_count": self.api_rejected_count,
                "last_request_at": _isoformat(self.last_api_request_at),
                "last_result": self.last_api_result,
                "last_auth_result": self.last_api_auth_result,
                "last_authorization_header_present": (
                    self.last_api_authorization_header_present
                ),
                "last_private_source": self.last_api_private_source,
                "last_request_during_refresh": self.last_api_request_during_refresh,
                "last_refresh_sequence": self.last_api_refresh_sequence,
                "last_accepted_rooms": self.last_api_accepted_rooms,
                "last_ignored_rooms": list(self.last_api_ignored_rooms),
                "pre_auth_failures_observable": True,
            },
            "readings": {
                "configured_rooms": len(self.rooms),
                "fresh_rooms": len(self.fresh()),
                "last_submission": _isoformat(self.last_submission),
                "stale_after_minutes": self.stale_after,
            },
        }

    @callback
    def _notify(self) -> None:
        """Notify entities that runtime state changed."""
        async_dispatcher_send(self.hass, self.signal)

    async def _async_interval(self, _now: datetime) -> None:
        self.async_request_refresh("scheduled")

    async def _async_initial_refresh(self, _now: datetime) -> None:
        self._cancel_initial = None
        self.async_request_refresh("initial")

    async def _async_end_refresh_later(self, _now: datetime) -> None:
        self._cancel_pulse = None
        self.async_end_refresh("timeout")
