"""Authenticated HTTP endpoint for HomePod readings."""

from __future__ import annotations

import ipaddress
import logging
from http import HTTPStatus

from aiohttp import hdrs, web
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.auth_util import async_user_not_allowed_do_auth
from homeassistant.components.http.const import KEY_HASS
from homeassistant.core import HomeAssistant

from .const import API_NAME, API_PATH, CONF_ALLOWED_USER_ID, CONF_LOCAL_ONLY, DOMAIN

_LOGGER = logging.getLogger(__name__)


class HomePodIndoorClimateReadingsView(HomeAssistantView):
    """Receive authenticated environmental readings."""

    url = API_PATH
    name = API_NAME
    requires_auth = False

    async def post(self, request: web.Request, entry_id: str) -> web.Response:
        """Accept a single reading or batch."""
        hass: HomeAssistant = request.app[KEY_HASS]
        runtime = hass.data.get(DOMAIN, {}).get(entry_id)
        if runtime is None:
            raise web.HTTPNotFound(text="Unknown integration entry")

        auth_header = request.headers.get(hdrs.AUTHORIZATION, "")
        private_source = _is_private_request(request)
        runtime.record_api_request(
            authorization_header_present=bool(auth_header),
            private_source=private_source,
        )

        user = _authenticate_request(hass, request, auth_header)
        if user is None:
            runtime.record_api_auth_failure(_auth_failure_reason(hass, request, auth_header))
            raise web.HTTPUnauthorized(text="Invalid or missing Home Assistant bearer token")

        runtime.record_api_authenticated()
        settings = runtime.settings
        allowed_user_id = settings.get(CONF_ALLOWED_USER_ID)

        if allowed_user_id and user.id != allowed_user_id:
            runtime.record_api_rejection("forbidden_user")
            raise web.HTTPForbidden(text="This token is not authorized for this bridge")

        if settings.get(CONF_LOCAL_ONLY, True) and not private_source:
            runtime.record_api_rejection("remote_rejected")
            raise web.HTTPForbidden(text="Remote submissions are disabled")

        source = f"{user.id}:{request.remote or 'unknown'}"
        if not runtime.allow_submission(source):
            runtime.record_api_rejection("rate_limited")
            raise web.HTTPTooManyRequests(text="Too many submissions; try again shortly")

        if request.content_length is not None and request.content_length > 16_384:
            runtime.record_api_rejection("payload_too_large")
            raise web.HTTPRequestEntityTooLarge(
                max_size=16_384, actual_size=request.content_length
            )

        try:
            payload = await request.json()
        except (ValueError, TypeError) as err:
            runtime.record_api_rejection("invalid_json")
            raise web.HTTPBadRequest(text="Expected a JSON object") from err

        if not isinstance(payload, dict):
            runtime.record_api_rejection("invalid_json_object")
            raise web.HTTPBadRequest(text="Expected a JSON object")

        try:
            count, ignored_rooms = await runtime.async_ingest(payload)
        except ValueError as err:
            runtime.record_api_rejection("invalid_reading")
            _LOGGER.warning("Rejected HomePod reading: %s", err)
            raise web.HTTPBadRequest(text=str(err)) from err

        runtime.record_api_accept(count, ignored_rooms)
        return web.json_response(
            {
                "accepted": count,
                "ignored_rooms": ignored_rooms,
                "fresh_rooms": len(runtime.fresh()),
            },
            status=HTTPStatus.OK,
        )


def _authenticate_request(
    hass: HomeAssistant, request: web.Request, auth_header: str
):
    """Return the authenticated HA user or None."""
    try:
        auth_type, auth_value = auth_header.split(" ", 1)
    except ValueError:
        return None

    if auth_type != "Bearer":
        return None

    refresh_token = hass.auth.async_validate_access_token(auth_value)
    if refresh_token is None:
        return None

    if async_user_not_allowed_do_auth(hass, refresh_token.user, request):
        return None

    return refresh_token.user


def _auth_failure_reason(
    hass: HomeAssistant, request: web.Request, auth_header: str
) -> str:
    """Return a non-secret diagnostic reason for authentication failure."""
    if not auth_header:
        return "missing_authorization_header"

    try:
        auth_type, auth_value = auth_header.split(" ", 1)
    except ValueError:
        return "malformed_authorization_header"

    if auth_type != "Bearer":
        return "wrong_authorization_scheme"

    refresh_token = hass.auth.async_validate_access_token(auth_value)
    if refresh_token is None:
        return "invalid_bearer_token"

    restriction = async_user_not_allowed_do_auth(hass, refresh_token.user, request)
    if restriction:
        return "user_auth_restricted"

    return "unknown_auth_failure"


def _is_private_request(request: web.Request) -> bool:
    """Return whether the resolved peer is local/private."""
    remote = request.remote
    if not remote:
        return False
    try:
        address = ipaddress.ip_address(remote.split("%", 1)[0])
    except ValueError:
        return False
    return address.is_private or address.is_loopback or address.is_link_local
