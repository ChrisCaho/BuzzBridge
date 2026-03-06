# BuzzBridge
# Rev: 2.0

**A Home Assistant custom integration that bridges Beestat data into your smart home.**

BuzzBridge connects to the [Beestat](https://beestat.io/) API to pull advanced ecobee thermostat data that isn't available through the HomeKit or native ecobee integrations — especially since ecobee closed their developer API to new users in March 2024.

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
- **Comfort Index** — 0-100% based on temperature accuracy (70% weight) and humidity comfort (30% weight)
- **Indoor/Outdoor Differential** — temperature difference showing insulation effectiveness

### Remote Sensors
- **Temperature** — for every ecobee remote sensor
- **Humidity** — where available (thermostat built-in sensor)
- **Occupancy** — motion detection as binary sensor

### Filter Status
- **Filter Runtime** — total hours since last change
- **Days Remaining** — estimated based on filter life setting

### Weather (disabled by default)
- **Outdoor Temperature** — from ecobee weather data
- **Outdoor Humidity** — from ecobee weather data

### Boost Polling
Each thermostat gets a **Boost Polling** button that switches polling from the configured interval (default 5 min) to every 60 seconds for 60 minutes, then automatically reverts. Useful for monitoring changes in real-time or debugging.

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
4. All thermostats and sensors are discovered automatically
5. Configure poll intervals in integration options (Settings → Devices & Services → BuzzBridge → Configure)

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

## Troubleshooting

### Enable Debug Logging
Add to `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.buzzbridge: debug
```

### Common Issues
- **"Invalid API key"** — Ensure the key is exactly 40 hex characters. Find it at app.beestat.io → Menu → API Key.
- **"Cannot connect"** — Check your internet connection and that beestat.io is accessible.
- **Air quality shows unavailable** — Only ecobee Premium models (aresSmart) have air quality sensors.
- **Stale data** — Beestat caches sync responses for 3 minutes. Data may lag by up to 3 min.

## License

MIT License — see [LICENSE](LICENSE) for details.

## Credits

- [Beestat](https://beestat.io/) by Jon Ziebell — the API that makes this possible
- Built with [Claude Code](https://claude.ai/claude-code)
