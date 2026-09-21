"""Constants for HomePod Indoor Climate."""

from __future__ import annotations

DOMAIN = "homepod_indoor_climate"
PLATFORMS = ["sensor", "binary_sensor", "switch"]

CONF_ROOMS = "rooms"
CONF_UPDATE_INTERVAL = "update_interval_minutes"
CONF_STALE_AFTER = "stale_after_minutes"
CONF_ALLOWED_USER_ID = "allowed_user_id"
CONF_LOCAL_ONLY = "local_only"

DEFAULT_UPDATE_INTERVAL = 5
DEFAULT_STALE_AFTER = 15
DEFAULT_LOCAL_ONLY = True
PULSE_SECONDS = 8
RATE_LIMIT_REQUESTS = 60
RATE_LIMIT_WINDOW_SECONDS = 60

API_PATH = "/api/homepod_indoor_climate/{entry_id}/readings"
API_NAME = "api:homepod_indoor_climate:readings"
SIGNAL_UPDATE = f"{DOMAIN}_update"

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.{{entry_id}}"
