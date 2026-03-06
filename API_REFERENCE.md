# Beestat API - Comprehensive Reference
# Rev: 1.0
# Compiled: 2026-03-06

## 1. Base URL and Authentication

- **Base URL:** `https://api.beestat.io/`
- **Authentication:** API key passed as query parameter: `?api_key={YOUR_API_KEY}`
- **API Key Generation:** Users create API keys via `user.create_api_key` method in beestat. Keys are 40-character hex strings generated from `random_bytes(20)`. One API key per user maximum.
- **Rate Limit:** 30 requests per minute (developer-stated, subject to change).
- **Execution Timeout:** 5 seconds per request (server-side).
- **Response Compression:** gzip (`ob_gzhandler`).

## 2. Request Format

### Single Request
```
GET/POST https://api.beestat.io/?api_key={KEY}&resource={RESOURCE}&method={METHOD}&arguments={JSON_ENCODED_ARGS}
```

### Batch Request
Multiple API calls can be batched in a single HTTP request:
```
POST https://api.beestat.io/
Content-Type: application/json

{
  "batch": "[{\"resource\":\"thermostat\",\"method\":\"read\",\"alias\":\"thermostats\"},{\"resource\":\"sensor\",\"method\":\"read_id\",\"alias\":\"sensors\"}]",
  "api_key": "{KEY}"
}
```

Each call in a batch requires an `alias` field to identify its response. The API also accepts standard form POST or JSON body.

### Request Fields Per API Call
| Field | Description |
|-------|-------------|
| `resource` | API resource name (e.g., `thermostat`, `sensor`) |
| `method` | Method to call on the resource |
| `arguments` | JSON-encoded parameters object |
| `alias` | (batch only) Identifier for matching response |
| `bypass_cache_read` | Skip reading from cache |
| `bypass_cache_write` | Skip writing to cache |
| `clear_cache` | Clear cached data |

### Response Format
JSON object. Data is typically returned as objects keyed by the record's primary ID:
```json
{
  "data": {
    "12345": { ...record fields... },
    "12346": { ...record fields... }
  }
}
```
Responses include a `beestat-cached-until` header for cache management.

### Error Codes
- **1505** - Session expired
- **10000-10501** - Ecobee token issues
- **10201** - Missing thermostat_id (runtime_thermostat.read)
- **10202** - Missing timestamp (runtime_thermostat.read)
- **10203** - Invalid thermostat_id / unauthorized access
- **10204** - Invalid timestamp format
- **10205** - Query range exceeds 31 days
- **10401** - Missing sensor_id (runtime_sensor.read)
- **10402** - Missing timestamp (runtime_sensor.read)
- **10403** - Invalid sensor_id
- **10404** - Invalid timestamp format (runtime_sensor)
- **10405** - Query range exceeds 31 days (runtime_sensor)
- **10506** - OAuth error
- **10507** - OAuth error with description
- **10508** - ecobee authorization failure

---

## 3. API Resources and Methods

### 3.1 `thermostat`

**Exposed Methods:** `read_id` (private), `sync` (private), `read` (private), `update` (private), `set_reported_system_types` (private), `dismiss_alert` (private), `restore_alert` (private), `generate_profiles` (private), `generate_profile` (private), `get_metrics` (private)

**Cache:** `sync` = 180 seconds (3 minutes)

#### `thermostat.read_id`
Returns thermostat(s) for the authenticated user, keyed by thermostat_id.

**Response Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `thermostat_id` | int | Unique thermostat identifier |
| `name` | string | Thermostat name |
| `temperature` | float | Current temperature (divided by 10 from storage) |
| `temperature_unit` | string | Temperature unit (F/C) |
| `humidity` | int | Current humidity percentage |
| `setpoint_heat` | float | Heat setpoint |
| `setpoint_cool` | float | Cool setpoint |
| `first_connected` | string | First connection timestamp |
| `address_id` | int | Associated address ID |
| `property` | object | Property details (age, square_feet, stories, structure_type) |
| `filters` | object | Filter runtime usage data |
| `weather` | object | Current weather forecast data |
| `settings` | object | Thermostat settings (differential temps) |
| `time_zone` | string | Thermostat timezone |
| `program` | object | Climate program data (comfort profiles, schedule) |
| `system_type` | object | HVAC system configuration |
| `running_equipment` | array | Currently active equipment list |
| `alerts` | array | Active alerts with guid, text, dismissed status |
| `inactive` | int | Whether thermostat is inactive |
| `profile` | object | Temperature profile data |

