# HomePod Indoor Climate

A Home Assistant custom integration that turns Apple HomePod temperature and
humidity readings into normal Home Assistant entities. Apple Home supplies the
# HomePod Indoor Climate

A Home Assistant custom integration that turns Apple HomePod temperature and
humidity readings into normal Home Assistant entities. Apple Home supplies the
readings; the integration authenticates, validates, stores, converts, aggregates,
and monitors them.

## What it creates

- Fahrenheit temperature and relative-humidity sensors for every configured room
- Fresh-room average temperature and humidity
- Fresh-room minimum, maximum, and temperature spread
- A stale/missing-readings problem sensor
- Fresh-room count and last-submission diagnostics
- A refresh switch that Apple Home can use as an automation trigger

Incoming temperature values remain stored as Celsius internally and are exposed
in Fahrenheit. The raw Celsius value is also available as a temperature entity
attribute. Aggregate sensors exclude readings older than the configured stale
threshold.
Removing or renaming a configured room also removes its obsolete entities and
stored reading when the integration reloads.
If an Apple automation temporarily continues submitting a removed room, that
reading is ignored without preventing configured rooms from updating.

## Install

1. In HACS, open **Integrations** and choose **Custom repositories**.
2. Add this repository as an **Integration**.
3. Install **HomePod Indoor Climate** and restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration** and select
   **HomePod Indoor Climate**.
5. Enter one HomePod room or zone label per line. The displayed names become
   lowercase API keys: `Living Room` becomes `living_room`.

For a manual test before installing through HACS, copy
`custom_components/homepod_indoor_climate` into Home Assistant's
`/config/custom_components/` directory, restart Home Assistant, and continue
from step 4.

Use a distinct label for each HomePod you want weighted independently. For
example, use `Living Room East` and `Living Room West` rather than submitting
both devices under the same key.

## Authentication

Create a dedicated, non-administrator Home Assistant user for this bridge, log
in as that user, and create a long-lived access token from its profile. In the
integration options, select that user under **Only accept this Home Assistant
user**.

The receiver is a normal authenticated Home Assistant API view. Requests need:

```http
Authorization: Bearer YOUR_LONG_LIVED_ACCESS_TOKEN
Content-Type: application/json
```

The token is not stored by this integration. Home Assistant validates it before
the request reaches the bridge. The optional user restriction ensures that even
another valid Home Assistant user's token cannot submit data to this bridge.

**Accept submissions only from the local network** is enabled by default. Keep
it enabled and use Home Assistant's LAN URL in the Apple Home automation. A Home
Assistant proxy configuration that reports a public client address will be
rejected while this option is enabled.

## Apple Home automation

Expose the integration's **Refresh** switch through Home Assistant's HomeKit
Bridge. Then, in the Apple Home app on an iPhone or iPad:

1. Create an automation for **An Accessory is Controlled**.
2. Select the HomePod Indoor Climate **Refresh** switch and trigger when it
   turns on.
3. Choose **Convert to Shortcut**.
4. Read the current temperature and humidity from each HomePod.
5. Add **Get Contents of URL** for each configured room.
6. Use `POST`, set the two headers above, choose a JSON request body, and submit:

```json
{
  "room": "living_room",
  "temperature_c": 20.4,
  "humidity": 47
}
```

The endpoint is:

```text
http://HOME_ASSISTANT_LAN_ADDRESS:8123/api/homepod_indoor_climate/ENTRY_ID/readings
```

You do not need to hunt for `ENTRY_ID`: open the integration's **Refresh**
switch or **Last Submission** sensor and copy its `submission_path` attribute.
The `accepted_room_keys` attribute lists the exact room values to send.

Apple may pass measurements as `20.4 °C` and `47%`; the endpoint accepts those
forms as well as plain JSON numbers. Fahrenheit input is deliberately rejected
because the field is explicitly Celsius.

For advanced shortcuts, all rooms can be submitted in one request:

```json
{
  "readings": [
    {"room": "living_room", "temperature_c": 20.4, "humidity": 47},
    {"room": "bedroom", "temperature_c": 21.1, "humidity": 44}
  ]
}
```

## How refresh and freshness work

At the configured interval, Home Assistant pulses the **Refresh** switch on for
eight seconds. The Apple Home automation observes that change and posts the
latest readings. An accepted response turns the switch off immediately.

The default refresh interval is five minutes and the default stale threshold is
15 minutes. A late or failed Apple automation therefore cannot quietly leave an
old value in the whole-home average: stale room entities become unavailable,
the aggregate drops that room, and **Stale Readings** turns on.

## API responses

Successful submission:

```json
{"accepted": 1, "fresh_rooms": 1}
```

The endpoint rejects invalid tokens, unauthorized users, non-local requests
when local-only mode is enabled, unknown rooms, impossible values, oversized
bodies, and excessive request rates. Valid ranges are -40 to 60 °C and 0 to
100% relative humidity.

