# BuzzBridge Project Memory

## Project Info
- Name: BuzzBridge
- Repo: https://github.com/ChrisCaho/BuzzBridge (private, will go public later)
- Local path: /homeassistant/claudeSrc/beeStat
- GitHub user: ChrisCaho
- Target: HA 2026.3 custom component
- Will be installed on a separate HA monitoring machine, NOT this one

## Conventions
- All files carry a Rev number (e.g. `# Rev: 1.0`), updated on every change
- Progress tracked in NOTES.md
- Project memory kept here in MEMORY.md

## Architecture Decisions
- Native HA integration with config flow (not MQTT-based)
- Polls Beestat API (not ecobee directly — ecobee closed dev API)
- Read-only — no thermostat control
- Beestat API key as the only credential needed

## Key Files
- README.md - public docs
- NOTES.md - dev notes and progress log
- .gitignore - standard Python/HA ignores
- custom_components/buzzbridge/ - (to be created) the actual integration

## Beestat API
- Base: https://api.beestat.io/
- Auth: ?api_key={KEY}
- Rate limit: ~30 req/min
- Full reference: API_REFERENCE.md (50+ methods across 15+ resources)
- Key endpoints: thermostat.read_id, sensor.read_id, runtime_thermostat.read, runtime_sensor.read, runtime_thermostat_summary.read_id, thermostat.sync, sensor.sync, runtime.sync
- Batch API: multiple calls per HTTP request supported
- Temps stored x10, API divides by 10 on return
- Air quality normalized 0-100 from ecobee 0-350 scale
- Max query range for runtime data: 31 days
- Server caching: sync methods 180s, runtime reads 900s
