# BuzzBridge - Development Notes
# Rev: 5.0

## Project Overview
Custom Home Assistant integration that pulls ecobee thermostat data from the Beestat API
and exposes it as HA sensors. Bridges the gap left by ecobee closing their developer API.

## Architecture
- Two DataUpdateCoordinators: Fast (5 min) and Slow (30 min)
- All API calls use batch requests (multiple calls per HTTP request)
- BeestatApi client handles auth, errors, rate limits
- Config flow for API key entry, options flow for poll intervals
- Reauth flow and reconfigure flow for API key changes
- Platforms: sensor, binary_sensor, button, diagnostics
- Typed runtime_data pattern (BuzzBridgeData dataclass)
- Shared base entity class (entity.py)
- Device cleanup (async_remove_config_entry_device) prevents removing active devices
- Repair issues for device discovery events

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
  __init__.py      - Integration setup, naming migration, options listener, device cleanup
  api.py           - BeestatApi async HTTP client with batch support
  config_flow.py   - Config flow + reauth + reconfigure + options flow
  coordinator.py   - FastPollCoordinator + SlowPollCoordinator + boost mode
  entity.py        - BuzzBridgeEntity base class, BuzzBridgeData dataclass, type alias
  sensor.py        - All sensor entities (thermostat, AQ, runtime, remote, base)
  binary_sensor.py - Online + occupancy + participating
  button.py        - Boost polling button
  air_quality.py   - AQ threshold lookups (CO2, VOC, score, accuracy)
  calculations.py  - Calculated sensor functions (efficiency, comfort, etc.)
  const.py         - All constants, thresholds, equipment maps, model names
  diagnostics.py   - Diagnostic data export with sensitive field redaction
  manifest.json    - HA integration manifest
  strings.json     - All UI strings, entity translations, issue strings, exception strings
  icons.json       - Entity icon definitions (translation-based)
  translations/en.json - English translations (copy of strings.json)
tools/
  beestat_dump.sh      - API data dump for developer analysis
  ha_diagnostic.sh     - HA state/registry collector
  entity_audit.py      - Naming convention validator
  beestat_live.sh      - Real-time API monitor
  validate_install.sh  - Pre-install checker
  list_entities.py     - Entity ID lister
  README.md            - Tool documentation
tests/
  conftest.py      - Shared fixtures, mock data
  test_config_flow.py - Config flow test coverage
  test_api.py      - API client tests
  test_coordinator.py - Coordinator tests
  test_diagnostics.py - Diagnostics tests
  test_calculations.py - Calculation function tests
```

## HA Quality Scale Compliance
### Bronze
- **config-flow**: ConfigFlow with validation ✓
- **test-before-configure**: API key validated before entry creation ✓
- **unique-config-entry**: SHA256 hash unique ID + _abort_if_unique_id_configured ✓
- **config-flow-test-coverage**: Full test suite ✓
- **runtime-data**: Typed BuzzBridgeData dataclass via entry.runtime_data ✓
- **test-before-setup**: async_config_entry_first_refresh raises ConfigEntryNotReady ✓
- **appropriate-polling**: Configurable 3-60 min, respects server cache ✓
- **entity-unique-id**: All entities have unique IDs ✓
- **has-entity-name**: All entities set _attr_has_entity_name = True ✓
- **common-modules**: entity.py base class, coordinator.py ✓

### Silver
- **reauthentication-flow**: async_step_reauth + reauth_confirm ✓
- **config-entry-unloading**: async_unload_entry ✓
- **log-when-unavailable**: Single warning on failure, single info on recovery ✓
- **entity-unavailable**: CoordinatorEntity handles automatically ✓
- **parallel-updates**: PARALLEL_UPDATES = 0 on all platforms ✓
- **test-coverage**: Comprehensive test suite ✓

### Gold
- **devices**: DeviceInfo with identifiers, model, manufacturer, firmware ✓
- **diagnostics**: async_redact_data with comprehensive key list ✓
- **entity-category**: EntityCategory.DIAGNOSTIC on online and filter sensors ✓
- **entity-device-class**: CO2, VOC, temperature, humidity device classes ✓
- **entity-disabled-by-default**: Weather sensors disabled ✓
- **entity-translations**: All entities use _attr_translation_key + strings.json ✓
- **icon-translations**: icons.json with all entity icons ✓
- **exception-translations**: Exception messages in strings.json ✓
- **reconfiguration-flow**: async_step_reconfigure ✓
- **repair-issues**: issue_registry for device discovery ✓
- **stale-devices**: async_remove_config_entry_device ✓
- **dynamic-devices**: Coordinator detects new thermostats ✓

### Platinum
- **async-dependency**: aiohttp only ✓
- **inject-websession**: async_get_clientsession ✓

### Not Yet Implemented
- **brands**: Logo/icon assets (needs designer)
- **strict-typing**: Full mypy strict mode
- **discovery**: N/A (cloud API, not local device)
- **docs-removal-instructions**: In README troubleshooting section

## Progress Log
- 2026-03-06: Project initialized, git repo created, connected to GitHub
- 2026-03-06: Comprehensive API research completed - see API_REFERENCE.md
- 2026-03-06: v1.0 build complete — all files written and code reviewed
- 2026-03-06: v1.1 — Null-safety fixes, resilience audit, INSTALL.md
- 2026-03-06: v1.2 — HA quality scale upgrades (diagnostics, reauth, has_entity_name, device cleanup)
- 2026-03-06: v1.3 — Comprehensive quality scale overhaul:
  - entity.py base class + BuzzBridgeData runtime_data dataclass
  - runtime_data pattern (replaced hass.data[DOMAIN])
  - Entity translations (_attr_translation_key + strings.json entity section)
  - icons.json for all entity icons (removed hardcoded _attr_icon)
  - CO2/VOC proper device classes (SensorDeviceClass.CO2, VOLATILE_ORGANIC_COMPOUNDS_PARTS)
  - Reconfigure flow (async_step_reconfigure)
  - Repair issues (replaced persistent_notification with issue_registry)
  - Log-when-unavailable state tracking in both coordinators
  - Exception translation strings
  - Comprehensive test suite
  - Gold-tier documentation (data update, supported devices/functions, examples, troubleshooting)
- 2026-03-06: v1.7.1 — Data fixes (differential x10 encoding, removed remote sensor humidity, participating binary sensor, source attribute)
- 2026-03-06: v1.7.3 — Standardized naming convention:
  - Four device types: Thermostat, Base, Remote (+ Premium variant)
  - Device names: {prefix} {type} {room}
  - Entity IDs: {domain}.{prefix}_{type}_{room}_{measurement}
  - Two-phase migration in __init__.py
  - SENSOR_TYPE_MODELS const for base sensor model name
- 2026-03-06: v1.7.4 — Bug fixes from code review:
  - Fixed None/empty name handling (.get("name") or fallback)
  - Fixed EntityCategory import in binary_sensor.py
  - Moved datetime import to top-level in sensor.py
  - Eliminated duplicate dict lookups in filter sensor
  - Fixed name_by_user clearing on every restart
  - Created tools/ diagnostic directory