**`system_type` sub-object:**
```json
{
  "reported": {
    "heat": {"equipment": "...", "stages": N},
    "auxiliary_heat": {"equipment": "...", "stages": N},
    "cool": {"equipment": "...", "stages": N}
  },
  "detected": {
    "heat": {"equipment": "...", "stages": N},
    "auxiliary_heat": {"equipment": "...", "stages": N},
    "cool": {"equipment": "...", "stages": N}
  }
}
```

**`running_equipment` values:** List of currently running equipment strings. Maps from ecobee `equipment_status` field. Includes items like: `compressor_cool_1`, `compressor_cool_2`, `compressor_heat_1`, `compressor_heat_2`, `auxiliary_heat_1`, `auxiliary_heat_2`, `fan`, `humidifier`, `dehumidifier`, `ventilator`, `economizer`.

#### `thermostat.read`
Same as `read_id` but with attribute filtering support. Accepts `$attributes` and `$columns` parameters.

#### `thermostat.sync`
Forces synchronization of all thermostats for the current user with ecobee. Uses database locking to prevent concurrent syncs. Skips in demo mode.

**Parameters:** None
**Returns:** boolean
**Cache:** 180 seconds

#### `thermostat.update`
Updates thermostat with merged generated columns.

**Parameters:** `$attributes` - fields to update

#### `thermostat.set_reported_system_types`
**Parameters:**
- `thermostat_id` (int)
- `system_types` (object) - with `heat`, `auxiliary_heat`, `cool` modes, each containing `equipment` and `stages`

#### `thermostat.dismiss_alert` / `thermostat.restore_alert`
**Parameters:**
- `thermostat_id` (int)
- `guid` (string) - alert GUID

#### `thermostat.generate_profile`
**Parameters:** `thermostat_id` (int)
Generates temperature profile from runtime data. Requires 365+ days of data.

#### `thermostat.get_metrics`
**Parameters:**
- `thermostat_id` (int)
- `attributes` (object) - comparison filters (radius, property characteristics)

---

### 3.2 `sensor`

**Exposed Methods:** `read_id` (private), `sync` (private)

**Cache:** `sync` = 180 seconds

#### `sensor.read_id`
Returns sensors for the authenticated user. Filters to supported types only.

**Supported Sensor Types:** `ecobee3_remote_sensor`, `thermostat`, `monitor_sensor`, `control_sensor`

**Response Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `sensor_id` | int | Unique sensor identifier |
| `type` | string | Sensor type |
| `capability` | array | Sensor capabilities (temperature, humidity, occupancy) |
| `name` | string | Sensor name |
| `thermostat_id` | int | Parent thermostat ID |
| `in_use` | boolean | Whether sensor is active |
| `inactive` | int | Whether sensor is inactive |

#### `sensor.sync`
Synchronizes all sensors for the current user. Uses database locking. Calls `ecobee_sensor.sync()` internally.

**Parameters:** None
**Returns:** boolean

---

### 3.3 `runtime_thermostat`

**Exposed Methods:** `read` (private)

**Cache:** `read` = 900 seconds (15 minutes)

#### `runtime_thermostat.read`
Returns 5-minute interval runtime data for a thermostat.

**Parameters (in `arguments`):**
| Parameter | Required | Description |
|-----------|----------|-------------|
| `thermostat_id` | Yes | Thermostat to query |
| `timestamp` | Yes | Time filter with operator |

**Timestamp Operators:** `>`, `>=`, `<`, `<=`, `between`
**Max Range:** 31 days

**Example:**
```json
{
  "thermostat_id": 12345,
  "timestamp": {
    "value": ["2026-01-01", "2026-01-31"],
    "operator": "between"
  }
}
```

