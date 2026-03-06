# BuzzBridge
# Rev: 1.0

**A Home Assistant custom integration that bridges Beestat data into your smart home.**

BuzzBridge connects to the [Beestat](https://beestat.io/) API to pull advanced ecobee thermostat data that isn't available through the HomeKit or native ecobee integrations — especially since ecobee closed their developer API to new users in March 2024.

## Features

- **Hold Status** — current hold type, duration, and end time
- **Running Equipment** — heat stage 1/2, cool stage 1/2, aux heat, fan, humidifier, dehumidifier
- **Air Quality** — VOC, CO2 levels (ecobee Premium only)
- **Runtime Data** — heating/cooling runtime hours
- **Equipment Details** — what's currently active on each thermostat

## Prerequisites

1. An [ecobee](https://www.ecobee.com/) thermostat
2. A free [Beestat](https://beestat.io/) account linked to your ecobee
3. A Beestat API key (obtained from your Beestat account)
4. Home Assistant 2024.1+

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
3. Enter your Beestat API key
4. Select your thermostat(s)
5. Sensors will be created automatically

## Sensors Created

| Sensor | Description | Unit |
|--------|-------------|------|
| `sensor.buzzbridge_<name>_hold_status` | Current hold type (none, hold, vacation) | — |
| `sensor.buzzbridge_<name>_running_equipment` | Currently active equipment | — |
| `sensor.buzzbridge_<name>_air_quality_score` | Air quality index | AQI |
| `sensor.buzzbridge_<name>_air_quality_voc` | Volatile organic compounds | ppb |
| `sensor.buzzbridge_<name>_air_quality_co2` | Carbon dioxide level | ppm |
| `sensor.buzzbridge_<name>_heat_runtime` | Heating runtime today | hours |
| `sensor.buzzbridge_<name>_cool_runtime` | Cooling runtime today | hours |

## How It Works

BuzzBridge uses the Beestat public API to read your ecobee thermostat data. Beestat is a free,
open-source analytics platform that is grandfathered into ecobee's API. BuzzBridge polls every
5 minutes (configurable) and creates/updates HA sensor entities with the latest data.

**Important:** BuzzBridge is **read-only**. It cannot control your thermostat — it only provides
visibility into data that the HomeKit integration doesn't expose.

## Privacy

- Your Beestat API key is stored locally in Home Assistant (encrypted in `.storage`)
- No data is sent anywhere except to the Beestat API to retrieve your thermostat data
- BuzzBridge is fully open source — audit the code yourself

## License

MIT License — see [LICENSE](LICENSE) for details.

## Credits

- [Beestat](https://beestat.io/) by Jon Ziebell — the API that makes this possible
- Built with [Claude Code](https://claude.ai/claude-code)
