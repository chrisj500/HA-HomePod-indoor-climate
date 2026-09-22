"""Authenticated HTTP endpoint for HomePod readings."""

from __future__ import annotations

import ipaddress
import logging
from http import HTTPStatus

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.const import KEY_HASS, KEY_HASS_USER
from homeassistant.core import HomeAssistant

from .const import API_NAME, API_PATH, CONF_ALLOWED_USER_ID, CONF_LOCAL_ONLY, DOMAIN

_LOGGER = logging.getLogger(__name__)


class HomePodIndoorClimateReadingsView(HomeAssistantView):
    """Receive authenticated environmental readings."""

    url = API_PATH
    name = API_NAME
    requires_auth = True

    async def post(self, request: web.Request, entry_id: str) -> web.Response:
        """Accept a single reading or batch."""
        hass: HomeAssistant = request.app[KEY_HASS]
        runtime = hass.data.get(DOMAIN, {}).get(entry_id)
        if runtime is None:
            raise web.HTTPNotFound(text="Unknown integration entry")

        settings = runtime.settings
        allowed_user_id = settings.get(CONF_ALLOWED_USER_ID)
        user = request.get(KEY_HASS_USER)
        if allowed_user_id and (user is None or user.id != allowed_user_id):
            raise web.HTTPForbidden(text="This token is not authorized for this bridge")

        if settings.get(CONF_LOCAL_ONLY, True) and not _is_private_request(request):
            raise web.HTTPForbidden(text="Remote submissions are disabled")

        source = f"{getattr(user, 'id', 'unknown')}:{request.remote or 'unknown'}"
        if not runtime.allow_submission(source):
            raise web.HTTPTooManyRequests(text="Too many submissions; try again shortly")

        if request.content_length is not None and request.content_length > 16_384:
            raise web.HTTPRequestEntityTooLarge(max_size=16_384, actual_size=request.content_length)
        try:
            payload = await request.json()
        except (ValueError, TypeError) as err:
            raise web.HTTPBadRequest(text="Expected a JSON object") from err
        if not isinstance(payload, dict):
            raise web.HTTPBadRequest(text="Expected a JSON object")

        try:
            count, ignored_rooms = await runtime.async_ingest(payload)
        except ValueError as err:
            _LOGGER.warning("Rejected HomePod reading: %s", err)
            raise web.HTTPBadRequest(text=str(err)) from err

        return web.json_response(
            {
                "accepted": count,
                "ignored_rooms": ignored_rooms,
                "fresh_rooms": len(runtime.fresh()),
            },
            status=HTTPStatus.OK,
        )


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
