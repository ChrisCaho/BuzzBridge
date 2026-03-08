#!/bin/bash
# BuzzBridge Diagnostic Tool - Home Assistant State Dump
# Rev: 1.0
#
# Collects BuzzBridge entity states, device info, and integration logs
# from a running Home Assistant instance. Run this ON the HA machine
# (or in the SSH/Terminal add-on).
#
# Usage:
#   bash ha_diagnostic.sh
#
# Output: buzzbridge_ha_diag_*.txt
#
# Requirements:
#   - Must run on the Home Assistant host (or inside an add-on container)
#   - Needs access to the HA API (localhost:8123)
#   - Requires a Long-Lived Access Token (or Supervisor token if in add-on)

set -euo pipefail

OUTPUT_FILE="buzzbridge_ha_diag_$(date +%Y%m%d_%H%M%S).txt"

# --------------------------------------------------------------------------
# Detect HA access method
# --------------------------------------------------------------------------
if [ -n "${SUPERVISOR_TOKEN:-}" ]; then
    # Running inside a HA add-on — use Supervisor API
    HA_URL="http://supervisor/core/api"
    AUTH_HEADER="Authorization: Bearer ${SUPERVISOR_TOKEN}"
    echo "Detected: Running inside HA add-on (Supervisor token)"
elif [ -n "${HA_TOKEN:-}" ]; then
    HA_URL="${HA_URL:-http://localhost:8123/api}"
    AUTH_HEADER="Authorization: Bearer ${HA_TOKEN}"
    echo "Detected: Using HA_TOKEN environment variable"
else
    echo "==========================================================="
    echo "  No HA access token found."
    echo ""
    echo "  Option A (add-on): Run this script inside a HA add-on"
    echo "           (Terminal & SSH, Claude Code, etc.)"
    echo ""
    echo "  Option B (manual): Set HA_TOKEN to a Long-Lived Access Token"
    echo "           export HA_TOKEN='your_long_lived_token_here'"
    echo "           bash ha_diagnostic.sh"
    echo ""
    echo "  Create a token: HA Settings -> People -> Your User ->"
    echo "                  Long-Lived Access Tokens -> Create Token"
    echo "==========================================================="
    exit 1
fi

echo ""
echo "BuzzBridge HA Diagnostic"
echo "========================"
echo ""

# --------------------------------------------------------------------------
# Helper: HA API call
# --------------------------------------------------------------------------
ha_api() {
    local endpoint="$1"
    curl -s -H "${AUTH_HEADER}" -H "Content-Type: application/json" "${HA_URL}${endpoint}" 2>/dev/null
}

