# BuzzBridge - Development Notes
# Rev: 1.0

## Project Overview
Custom Home Assistant integration that pulls ecobee thermostat data from the Beestat API
and exposes it as HA sensors. Bridges the gap left by ecobee closing their developer API.

## Architecture
- Polls Beestat API every 3-5 minutes
- Creates HA sensor entities via native HA integration (config flow)
- No MQTT dependency required

## Beestat API Details
- Base URL: https://api.beestat.io/
- Auth: API key as query parameter `?api_key={KEY}`
- Rate limit: ~30 requests/minute
- Key endpoints:
  - `thermostat.read` - thermostat data, running_equipment, hold status
  - `runtime_sensor.read` - sensor data, air quality
  - `thermostat.sync` - force fresh sync from ecobee
  - `sensor.sync` - force sensor data sync
- Data syncs when beestat is actively used in browser, and periodically otherwise

## Target Sensors
- Hold status (type, duration, end time)
- Running equipment (stage 1/2, aux, fan, humidifier, dehumidifier)
- Air quality (if Premium ecobee)
- Runtime data (daily, monthly, yearly)
- Equipment stage details

## Progress Log
- 2026-03-06: Project initialized, git repo created, connected to GitHub ChrisCaho/BuzzBridge