## Development validation

Pure conversion, validation, freshness, and aggregate logic is covered by the
tests in `tests/test_models.py`. The integration targets current Home Assistant
releases and Python 3.12 or newer.
readings; the integration authenticates, validates, stores, converts, aggregates,
and monitors them.

## What it creates

- Fahrenheit temperature and relative-humidity sensors for every configured room
- Fresh-room average temperature and humidity
- Fresh-room minimum, maximum, and temperature spread
- A stale/missing-readings problem sensor
- Fresh-room count and last-submission diagnostics
- A refresh switch that Apple Home can use as an automation trigger

Incoming temperature values remain stored as Celsius internally and are exposed
in Fahrenheit. The raw Celsius value is also available as a temperature entity
attribute. Aggregate sensors exclude readings older than the configured stale
threshold.
Removing or renaming a configured room also removes its obsolete entities and
stored reading when the integration reloads.

## Install

1. In HACS, open **Integrations** and choose **Custom repositories**.
2. Add this repository as an **Integration**.
3. Install **HomePod Indoor Climate** and restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration** and select
   **HomePod Indoor Climate**.
5. Enter one HomePod room or zone label per line. The displayed names become
   lowercase API keys: `Living Room` becomes `living_room`.

For a manual test before installing through HACS, copy
`custom_components/homepod_indoor_climate` into Home Assistant's
`/config/custom_components/` directory, restart Home Assistant, and continue
from step 4.

Use a distinct label for each HomePod you want weighted independently. For
example, use `Living Room East` and `Living Room West` rather than submitting
both devices under the same key.

## Authentication

Create a dedicated, non-administrator Home Assistant user for this bridge, log
in as that user, and create a long-lived access token from its profile. In the
integration options, select that user under **Only accept this Home Assistant
user**.

The receiver is a normal authenticated Home Assistant API view. Requests need:

```http
Authorization: Bearer YOUR_LONG_LIVED_ACCESS_TOKEN
Content-Type: application/json
```

The token is not stored by this integration. Home Assistant validates it before
the request reaches the bridge. The optional user restriction ensures that even
another valid Home Assistant user's token cannot submit data to this bridge.

**Accept submissions only from the local network** is enabled by default. Keep
it enabled and use Home Assistant's LAN URL in the Apple Home automation. A Home
Assistant proxy configuration that reports a public client address will be
rejected while this option is enabled.

## Apple Home automation

Expose the integration's **Refresh** switch through Home Assistant's HomeKit
Bridge. Then, in the Apple Home app on an iPhone or iPad:

1. Create an automation for **An Accessory is Controlled**.
2. Select the HomePod Indoor Climate **Refresh** switch and trigger when it
   turns on.
3. Choose **Convert to Shortcut**.
4. Read the current temperature and humidity from each HomePod.
5. Add **Get Contents of URL** for each configured room.
6. Use `POST`, set the two headers above, choose a JSON request body, and submit:

```json
{
  "room": "living_room",
  "temperature_c": 20.4,
  "humidity": 47
}
```

The endpoint is:

```text
http://HOME_ASSISTANT_LAN_ADDRESS:8123/api/homepod_indoor_climate/ENTRY_ID/readings
```

You do not need to hunt for `ENTRY_ID`: open the integration's **Refresh**
switch or **Last Submission** sensor and copy its `submission_path` attribute.
The `accepted_room_keys` attribute lists the exact room values to send.

Apple may pass measurements as `20.4 °C` and `47%`; the endpoint accepts those
forms as well as plain JSON numbers. Fahrenheit input is deliberately rejected
because the field is explicitly Celsius.

For advanced shortcuts, all rooms can be submitted in one request:

```json
{
  "readings": [
    {"room": "living_room", "temperature_c": 20.4, "humidity": 47},
    {"room": "bedroom", "temperature_c": 21.1, "humidity": 44}
  ]
}
```

## How refresh and freshness work

At the configured interval, Home Assistant pulses the **Refresh** switch on for
eight seconds. The Apple Home automation observes that change and posts the
latest readings. An accepted response turns the switch off immediately.

The default refresh interval is five minutes and the default stale threshold is
15 minutes. A late or failed Apple automation therefore cannot quietly leave an
old value in the whole-home average: stale room entities become unavailable,
the aggregate drops that room, and **Stale Readings** turns on.

## API responses

Successful submission:

```json
{"accepted": 1, "fresh_rooms": 1}
```

The endpoint rejects invalid tokens, unauthorized users, non-local requests
when local-only mode is enabled, unknown rooms, impossible values, oversized
bodies, and excessive request rates. Valid ranges are -40 to 60 °C and 0 to
100% relative humidity.

## Development validation

Pure conversion, validation, freshness, and aggregate logic is covered by the
tests in `tests/test_models.py`. The integration targets current Home Assistant
releases and Python 3.12 or newer.