# --------------------------------------------------------------------------
# Start output
# --------------------------------------------------------------------------
{
    echo "BuzzBridge Home Assistant Diagnostic Report"
    echo "Generated: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
    echo "============================================"
    echo ""

    # ------------------------------------------------------------------
    # HA version
    # ------------------------------------------------------------------
    echo "--- Home Assistant Version ---"
    ha_api "/config" | python3 -c "
import json, sys
try:
    config = json.load(sys.stdin)
    print(f\"  Version: {config.get('version', 'unknown')}\")
    print(f\"  Location: {config.get('location_name', 'unknown')}\")
    print(f\"  Unit System: {config.get('unit_system', {}).get('temperature', 'unknown')}\")
    print(f\"  Time Zone: {config.get('time_zone', 'unknown')}\")
except: print('  Could not read HA config')
" 2>/dev/null || echo "  Could not read HA config"
    echo ""

    # ------------------------------------------------------------------
    # BuzzBridge integration status
    # ------------------------------------------------------------------
    echo "--- BuzzBridge Integration Status ---"
    ha_api "/config/config_entries/entry" | python3 -c "
import json, sys
try:
    entries = json.load(sys.stdin)
    found = False
    for entry in entries:
        if entry.get('domain') == 'buzzbridge':
            found = True
            print(f\"  Entry ID: {entry.get('entry_id', 'unknown')}\")
            print(f\"  Title: {entry.get('title', 'unknown')}\")
            print(f\"  State: {entry.get('state', 'unknown')}\")
            print(f\"  Version: {entry.get('version', 'unknown')}\")
            # Mask API key
            data = entry.get('data', {})
            if 'api_key' in data:
                key = data['api_key']
                data['api_key'] = key[:4] + '***' + key[-4:] if len(key) > 8 else '***'
            print(f\"  Config: {json.dumps(data, indent=4)}\")
            opts = entry.get('options', {})
            if opts:
                print(f\"  Options: {json.dumps(opts, indent=4)}\")
    if not found:
        print('  BuzzBridge integration NOT found!')
except Exception as e:
    print(f'  Error reading config entries: {e}')
" 2>/dev/null || echo "  Could not read config entries"
    echo ""

    # ------------------------------------------------------------------
    # All BuzzBridge entities
    # ------------------------------------------------------------------
    echo "--- BuzzBridge Entities ---"
    ha_api "/states" | python3 -c "
import json, sys
try:
    states = json.load(sys.stdin)
    bb_states = [s for s in states if 'buzzbridge' in s.get('entity_id', '')]
    bb_states.sort(key=lambda s: s['entity_id'])
    print(f'  Total BuzzBridge entities: {len(bb_states)}')
    print()
    for s in bb_states:
        eid = s['entity_id']
        state = s.get('state', 'unknown')
        friendly = s.get('attributes', {}).get('friendly_name', '')
        unit = s.get('attributes', {}).get('unit_of_measurement', '')
        source = s.get('attributes', {}).get('source', '')
        print(f'  {eid}')
        print(f'    state: {state} {unit}')
        print(f'    friendly_name: {friendly}')
        if source:
            print(f'    source: {source}')
        # Show extra attributes (skip common ones)
        skip = {'friendly_name', 'unit_of_measurement', 'device_class',
                'state_class', 'icon', 'source', 'attribution'}
        extras = {k: v for k, v in s.get('attributes', {}).items() if k not in skip}
        if extras:
            for k, v in extras.items():
                print(f'    {k}: {v}')
        print()
except Exception as e:
    print(f'  Error reading states: {e}')
" 2>/dev/null || echo "  Could not read entity states"
    echo ""

    # ------------------------------------------------------------------
    # BuzzBridge devices
    # ------------------------------------------------------------------
    echo "--- BuzzBridge Devices ---"
    ha_api "/config/device_registry/list" 2>/dev/null | python3 -c "
import json, sys
try:
    # Try the newer API format
    data = json.load(sys.stdin)
    devices = data if isinstance(data, list) else data.get('result', data.get('data', []))
    if not isinstance(devices, list):
        devices = []
    bb_devices = []
    for d in devices:
        ids = d.get('identifiers', [])
        for domain, ident in ids:
            if domain == 'buzzbridge':
                bb_devices.append(d)
                break
    print(f'  Total BuzzBridge devices: {len(bb_devices)}')
    print()
    for d in bb_devices:
        print(f\"  Device: {d.get('name', 'unknown')}\")
        print(f\"    ID: {d.get('id', 'unknown')}\")
        print(f\"    Model: {d.get('model', 'unknown')}\")
        print(f\"    Manufacturer: {d.get('manufacturer', 'unknown')}\")
        print(f\"    SW Version: {d.get('sw_version', 'unknown')}\")
        print(f\"    Identifiers: {d.get('identifiers', [])}\")
        if d.get('name_by_user'):
            print(f\"    Name by user: {d.get('name_by_user')}\")
        if d.get('via_device_id'):
            print(f\"    Via device: {d.get('via_device_id')}\")
        print()
except Exception as e:
    print(f'  Error reading devices: {e}')
" 2>/dev/null || echo "  Could not read device registry (may need ws API)"
    echo ""

    # ------------------------------------------------------------------
    # BuzzBridge logs
    # ------------------------------------------------------------------
    echo "--- BuzzBridge Logs (last 200 lines) ---"
    if [ -f /homeassistant/home-assistant.log ]; then
        grep -i "buzzbridge\|beestat" /homeassistant/home-assistant.log 2>/dev/null | tail -200
    elif [ -f /config/home-assistant.log ]; then
        grep -i "buzzbridge\|beestat" /config/home-assistant.log 2>/dev/null | tail -200
    else
        echo "  Log file not found at expected paths"
        echo "  Trying ha core logs..."
        ha core logs 2>&1 | grep -i "buzzbridge\|beestat" | tail -200 || echo "  Could not read logs"
    fi
    echo ""

    # ------------------------------------------------------------------
    # Entity registry entries (shows unique_ids, disabled status)
    # ------------------------------------------------------------------
    echo "--- Entity Registry (BuzzBridge) ---"
    if [ -f /homeassistant/.storage/core.entity_registry ]; then
        python3 -c "
import json
with open('/homeassistant/.storage/core.entity_registry') as f:
    reg = json.load(f)
entities = reg.get('data', {}).get('entities', [])
bb = [e for e in entities if e.get('platform') == 'buzzbridge']
bb.sort(key=lambda e: e.get('entity_id', ''))
print(f'  Total BuzzBridge entities in registry: {len(bb)}')
print()
for e in bb:
    print(f\"  {e.get('entity_id')}\")
    print(f\"    unique_id: {e.get('unique_id')}\")
    print(f\"    original_name: {e.get('original_name')}\")
    print(f\"    platform: {e.get('platform')}\")
    print(f\"    device_id: {e.get('device_id')}\")
    if e.get('disabled_by'):
        print(f\"    disabled_by: {e.get('disabled_by')}\")
    if e.get('name'):
        print(f\"    user_name: {e.get('name')}\")
    print()
" 2>/dev/null || echo "  Could not read entity registry"
    else
        echo "  Entity registry file not found"
    fi
    echo ""

    # ------------------------------------------------------------------
    # Device registry entries
    # ------------------------------------------------------------------
    echo "--- Device Registry (BuzzBridge) ---"
    if [ -f /homeassistant/.storage/core.device_registry ]; then
        python3 -c "
import json
with open('/homeassistant/.storage/core.device_registry') as f:
    reg = json.load(f)
devices = reg.get('data', {}).get('devices', [])
bb = []
for d in devices:
    for domain, ident in d.get('identifiers', []):
        if domain == 'buzzbridge':
            bb.append(d)
            break
print(f'  Total BuzzBridge devices in registry: {len(bb)}')
print()
for d in bb:
    print(f\"  {d.get('name')}\")
    print(f\"    id: {d.get('id')}\")
    print(f\"    identifiers: {d.get('identifiers')}\")
    print(f\"    model: {d.get('model')}\")
    print(f\"    sw_version: {d.get('sw_version')}\")
    if d.get('name_by_user'):
        print(f\"    name_by_user: {d.get('name_by_user')}\")
    print()
" 2>/dev/null || echo "  Could not read device registry"
    else
        echo "  Device registry file not found"
    fi

} > "${OUTPUT_FILE}" 2>&1

echo "Done! Output written to: ${OUTPUT_FILE}"
echo ""
echo "File size: $(wc -c < "${OUTPUT_FILE}") bytes"
echo ""
echo "NEXT STEPS:"
echo "  1. Review the file — API keys are masked but check for anything else"
echo "  2. Send ${OUTPUT_FILE} to the BuzzBridge developer"
echo "  3. Delete the file when done: rm ${OUTPUT_FILE}"