**Response Fields (per 5-minute interval):**
| Field | Type | Description |
|-------|------|-------------|
| `thermostat_id` | int | Thermostat identifier |
| `timestamp` | string | ISO 8601 timestamp (UTC) |
| `compressor_mode` | string | Current compressor mode |
| `compressor_1` | int | Compressor stage 1 runtime (seconds in interval) |
| `compressor_2` | int | Compressor stage 2 runtime |
| `auxiliary_heat_1` | int | Aux heat stage 1 runtime |
| `auxiliary_heat_2` | int | Aux heat stage 2 runtime |
| `fan` | int | Fan runtime |
| `accessory_type` | string | Type of accessory |
| `accessory` | int | Accessory runtime |
| `system_mode` | string | System mode |
| `indoor_temperature` | float | Indoor temp (stored /10, returned as float) |
| `indoor_humidity` | float | Indoor humidity |
| `outdoor_temperature` | float | Outdoor temp |
| `outdoor_humidity` | float | Outdoor humidity |
| `event` | string | Current event text (e.g., "hold", "vacation") |
| `climate` | string | Current climate/comfort profile name |
| `setpoint_cool` | float | Cool setpoint |
| `setpoint_heat` | float | Heat setpoint |

**Note:** `event` and `climate` fields are resolved from `runtime_thermostat_text` table (text normalization). The raw fields are `event_runtime_thermostat_text_id` and `climate_runtime_thermostat_text_id`.

---

### 3.4 `runtime_sensor`

**Exposed Methods:** `read` (private)

**Cache:** `read` = 900 seconds (15 minutes)

#### `runtime_sensor.read`
Returns 5-minute interval runtime data for a sensor.

**Parameters (in `arguments`):**
| Parameter | Required | Description |
|-----------|----------|-------------|
| `sensor_id` | Yes | Sensor to query |
| `timestamp` | Yes | Time filter with operator |

**Timestamp Operators:** `>`, `>=`, `<`, `<=`, `between`
**Max Range:** 31 days

**Response Fields (per 5-minute interval):**
| Field | Type | Description |
|-------|------|-------------|
| `sensor_id` | int | Sensor identifier |
| `timestamp` | string | ISO 8601 timestamp (UTC) |
| `temperature` | float | Temperature (stored /10, returned as float) |
| `occupancy` | int | Occupancy detected (0/1) |
| `air_pressure` | float | Air pressure |
| `air_quality` | float | Air quality (normalized 0-100 from 0-350 scale) |
| `air_quality_accuracy` | int | Air quality accuracy level |
| `voc_concentration` | float | VOC concentration in PPM |
| `co2_concentration` | float | CO2 concentration |

**Note:** Air quality sensors (IAQ, VOC, CO2) require ecobee Premium or SmartSensor with air quality.

---

### 3.5 `runtime_thermostat_summary`

**Exposed Methods:** `read_id` (private), `sync` (private)

#### `runtime_thermostat_summary.read_id`
Returns daily aggregated runtime summaries for a thermostat.

**Response Fields (per day):**
| Field | Type | Description |
|-------|------|-------------|
| `runtime_thermostat_summary_id` | int | Unique row ID (database key, not meaningful) |
| `date` | string | Date (YYYY-MM-DD) |
| `thermostat_id` | int | Thermostat identifier |
| `count` | int | Number of 5-min intervals in day |
| `avg_outdoor_temperature` | float | Average outdoor temp |
| `min_outdoor_temperature` | float | Minimum outdoor temp (null if no data) |
| `max_outdoor_temperature` | float | Maximum outdoor temp (null if no data) |
| `avg_indoor_temperature` | float | Average indoor temp |
| `avg_outdoor_humidity` | float | Average outdoor humidity |
| `avg_indoor_humidity` | float | Average indoor humidity |
| `sum_fan` | int | Total fan runtime (seconds) |
| `sum_compressor_cool_1` | int | Stage 1 cooling runtime (seconds) |
| `sum_compressor_cool_2` | int | Stage 2 cooling runtime (seconds) |
| `sum_compressor_heat_1` | int | Stage 1 heat pump runtime (seconds) |
| `sum_compressor_heat_2` | int | Stage 2 heat pump runtime (seconds) |
| `sum_auxiliary_heat_1` | int | Stage 1 aux heat runtime (seconds) |
| `sum_auxiliary_heat_2` | int | Stage 2 aux heat runtime (seconds) |
| `sum_humidifier` | int | Humidifier runtime (seconds) |
| `sum_dehumidifier` | int | Dehumidifier runtime (seconds) |
| `sum_ventilator` | int | Ventilator runtime (seconds) |
| `sum_economizer` | int | Economizer runtime (seconds) |
| `sum_heating_degree_days` | float | Heating degree days (base 65F) |
| `sum_cooling_degree_days` | float | Cooling degree days (base 65F) |

