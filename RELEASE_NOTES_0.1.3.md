# HomePod Indoor Climate 0.1.3

This release adds first-class refresh-path diagnostics so Home Assistant can
show where a failed HomePod update stopped instead of requiring repeated manual
Apple Home tests.

## Diagnostics added

- New **Refresh Diagnostics** diagnostic sensor.
- Distinguishes initial, scheduled, and manual refresh requests.
- Records whether each refresh completed by submission, timeout, manual off, or
  was superseded by another refresh.
- Tracks refresh counts, sequence numbers, timestamps, and completion latency.
- Tracks authenticated API requests reaching the integration, accepted and
  rejected requests, accepted room counts, ignored rooms, and whether the
  request arrived while a refresh pulse was active.
- Adds Home Assistant **Download diagnostics** support from the integration
  device/config-entry page.
- Diagnostics deliberately do not expose access tokens or the configured user
  identifier.

Home Assistant authentication failures that occur before the request reaches
the integration cannot be counted by the integration itself; downloaded
diagnostics state this limitation explicitly.
