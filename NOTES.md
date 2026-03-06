# BuzzBridge - Development Notes
# Rev: 3.0

## Project Overview
Custom Home Assistant integration that pulls ecobee thermostat data from the Beestat API
and exposes it as HA sensors. Bridges the gap left by ecobee closing their developer API.

## Architecture
- Two DataUpdateCoordinators: Fast (5 min) and Slow (30 min)
- All API calls use batch requests (multiple calls per HTTP request)
- BeestatApi client handles auth, errors, rate limits
- Config flow for API key entry, options flow for poll intervals
- Platforms: sensor, binary_sensor, button, diagnostics
- Reauth flow for expired API keys
- Device cleanup (async_remove_config_entry_device) prevents removing active devices

## Beestat API Details
- Base URL: https://api.beestat.io/
- Auth: API key as query parameter `?api_key={KEY}`
- Rate limit: ~30 requests/minute (batch counts as 1)
- See API_REFERENCE.md for complete endpoint documentation
- Key endpoints:
  - `thermostat.read_id` - thermostat data, running_equipment, alerts
  - `ecobee_thermostat.read_id` - raw ecobee data (events, settings, runtime, weather)
  - `sensor.read_id` - sensor list with capabilities
  - `runtime_thermostat_summary.read_id` - daily aggregated runtime summaries
  - `thermostat.sync` / `sensor.sync` / `runtime.sync` - force sync from ecobee
- Batch API: multiple calls in single HTTP request via `batch` param
- Server-side caching: sync=180s, runtime reads=900s

## Security
- API key entered via config flow UI prompt during installation
- Stored in HA .storage (encrypted config entries)
- Validated as 40-char hex string before API call
- Uses HA's shared aiohttp session (not custom sessions)
- Auth failures raise ConfigEntryAuthFailed (disables entry, prompts re-auth)

## File Structure
```
custom_components/buzzbridge/
  __init__.py      - Integration setup, coordinators, options listener
  api.py           - BeestatApi async HTTP client with batch support
  config_flow.py   - Config flow (API key) + Options flow (poll intervals)
  coordinator.py   - FastPollCoordinator + SlowPollCoordinator + boost mode
  sensor.py        - All sensor entities (thermostat, AQ, runtime, remote)
  binary_sensor.py - Occupancy + online status
  button.py        - Boost polling button
  air_quality.py   - AQ threshold lookups (CO2, VOC, score, accuracy)
  calculations.py  - Calculated sensor functions (efficiency, comfort, etc.)
  const.py         - All constants, thresholds, equipment maps
  manifest.json    - HA integration manifest
  strings.json     - UI strings for config/options flows
  diagnostics.py   - Diagnostic data export with sensitive field redaction
  translations/en.json - English translations
```

## Code Review Notes
- api.py: Batch call definitions are module-level constants (not rebuilt per poll)
- api.py: Catches TimeoutError, 429 rate limits, validates response is dict
- coordinator.py: Uses dt_util.utcnow() for boost timer (not naive datetime)
- coordinator.py: is_boosted is a pure property (no side effects)
- coordinator.py: Device discovery uses None sentinel (not empty set)
- config_flow.py: Uses HA's shared session, SHA256 hash for unique ID
- calculations.py: Uses explicit None checks (not falsy `not x` which breaks on 0)
- All platforms: PARALLEL_UPDATES = 0, _attr_has_entity_name = True
- binary_sensor.py: EntityCategory.DIAGNOSTIC on online sensor
- sensor.py: EntityCategory.DIAGNOSTIC on filter sensor
- diagnostics.py: Redacts API keys, tokens, addresses, serial numbers, MAC addresses
- config_flow.py: Reauth flow (async_step_reauth → reauth_confirm)
- __init__.py: async_remove_config_entry_device blocks removal of active devices

## HA Quality Scale Compliance
- **has_entity_name**: All entity classes use `_attr_has_entity_name = True`
- **entity_category**: Diagnostic entities marked with `EntityCategory.DIAGNOSTIC`
- **PARALLEL_UPDATES**: Set to 0 on all coordinator-based platforms
- **Diagnostics**: Full coordinator data export with `async_redact_data`
- **Reauthentication**: `ConfigEntryAuthFailed` triggers reauth flow in UI
- **Device cleanup**: `async_remove_config_entry_device` prevents removing active devices

## Progress Log
- 2026-03-06: Project initialized, git repo created, connected to GitHub
- 2026-03-06: Comprehensive API research completed - see API_REFERENCE.md
- 2026-03-06: v1.0 build complete — all files written and code reviewed
- 2026-03-06: v1.1 — Null-safety fixes, resilience audit, INSTALL.md
- 2026-03-06: v1.2 — HA quality scale upgrades (diagnostics, reauth, has_entity_name, device cleanup)
