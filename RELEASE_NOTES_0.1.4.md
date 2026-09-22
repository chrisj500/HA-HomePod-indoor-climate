# HomePod Indoor Climate 0.1.4

This release closes the remaining diagnostics blind spot around HTTP authentication.

## Changes

- Records every request that reaches the HomePod readings route before Bearer-token validation.
- Distinguishes:
  - no Authorization header
  - malformed Authorization header
  - wrong authorization scheme
  - invalid Bearer token
  - Home Assistant user authentication restrictions
  - integration-level user restriction
  - remote-source rejection
  - accepted submissions
- Records whether the request source was local/private and whether it arrived during an active refresh pulse.
- Does not log or expose token contents.
- Keeps the endpoint protected with Home Assistant's normal long-lived access-token validation.