**Temperature Storage:** All temperatures stored multiplied by 10; `read()` divides by 10. INF/-INF values converted to null.

**Degree Day Calculation:** Uses 65F (650 stored) as base. Each 5-minute interval contributes 5/1440 of a degree day.

---

### 3.6 `ecobee_thermostat`

**Exposed Methods:** `read_id` (private), `sync` (private)

#### `ecobee_thermostat.read_id`
Returns raw ecobee thermostat data (less normalized than `thermostat.read_id`).

**Response Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `ecobee_thermostat_id` | int | Internal ID |
| `identifier` | string | Ecobee device identifier |
| `name` | string | Thermostat name |
| `model_number` | string | Device model |
| `utc_time` | string | Last UTC time from device |
| `runtime` | object | Runtime data from ecobee |
| `extended_runtime` | object | Extended runtime data |
| `electricity` | object | Electricity data |
| `settings` | object | All ecobee settings |
| `location` | object | Location data |
| `program` | object | Program/schedule data |
| `events` | array | Active events (holds, vacations) |
| `device` | object | Device info |
| `technician` | object | Technician info |
| `utility` | object | Utility info |
| `management` | object | Management info |
| `alerts` | array | Device alerts |
| `weather` | object | Weather data |
| `house_details` | object | House details |
| `oem_cfg` | object | OEM configuration |
| `equipment_status` | string | Raw equipment status string |
| `notification_settings` | object | Notification preferences |
| `privacy` | object | Privacy settings |
| `version` | object | Firmware version |
| `remote_sensors` | array | Connected remote sensors |
| `audio` | object | Audio settings |
| `inactive` | int | Inactive flag |

#### `ecobee_thermostat.sync`
Full synchronization with ecobee API. Retrieves all thermostat data with extensive include parameters. Handles:
- Authorization failures by filtering inaccessible identifiers
- Temperature validation: -10F to 120F range
- Humidity validation: 0-100%
- Equipment detection based on runtime history
- Weather condition mapping
- Alert generation (low differential warnings)

---

### 3.7 `runtime`

**Exposed Methods:** `sync` (private), `download` (private), `download_glenwood_report` (private)

**Cache:** `sync` = 300 seconds (5 minutes)

#### `runtime.sync`
Synchronizes runtime data for a thermostat (both thermostat and sensor data). Determines whether to sync forwards (recent data) or backwards (historical backfill).

**Parameters:**
- `thermostat_id` (int, optional) - specific thermostat, or all if omitted

**Sync Strategy:**
- **Forwards:** From last recorded point to now (with 3-hour overlap for ecobee reliability)
- **Backwards:** Historical backfill in weekly chunks

**Data Interval:** 5-minute intervals from ecobee `runtimeReport` endpoint.

#### `runtime.download`
Exports runtime data as CSV.

**Parameters:**
- `thermostat_id` (int)
- `download_begin` (string) - Start timestamp
- `download_end` (string) - End timestamp

---

### 3.8 `user`

**Exposed Methods (private):** `read_id`, `update_setting`, `log_out`, `sync_patreon_status`, `unlink_patreon_account`, `create_api_key`, `recycle_api_key`, `delete_api_key`, `session_read_id`

**Exposed Methods (public):** `force_log_in`

#### `user.read_id`
Returns user info (password field stripped).

**Response Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `user_id` | int | User identifier |
| `username` | string | Username |
| `anonymous` | int | Whether anonymous user |
| `settings` | object | User settings (JSON) |
| `sync_status` | object | Sync timestamps per resource |
| `patreon_status` | object | Patreon membership data |

#### `user.create_api_key`
Generates a new 40-character API key. Maximum one key per user.

#### `user.recycle_api_key`
Regenerates the existing API key with a new value.

#### `user.delete_api_key`
Soft-deletes the API key.

#### `user.update_setting`
**Parameters:**
- `key` (string) - Supports dotted notation (e.g., "parent.child.value")
- `value` (mixed) - New setting value

---

### 3.9 `ecobee`

**Exposed Methods (public):** `authorize`, `initialize`

#### `ecobee.authorize`
Initiates OAuth flow. Redirects to ecobee authorization page with `smartRead` scope.

**Parameters:**
- `redirect` (string, optional) - Post-auth redirect URL

#### `ecobee.initialize`
Completes OAuth callback. Obtains tokens, creates/links user account.

