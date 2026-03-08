# BuzzBridge Diagnostic Tools

Tools for troubleshooting BuzzBridge installations. These help collect debug
information from users experiencing issues.

## Tools

### `beestat_dump.sh` — API Data Dump
Pulls all data from the Beestat API (same calls BuzzBridge makes) and writes
it to a JSON file. The user sends this file to you for analysis.

```bash
# Edit the script and set your API key, then:
bash beestat_dump.sh
# Output: buzzbridge_dump_20260306_143022.json
```

**What it captures:** Thermostat data, ecobee data, sensor data, runtime
summaries, user info (email masked, API key excluded).

### `ha_diagnostic.sh` — HA State & Registry Dump
Collects BuzzBridge entity states, device info, entity/device registry entries,
and integration logs from a running HA instance.

```bash
# Inside an HA add-on (auto-detects Supervisor token):
bash ha_diagnostic.sh

# Or with a Long-Lived Access Token:
export HA_TOKEN='your_token_here'
bash ha_diagnostic.sh
# Output: buzzbridge_ha_diag_20260306_143022.txt
```

**What it captures:** HA version, integration config (API key masked), all
BuzzBridge entities with states/attributes, device registry, entity registry
(unique_ids, original_names), and recent BuzzBridge logs.

### `entity_audit.py` — Naming Convention Validator
Reads the HA registry files offline and validates that all BuzzBridge devices
and entities follow the naming convention.

```bash
python3 entity_audit.py
# Or with a custom path:
python3 entity_audit.py --registry-path /homeassistant/.storage
```

**What it checks:** Device naming pattern (`{prefix} {type} {room}`), entity
ID alignment with device names, orphaned entities, duplicate unique_ids,
entity counts per device.

### `beestat_live.sh` — Real-time API Monitor
Polls the Beestat API at a set interval and displays key values in a readable
format. Useful for watching thermostat behavior while debugging.

```bash
bash beestat_live.sh --key YOUR_API_KEY              # Poll every 60s
bash beestat_live.sh --key YOUR_API_KEY --interval 30 # Poll every 30s
bash beestat_live.sh --key YOUR_API_KEY --once         # Single poll
```

### `validate_install.sh` — Installation Checker
Validates file structure, JSON syntax, Python syntax, and required files.
Run before adding the integration in HA.

```bash
bash validate_install.sh
# Or with a custom path:
bash validate_install.sh /homeassistant/custom_components/buzzbridge
```

## Troubleshooting Workflow

1. **User reports a problem** → Have them run `beestat_dump.sh` and
   `ha_diagnostic.sh`, send both files
2. **You receive the files** → Run `entity_audit.py` on their HA data to
   check naming. Compare their API dump to expected data shapes.
3. **Need real-time debugging** → Have them run `beestat_live.sh` and share
   the terminal output while reproducing the issue.
4. **After a fix** → Have them run `validate_install.sh` to verify the
   installation before restarting HA.
