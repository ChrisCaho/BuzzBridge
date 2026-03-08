#!/bin/bash
# BuzzBridge Live Monitor - Real-time Beestat API Polling
# Rev: 1.0
#
# Polls the Beestat API at a specified interval and displays key values
# in a readable format. Useful for watching thermostat behavior in real-time
# while debugging issues.
#
# Usage:
#   bash beestat_live.sh                    # Poll every 60 seconds
#   bash beestat_live.sh --interval 30      # Poll every 30 seconds
#   bash beestat_live.sh --once             # Single poll, no loop

set -euo pipefail

API_KEY="PUT_YOUR_BEESTAT_TOKEN_HERE"
API_URL="https://api.beestat.io/"
INTERVAL=60
ONCE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --interval) INTERVAL="$2"; shift 2 ;;
        --once) ONCE=true; shift ;;
        --key) API_KEY="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

if [ "$API_KEY" = "PUT_YOUR_BEESTAT_TOKEN_HERE" ]; then
    echo "ERROR: Set your API key with --key YOUR_KEY or edit the script."
    exit 1
fi

FAST_BATCH='[
    {"resource":"thermostat","method":"sync","alias":"thermostat_sync"},
    {"resource":"sensor","method":"sync","alias":"sensor_sync"},
    {"resource":"thermostat","method":"read_id","alias":"thermostats"},
    {"resource":"ecobee_thermostat","method":"read_id","alias":"ecobee_thermostats"},
    {"resource":"sensor","method":"read_id","alias":"sensors"}
]'

poll() {
    local response
    response=$(curl -s \
        -X POST \
        -H "Content-Type: application/x-www-form-urlencoded" \
        --data-urlencode "api_key=${API_KEY}" \
        --data-urlencode "batch=${FAST_BATCH}" \
        "${API_URL}" 2>/dev/null)

    python3 -c "
import json, sys
from datetime import datetime

try:
    raw = json.loads(sys.argv[1])
    data = raw.get('data', raw)
except:
    print('  ERROR: Could not parse API response')
    sys.exit(1)

thermostats = data.get('thermostats', {})
ecobee = data.get('ecobee_thermostats', {})
sensors = data.get('sensors', {})

print(f'  Polled: {datetime.now().strftime(\"%H:%M:%S\")}')
print()

for tid, t in thermostats.items():
    name = t.get('name', f'Thermostat {tid}')
    temp = t.get('temperature', '?')
    humidity = t.get('humidity', '?')
    heat_sp = t.get('setpoint_heat', '?')
    cool_sp = t.get('setpoint_cool', '?')
    equip = t.get('running_equipment', [])
    equip_str = ', '.join(equip) if equip else 'Idle'

    eid = str(t.get('ecobee_thermostat_id', ''))
    eco = ecobee.get(eid, {})
    hvac = (eco.get('settings') or {}).get('hvacMode', '?')

    # Weather
    weather = eco.get('weather', {})
    forecasts = weather.get('forecasts', [])
    outdoor_raw = forecasts[0].get('temperature', '?') if forecasts else '?'
    outdoor_humidity = forecasts[0].get('relativeHumidity', '?') if forecasts else '?'
    outdoor = round(outdoor_raw / 10, 1) if isinstance(outdoor_raw, (int, float)) and outdoor_raw > 200 else outdoor_raw

    # Hold
    hold_info = 'None'
    for event in (eco.get('events') or []):
        if event.get('type') == 'hold' and event.get('running'):
            hold_info = 'Indefinite' if event.get('isIndefinite') else 'Hold'
            break

    # AQ
    runtime = eco.get('runtime', {})
    aq = runtime.get('actualAQScore', 'N/A')
    co2 = runtime.get('actualCO2', 'N/A')
    voc = runtime.get('actualVOC', 'N/A')

    print(f'  THERMOSTAT: {name} (ID: {tid})')
    print(f'    Temp: {temp}°F  Humidity: {humidity}%  HVAC: {hvac}')
    print(f'    Setpoints: Heat={heat_sp}°F  Cool={cool_sp}°F')
    print(f'    Equipment: {equip_str}')
    print(f'    Hold: {hold_info}')
    print(f'    Outdoor: {outdoor}°F  Humidity: {outdoor_humidity}%')
    if aq != 'N/A' or co2 != 'N/A':
        print(f'    AQ Score: {aq}  CO2: {co2}ppm  VOC: {voc}ppb')
    print()

# Sensors
for sid, s in sensors.items():
    if s.get('deleted') or s.get('inactive'):
        continue
    name = s.get('name', f'Sensor {sid}')
    stype = s.get('type', '?')
    in_use = s.get('in_use', '?')
    temp = s.get('temperature', '?')
    humidity = s.get('humidity')

    # Get occupancy from capabilities
    occupancy = '?'
    for cap in (s.get('capability') or []):
        if cap.get('type') == 'occupancy':
            occupancy = cap.get('value', '?')

    type_label = 'BASE' if stype == 'thermostat' else 'REMOTE'
    parts = [f'Temp: {temp}°F']
    if humidity is not None:
        parts.append(f'Humidity: {humidity}%')
    parts.append(f'Occupancy: {occupancy}')
    parts.append(f'Participating: {in_use}')

    print(f'  {type_label} SENSOR: {name} (ID: {sid})')
    print(f'    {\"  \".join(parts)}')
    print()
" "$response"
}

echo "BuzzBridge Live Monitor"
echo "======================="
echo ""

if $ONCE; then
    poll
else
    echo "  Polling every ${INTERVAL}s (Ctrl+C to stop)"
    echo ""
    while true; do
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        poll
        sleep "$INTERVAL"
    done
fi