**Parameters:**
- `code` (string) - Authorization code
- `state` (string) - CSRF state parameter
- `error` (string) - Error code if failed
- `error_description` (string) - Error description

---

### 3.10 `address`

**Exposed Methods:** `read_id` (private)

Returns address information for thermostats.

**Response Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `address_id` | int | Address identifier |
| `line_1` | string | Street address |
| `locality` | string | City |
| `administrative_area` | string | State/province |
| `postal_code` | string | ZIP/postal code |
| `latitude` | float | Latitude |
| `longitude` | float | Longitude |

---

### 3.11 `announcement`

**Exposed Methods:** `read_id` (public - no auth required)

**Note:** `user_locked` = false. This is a public resource.

Returns system announcements.

---

### 3.12 `floor_plan`

**Exposed Methods (private):** `read_id`, `update`, `create`, `delete`

Full CRUD for floor plan objects.

---

### 3.13 `profile`

**Exposed Methods (private):** `generate`
**Exposed Methods (public):** `read_id`

#### `profile.generate`
Generates temperature profiles from runtime data.

**Parameters:**
- `thermostat_id` (int)
- `debug` (boolean, optional)

**Requirements:** 365+ days of runtime data, minimum 5 data points, minimum 2 samples per temperature range.

---

### 3.14 `ecobee_sensor`

**Exposed Methods:** `read_id` (private)

Returns raw ecobee sensor data.

**Response Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `ecobee_sensor_id` | int | Internal ID |
| `ecobee_thermostat_id` | int | Parent thermostat |
| `identifier` | string | Ecobee identifier |
| `name` | string | Sensor name |
| `type` | string | Sensor type |
| `code` | string | Sensor code |
| `in_use` | boolean | Active status |
| `capability` | array | Capabilities list |
| `inactive` | int | Inactive flag |

---

### 3.15 `ecobee_token`

Not directly exposed. Manages OAuth tokens internally.

---

### 3.16 Other Resources (Internal/Admin)

These exist in the codebase but are not useful for a HA integration:

| Resource | Purpose |
|----------|---------|
| `ecobee_api_cache` | Caches ecobee API responses |
| `ecobee_api_log` | Logs ecobee API calls |
| `external_api` | Base class for external API calls |
| `external_api_cache` | External API response cache |
| `external_api_log` | External API call logs |
| `mailgun` / `mailgun_api_cache` / `mailgun_api_log` | Email service |
| `patreon` / `patreon_api_cache` / `patreon_api_log` / `patreon_initialize` / `patreon_token` | Patreon integration |
| `smarty_streets` / `smarty_streets_api_cache` / `smarty_streets_api_log` | Address verification |
| `stripe` / `stripe_api_cache` / `stripe_api_log` / `stripe_event` / `stripe_payment_link` | Payment processing |
| `runtime_thermostat_text` | Text normalization table (event/climate names) |

---

## 4. Data Flow and Sync Architecture

### How Data Gets Updated
1. **Active sync:** When a user has beestat open in a browser, data syncs actively.
2. **Periodic sync:** Beestat periodically syncs in the background (less frequent).
3. **Manual sync:** Call `thermostat.sync` and/or `sensor.sync` to force a sync from ecobee.
4. **Runtime sync:** Call `runtime.sync` to fetch latest 5-minute interval data.

### Recommended Polling Strategy for HA Integration
1. Call `thermostat.sync` to ensure fresh data (cached 3 min server-side).
2. Call `thermostat.read_id` for current thermostat state.
3. Call `sensor.read_id` for sensor list.
4. Call `runtime_thermostat.read` with recent timestamp for latest runtime intervals.
5. Call `runtime_sensor.read` per sensor for latest sensor data.
6. For daily summaries, call `runtime_thermostat_summary.read_id` periodically.

### Batch Optimization
Use batch requests to combine multiple calls in one HTTP request:
```json
{
  "batch": "[{\"resource\":\"thermostat\",\"method\":\"sync\",\"alias\":\"sync\"},{\"resource\":\"thermostat\",\"method\":\"read_id\",\"alias\":\"thermostats\"},{\"resource\":\"sensor\",\"method\":\"read_id\",\"alias\":\"sensors\"}]",
  "api_key": "{KEY}"
}
```

---

## 5. Key Implementation Notes for HA Integration

### Temperature Values
- All temperatures in the database are stored multiplied by 10 (e.g., 725 = 72.5F).
- The API `read` methods divide by 10 before returning.
- `temperature_unit` field on thermostat tells you F or C.

