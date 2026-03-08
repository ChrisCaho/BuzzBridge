# BuzzBridge
# Rev: 1.7.5

**A Home Assistant custom integration that bridges Beestat data into your smart home.**

## Why BuzzBridge?

If you use ecobee thermostats with Home Assistant, you've probably set them up through Apple HomeKit or the native ecobee integration. These work well for basic control — adjusting temperature, switching modes, reading the current state — but they operate over local or cloud connections that only expose a limited slice of what your thermostat actually knows. You won't see air quality readings, CO2 and VOC levels, equipment runtime breakdowns, filter status, degree days, or detailed remote sensor data. The ecobee app shows some of this, but there's no way to get it into HA for automations, dashboards, or long-term tracking.

[Beestat](https://beestat.io/) fills that gap. Created by Jon Ziebell, Beestat is a free, open-source analytics platform that connects to ecobee via OAuth and exposes a rich API with all the data ecobee collects — including the advanced metrics the official integrations leave out. This is especially valuable since ecobee closed its developer API to new registrations in March 2024, making Beestat one of the few remaining ways to access this data programmatically. BuzzBridge is the bridge between Beestat and Home Assistant: it polls the Beestat API on a configurable schedule, maps all that data into properly typed HA entities with device classes, translations, and air quality thresholds, and presents it alongside your existing ecobee controls. Your HomeKit or ecobee integration handles control; BuzzBridge handles visibility.

The goal is threefold: give your automations access to richer thermostat data (runtimes, setpoints, equipment status, hold state), add detailed sensor information to your thermostat dashboard cards beyond what HomeKit exposes, and surface air quality monitoring (CO2, VOC, and overall AQ score) from ecobee Premium thermostats — data that would otherwise be locked inside the ecobee app.

## Features

### Per Thermostat
- **Temperature & Humidity** — current readings, heat/cool setpoints
- **HVAC Mode** — auto, heat, cool, off
- **Running Equipment** — human-readable status (e.g., "Cooling Stage 1, Fan")
- **Hold Status** — type, hold temperatures, end time (with indefinite detection)
- **Fan Mode** — auto, on
- **Online Status** — connectivity monitoring

### Air Quality (ecobee Premium only)
- **Air Quality Score** — 0-100 (higher = better), with level/description/health guidance
- **CO2** — parts per million with EPA/OSHA-referenced thresholds
- **VOC** — parts per billion with health impact descriptions
- **Accuracy** — BME680 sensor calibration state (0-4)

#### Air Quality Levels

| CO2 (ppm) | Level | Guidance |
|-----------|-------|----------|
| ≤400 | Excellent | Fresh outdoor air levels |
| 401-700 | Good | Well-ventilated indoor space |
| 701-1000 | Fair | EPA recommended maximum. Consider ventilating. |
| 1001-1500 | Warning | Cognitive performance declines. Ventilate. |
| 1501-2500 | Poor | Drowsiness, headaches likely. |
| 2501-5000 | Dangerous | Approaching OSHA workplace limit. |
| >5000 | Critical | Leave the area immediately. |

| VOC (ppb) | Level | Guidance |
|-----------|-------|----------|
| ≤100 | Excellent | Very clean air |
| 101-400 | Good | Normal indoor levels |
| 401-800 | Fair | Common after cleaning, cooking, new furniture |
| 801-1500 | Warning | Short-term irritation possible. Ventilate. |
| 1501-2200 | Poor | Headaches, nausea, eye/throat irritation likely |
| >2200 | Dangerous | Dizziness, loss of coordination. Ventilate immediately. |

### Runtime & Efficiency (updated every 30 min)
- **Cooling/Heating/Fan Runtime Today** — in hours
- **Heating Degree Days** — energy demand metric (base 65°F)
- **Cooling Degree Days** — energy demand metric (base 65°F)

#### What are Degree Days?
Degree days measure how much heating or cooling demand exists based on outdoor temperature, using a base of 65°F (the temperature below which buildings typically need heating, above which they need cooling).

- If the average outdoor temp is 55°F → 10 Heating Degree Days (65 - 55 = 10)
- If the average outdoor temp is 80°F → 15 Cooling Degree Days (80 - 65 = 15)
- A mild 65°F day has 0 of both

Higher numbers = more energy needed. Useful for:
- Comparing energy use across days with different weather
- Detecting efficiency changes ("same degree days, more runtime = problem")
- Seasonal energy planning

### Calculated Sensors
- **Comfort Index** — 0-100% combining temperature (70% weight) and humidity (30% weight). In auto mode, 100% means the temperature is anywhere within the heat-cool setpoint range and humidity is 30-50%. In heat-only or cool-only mode, 100% means at or past the setpoint in the comfortable direction. The score degrades linearly as conditions move outside the comfort zone, reaching 0% at 5°F beyond the range or at extreme humidity.
- **Indoor/Outdoor Differential** — temperature difference showing insulation effectiveness

### Remote Sensors
- **Temperature** — for every ecobee remote sensor and base (thermostat-extracted) sensor
- **Occupancy** — motion detection as binary sensor
- **Participating** — whether the sensor is included in the thermostat's comfort average (diagnostic)

Remote sensors are split into two device types:
- **Remote** — standalone ecobee room sensors (model: Ecobee3 Remote Sensor)
- **Base** — the thermostat's built-in sensor, extracted as its own device (model: Ecobee3 Base Sensor - Extracted)

### Filter Status
- **Filter Runtime** — total hours since last change
- **Days Remaining** — estimated based on filter life setting

### Weather (disabled by default)
- **Outdoor Temperature** — from ecobee weather data
- **Outdoor Humidity** — from ecobee weather data

### Boost Polling
Each thermostat gets a **Boost Polling** button that switches polling from the configured interval (default 5 min) to every 60 seconds for 60 minutes, then automatically reverts. Useful for monitoring changes in real-time or debugging.

### Refresh Now
Each thermostat gets a **Refresh Now** button that triggers an immediate one-time refresh of all data (both fast and slow poll) without changing polling intervals. Useful for getting fresh data on demand after making changes.

## Prerequisites

1. An [ecobee](https://www.ecobee.com/) thermostat
2. A free [Beestat](https://beestat.io/) account linked to your ecobee
3. A Beestat API key (found at app.beestat.io → Menu → API Key)
4. Home Assistant 2025.1+

## Installation

### HACS (Recommended)
1. Open HACS in Home Assistant
2. Click the three dots menu → Custom repositories
3. Add `https://github.com/ChrisCaho/BuzzBridge` as an Integration
4. Search for "BuzzBridge" and install
5. Restart Home Assistant

### Manual
1. Copy the `custom_components/buzzbridge` folder to your HA `custom_components` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **BuzzBridge**
3. Enter your Beestat API key (40-character hex string)
4. Optionally set a **device name prefix** (default: "BuzzBridge"). This prefix is added to all device and entity names to distinguish them from your other integrations (e.g., "BuzzBridge Living Room"). Leave blank for no prefix.
5. All thermostats and sensors are discovered automatically
6. Configure poll intervals in integration options (Settings → Devices & Services → BuzzBridge → Configure)

### Poll Intervals
| Poll Type | Default | Range | Data |
|-----------|---------|-------|------|
| Fast | 5 min | 3-60 min | Thermostat state, sensors, air quality |
| Slow | 30 min | 3-60 min | Runtime summaries, degree days |

The Beestat API rate limit is ~30 requests/minute. Each poll uses a single batch API request regardless of how many thermostats you have.

## Device Discovery

BuzzBridge auto-discovers all thermostats on your Beestat account. When changes occur:

- **New thermostat added** → HA persistent notification + entities created automatically
- **Thermostat lost** → HA notification + entities become unavailable
- **Thermostat replaced with same name** → Entities auto-migrate to new device

## How It Works

BuzzBridge uses the Beestat public API to read your ecobee thermostat data. Beestat is a free, open-source analytics platform created by Jon Ziebell that is grandfathered into ecobee's API access (via OAuth — Beestat never sees your ecobee password).

The integration uses two DataUpdateCoordinators with batch API requests:
- **Fast poll**: syncs + reads thermostat state, sensors, and air quality in one HTTP request
- **Slow poll**: syncs + reads runtime summaries in one HTTP request

**BuzzBridge is read-only.** It cannot control your thermostat — it only provides visibility into data that HomeKit doesn't expose.

## Privacy

- Your Beestat API key is stored locally in Home Assistant (encrypted in `.storage`)
- No data is sent anywhere except to the Beestat API to retrieve your thermostat data
- BuzzBridge is fully open source — audit the code yourself

## Data Update Mechanism

BuzzBridge uses a dual-coordinator polling architecture. Both coordinators use batch API requests, meaning each poll cycle sends a single HTTP request to Beestat regardless of how many thermostats are on the account.

### Fast Poll (default: 5 minutes)
Fetches real-time thermostat data in one batch request:
- Current temperature and humidity
- Heat and cool setpoints
- HVAC mode, fan mode, running equipment
- Hold status (type, temperatures, end time)
- Air quality readings (CO2, VOC, AQ score, accuracy) on Premium models
- Remote sensor readings (temperature, humidity, occupancy)
- Filter runtime status
- Weather data from ecobee

### Slow Poll (default: 30 minutes)
Fetches daily summary data in one batch request:
- Cooling, heating, and fan runtime totals for the current day
- Heating and cooling degree days

### Configuring Poll Intervals
Both intervals are configurable via the Options flow: **Settings > Devices & Services > BuzzBridge > Configure**. The allowed range is 3 to 60 minutes for each. Changes take effect immediately without restarting Home Assistant.

### Boost Mode
Each thermostat exposes a **Boost Polling** button entity. Pressing it switches the fast poll interval to every 60 seconds for 60 minutes, then automatically reverts to the configured interval. Pressing the button again while boost is active resets the 60-minute timer. This is useful for monitoring real-time changes or debugging.

### Beestat Server Cache
The Beestat API applies server-side caching: sync responses are cached for 3 minutes and runtime summary reads for up to 15 minutes. As a result, data displayed in Home Assistant is typically 3-5 minutes behind real-time ecobee readings. Setting the fast poll interval below 3 minutes will not yield fresher data.

---

## Supported Devices

BuzzBridge supports all ecobee thermostat models available through Beestat:

| Model Code | Device Name | Notes |
|------------|-------------|-------|
| `apolloSmart` | ecobee SmartThermostat | |
| `aresSmart` | ecobee Smart Thermostat Premium | Includes air quality sensors (CO2, VOC, AQ score) |
| `nikeSmart` | ecobee Smart Thermostat Enhanced | |
| `vulcanSmart` | ecobee Smart Thermostat Essential | |
| `athenaSmart` | ecobee3 | |
| `idtSmart` | ecobee3 lite | |
| `corSmart` | Carrier Cor | |
| `siSmart` | ecobee Si | |

All ecobee remote sensors are also supported:
- **Remote sensors** — standalone room sensors (temperature and occupancy)
- **Base sensors** — the thermostat's built-in sensor, extracted as a separate device (temperature and occupancy)

Both remote and base sensors are automatically discovered and registered as child devices of their parent thermostat.

---

## Naming Convention

BuzzBridge uses a standardized naming convention for all devices and entities. Names are ordered from most common to least common, left to right.

### Device Names

| Device Type | Name Pattern | Example |
|-------------|-------------|---------|
| Thermostat | `{prefix} Thermostat {room}` | BuzzBridge Thermostat Home |
| Base Sensor | `{prefix} Base {room}` | BuzzBridge Base Home |
| Remote Sensor | `{prefix} Remote {room}` | BuzzBridge Remote Kitchen |

### Entity IDs

Entity IDs follow the pattern: `{domain}.{prefix}_{type}_{room}_{measurement}`

| Entity | Example Entity ID |
|--------|-------------------|
| Thermostat temperature | `sensor.buzzbridge_thermostat_home_temperature` |
| Thermostat HVAC mode | `sensor.buzzbridge_thermostat_home_hvac_mode` |
| Thermostat air quality | `sensor.buzzbridge_thermostat_studio_air_quality_score` |
| Thermostat online | `binary_sensor.buzzbridge_thermostat_home_online` |
| Remote sensor temp | `sensor.buzzbridge_remote_kitchen_temperature` |
| Remote occupancy | `binary_sensor.buzzbridge_remote_kitchen_occupancy` |
| Remote participating | `binary_sensor.buzzbridge_remote_kitchen_participating` |
| Base sensor temp | `sensor.buzzbridge_base_home_temperature` |
| Base occupancy | `binary_sensor.buzzbridge_base_home_occupancy` |
| Boost button | `button.buzzbridge_thermostat_home_boost_polling` |

### Migration

When upgrading from older versions or changing the device prefix, BuzzBridge automatically migrates all device names and entity IDs to match the current naming convention. This runs on every startup and handles:
- Adding the type prefix (Thermostat, Base, Remote) to device names
- Renaming entity IDs to match the new device names
- Clearing any `name_by_user` overrides that conflict with the standard

---

## Supported Functions

### Sensor Entities (per thermostat)

**Core readings (fast poll):**
- Temperature
- Humidity
- Heat Setpoint
- Cool Setpoint
- HVAC Mode (auto, heat, cool, off)
- Running Equipment (human-readable, e.g., "Cooling Stage 1, Fan")
- Fan Mode (auto, on)
- Hold Status (None, Hold, Indefinite Hold) with detail attributes

**Air quality (fast poll, ecobee Premium only):**
- Air Quality Score (0-100, higher = better)
- CO2 (ppm)
- VOC (ppb)
- Air Quality Accuracy (BME680 calibration state: Stabilizing through Full)

**Filter status (fast poll):**
- Filter Runtime (total hours since last change, diagnostic entity)
- Days Remaining (estimated, exposed as attribute)

**Daily runtimes (slow poll):**
- Cooling Runtime Today (hours)
- Heating Runtime Today (hours)
- Fan Runtime Today (hours)
- Cooling Degree Days
- Heating Degree Days

**Calculated sensors (fast poll):**
- Comfort Index (0-100%, within setpoint range + ideal humidity = 100%)
- Indoor/Outdoor Differential (temperature difference in degrees)

**Weather (fast poll, disabled by default):**
- Outdoor Temperature
- Outdoor Humidity

### Binary Sensor Entities

- **Online** (per thermostat) — connectivity status, diagnostic entity
- **Occupancy** (per remote sensor) — motion detection
- **Participating** (per remote sensor) — included in comfort average, diagnostic entity

### Button Entities

- **Boost Polling** (per thermostat) — activates 1-minute polling for 60 minutes
- **Refresh Now** (per thermostat) — immediate one-time refresh of all data

### Source Attribute

Every BuzzBridge entity includes a `source` attribute indicating where its data comes from:
- **`beestat`** — data read directly from the Beestat API (temperature, humidity, equipment, air quality, etc.)
- **`calculated`** — derived from beestat data by BuzzBridge (comfort index, indoor/outdoor differential)

### Diagnostic Support

BuzzBridge supports the Home Assistant diagnostics platform. You can download a diagnostics dump from **Settings > Devices & Services > BuzzBridge > 3 dots menu > Download Diagnostics**. Sensitive data (API key, tokens, serial numbers, MAC addresses, location data) is automatically redacted.

---

## Known Limitations

- **Read-only** — BuzzBridge cannot control your thermostat. It only reads data through the Beestat API. Use the native ecobee or HomeKit integration for thermostat control.
- **Data is 3-5 minutes behind real-time** — Beestat applies server-side caching (3 min on sync, 15 min on runtime summaries). This is a Beestat platform constraint, not a BuzzBridge limitation.
- **API rate limit of ~30 requests/minute** — Each batch request (fast poll or slow poll) counts as 1 request regardless of how many thermostats you have. Under normal operation with defaults, BuzzBridge uses approximately 1 request every 5 minutes plus 1 every 30 minutes.
- **Air quality sensors require ecobee Premium** — Only the `aresSmart` model has the Bosch BME680 gas sensor. Other models will not expose CO2, VOC, AQ score, or accuracy entities.
- **Remote/base sensors provide temperature, occupancy, and participating status only** — Humidity is only available on the thermostat entity itself. Sensors cannot be directly controlled.
- **Beestat account required** — A free [Beestat](https://beestat.io/) account linked to your ecobee is required. BuzzBridge does not communicate directly with ecobee.
- **ecobee developer API closed** — ecobee closed its developer API to new registrations in March 2024. Beestat is grandfathered in. This is why BuzzBridge exists.
- **Weather sensors are basic** — Weather data comes from ecobee's built-in weather feed, which provides temperature and humidity only. For richer weather data, use a dedicated weather integration.

---

## Automation Examples

### Alert when air quality score drops below threshold

```yaml
automation:
  - alias: "BuzzBridge - Poor Air Quality Alert"
    trigger:
      - platform: numeric_state
        entity_id: sensor.buzzbridge_thermostat_studio_air_quality_score
        below: 40
        for:
          minutes: 5
    action:
      - service: notify.notify
        data:
          title: "Poor Air Quality"
          message: >
            Air quality score dropped to {{ states('sensor.buzzbridge_thermostat_studio_air_quality_score') }}.
            CO2: {{ states('sensor.buzzbridge_thermostat_studio_co2') }} ppm.
            VOC: {{ states('sensor.buzzbridge_thermostat_studio_voc') }} ppb.
            Consider opening windows or running ventilation.
```

### Alert on short cycling detection

```yaml
automation:
  - alias: "BuzzBridge - Short Cycling Warning"
    trigger:
      - platform: state
        entity_id: sensor.buzzbridge_thermostat_home_running_equipment
    condition:
      - condition: template
        value_template: >
          {% set changes = states.sensor.buzzbridge_thermostat_home_running_equipment.last_changed %}
          {{ (now() - changes).total_seconds() < 600 }}
    action:
      - service: notify.notify
        data:
          title: "HVAC Short Cycling Detected"
          message: >
            Your thermostat equipment is cycling frequently.
            Current status: {{ states('sensor.buzzbridge_thermostat_home_running_equipment') }}.
            This may indicate an oversized system, dirty filter, or refrigerant issue.
```

### Turn on a fan when CO2 exceeds 1000 ppm

```yaml
automation:
  - alias: "BuzzBridge - High CO2 Ventilation"
    trigger:
      - platform: numeric_state
        entity_id: sensor.buzzbridge_thermostat_studio_co2
        above: 1000
        for:
          minutes: 5
    action:
      - service: fan.turn_on
        target:
          entity_id: fan.whole_house_fan
      - service: notify.notify
        data:
          title: "High CO2 - Ventilating"
          message: >
            CO2 is {{ states('sensor.buzzbridge_thermostat_studio_co2') }} ppm (EPA max: 1000 ppm).
            Turning on ventilation fan.
```

### Send notification when thermostat goes offline

```yaml
automation:
  - alias: "BuzzBridge - Thermostat Offline Alert"
    trigger:
      - platform: state
        entity_id: binary_sensor.buzzbridge_thermostat_home_online
        to: "off"
        for:
          minutes: 10
    action:
      - service: notify.notify
        data:
          title: "Thermostat Offline"
          message: >
            {{ trigger.to_state.attributes.friendly_name }} has been offline
            for 10 minutes. Check your thermostat's Wi-Fi connection and power.
```

---

## Troubleshooting

### Enable Debug Logging
Add to `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.buzzbridge: debug
```
Then restart Home Assistant. Debug logs will appear in **Settings > System > Logs** and in the `home-assistant.log` file. Remember to disable debug logging after troubleshooting to avoid filling your log file.

### Download Diagnostics
Go to **Settings > Devices & Services > BuzzBridge > 3 dots menu > Download Diagnostics**. The diagnostics file includes coordinator data with sensitive fields (API key, tokens, location, serial numbers) automatically redacted. This is the most useful artifact when reporting issues.

### Developer Tools

The `tools/` directory contains diagnostic scripts for troubleshooting installations:
- **`beestat_dump.sh`** — Dumps all Beestat API data to a JSON file for analysis
- **`ha_diagnostic.sh`** — Collects HA entity states, device/entity registries, and logs
- **`entity_audit.py`** — Validates naming conventions against the entity registry
- **`beestat_live.sh`** — Real-time API monitor with configurable interval
- **`validate_install.sh`** — Pre-install checker for file structure and syntax
- **`list_entities.py`** — Lists all BuzzBridge entity IDs from the HA registry

See `tools/README.md` for usage details.

### Common Issues

- **"Invalid API key"** — Ensure the key is exactly 40 hex characters. Find it at app.beestat.io → Menu → API Key.
- **"Cannot connect"** — Check your internet connection and that beestat.io is accessible. The Beestat API endpoint is `https://api.beestat.io/`.
- **Air quality shows unavailable** — Only ecobee Premium models (aresSmart) have air quality sensors. Other models will show these entities as unavailable or they will not be created at all.
- **Stale data** — Beestat caches sync responses for 3 minutes and runtime summaries for up to 15 minutes. Data may lag by 3-5 minutes behind real-time. Setting the poll interval below 3 minutes will not help.
- **Rate limit errors** — If you see "Rate limited" warnings in your logs, increase your poll intervals in the integration options. The Beestat API allows approximately 30 requests per minute. Under normal BuzzBridge operation, you should not hit this limit unless other tools are also using your API key.
- **Entities show "unavailable"** — This usually means the thermostat has lost its internet connection. Check the Online binary sensor and your thermostat's Wi-Fi status.
- **Runtime sensors show 0 or None** — Runtime summaries are updated on the slow poll cycle (default 30 min). After initial setup, wait for the first slow poll to complete. If runtime data remains empty, confirm your Beestat account shows runtime data at app.beestat.io.
- **Boost polling not working** — Check the button entity attributes to confirm `boosted: true`. Boost mode reverts automatically after 60 minutes. If the integration was reloaded or HA restarted during boost, the boost state is lost.
- **"ConfigEntryAuthFailed"** — Your API key may have been revoked or your Beestat session expired. Go to **Settings > Devices & Services > BuzzBridge** and reconfigure with a fresh API key from app.beestat.io.

## License

MIT License — see [LICENSE](LICENSE) for details.

## Credits

- **Author:** Chris Caho — project concept, architecture direction, and testing
- **Developer:** [Claude Code](https://claude.ai/claude-code) by Anthropic — code generation, implementation, and documentation
- **Data source:** [Beestat](https://beestat.io/) by Jon Ziebell — the API that makes this possible

This project was built using AI-assisted development. All code was generated by Claude Code (Anthropic) under the direction and review of Chris Caho. This is an original work, not a fork or derivative of any existing integration.