### Air Quality Normalization
- Raw air quality from ecobee: 0-350 scale.
- Beestat normalizes to 0-100 percentage (higher = better).

### Equipment Status Mapping
The `running_equipment` array on `thermostat.read_id` maps from ecobee's `equipment_status` string. Possible values:
- `compressor_cool_1`, `compressor_cool_2`
- `compressor_heat_1`, `compressor_heat_2`
- `auxiliary_heat_1`, `auxiliary_heat_2`
- `fan`
- `humidifier`, `dehumidifier`
- `ventilator`, `economizer`

### Timestamp Handling
- All timestamps assume UTC if no timezone specified.
- Returned in ISO 8601 format.
- The thermostat's `time_zone` field gives the local timezone.

### Caching Behavior
Server-side caching means repeated calls within the cache window return stale data:
| Method | Cache Duration |
|--------|---------------|
| `thermostat.sync` | 180s (3 min) |
| `sensor.sync` | 180s (3 min) |
| `runtime.sync` | 300s (5 min) |
| `runtime_thermostat.read` | 900s (15 min) |
| `runtime_sensor.read` | 900s (15 min) |

### Access Control
- Methods marked `private` require authentication (API key).
- Methods marked `public` do not require authentication.
- `user_locked` resources filter data to the authenticated user automatically.

---

## 6. Complete Method Index

| Resource | Method | Access | Cache | Description |
|----------|--------|--------|-------|-------------|
| `thermostat` | `read_id` | private | - | Get user's thermostats |
| `thermostat` | `read` | private | - | Get thermostats with filters |
| `thermostat` | `sync` | private | 180s | Sync from ecobee |
| `thermostat` | `update` | private | - | Update thermostat |
| `thermostat` | `set_reported_system_types` | private | - | Set HVAC system types |
| `thermostat` | `dismiss_alert` | private | - | Dismiss an alert |
| `thermostat` | `restore_alert` | private | - | Restore an alert |
| `thermostat` | `generate_profile` | private | - | Generate temp profile |
| `thermostat` | `generate_profiles` | private | - | Generate all profiles |
| `thermostat` | `get_metrics` | private | - | Compare against peers |
| `sensor` | `read_id` | private | - | Get user's sensors |
| `sensor` | `sync` | private | 180s | Sync sensors from ecobee |
| `runtime_thermostat` | `read` | private | 900s | Get 5-min runtime data |
| `runtime_sensor` | `read` | private | 900s | Get 5-min sensor data |
| `runtime_thermostat_summary` | `read_id` | private | - | Get daily summaries |
| `runtime_thermostat_summary` | `sync` | private | - | Sync summary data |
| `runtime` | `sync` | private | 300s | Sync all runtime data |
| `runtime` | `download` | private | - | Export CSV |
| `ecobee_thermostat` | `read_id` | private | - | Get raw ecobee data |
| `ecobee_thermostat` | `sync` | private | - | Full ecobee sync |
| `ecobee_sensor` | `read_id` | private | - | Get raw sensor data |
| `user` | `read_id` | private | - | Get user info |
| `user` | `update_setting` | private | - | Update user setting |
| `user` | `log_out` | private | - | Log out |
| `user` | `create_api_key` | private | - | Create API key |
| `user` | `recycle_api_key` | private | - | Regenerate API key |
| `user` | `delete_api_key` | private | - | Delete API key |
| `user` | `session_read_id` | private | - | Get API sessions |
| `user` | `sync_patreon_status` | private | - | Sync Patreon status |
| `user` | `unlink_patreon_account` | private | - | Unlink Patreon |
| `user` | `force_log_in` | public | - | Admin login |
| `address` | `read_id` | private | - | Get address data |
| `announcement` | `read_id` | public | - | Get announcements |
| `floor_plan` | `read_id` | private | - | Get floor plans |
| `floor_plan` | `create` | private | - | Create floor plan |
| `floor_plan` | `update` | private | - | Update floor plan |
| `floor_plan` | `delete` | private | - | Delete floor plan |
| `profile` | `generate` | private | - | Generate temp profile |
| `profile` | `read_id` | public | - | Get profile data |
| `ecobee` | `authorize` | public | - | Start OAuth flow |
| `ecobee` | `initialize` | public | - | Complete OAuth flow |
