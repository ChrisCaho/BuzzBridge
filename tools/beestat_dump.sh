#!/bin/bash
# BuzzBridge Diagnostic Tool - Beestat API Data Dump
# Rev: 1.0
#
# Pulls all data from the Beestat API that BuzzBridge uses and writes it
# to a JSON file for troubleshooting. Send the output file to the
# BuzzBridge developer for analysis.
#
# Usage:
#   1. Replace PUT_YOUR_BEESTAT_TOKEN_HERE with your 40-character API key
#   2. Run: bash beestat_dump.sh
#   3. Send the generated buzzbridge_dump_*.json file to the developer
#
# Your API key is NOT included in the output file.

set -euo pipefail

API_KEY="PUT_YOUR_BEESTAT_TOKEN_HERE"
API_URL="https://api.beestat.io/"
OUTPUT_FILE="buzzbridge_dump_$(date +%Y%m%d_%H%M%S).json"

# --------------------------------------------------------------------------
# Preflight checks
# --------------------------------------------------------------------------
if [ "$API_KEY" = "PUT_YOUR_BEESTAT_TOKEN_HERE" ]; then
    echo "ERROR: Please edit this script and replace PUT_YOUR_BEESTAT_TOKEN_HERE"
    echo "       with your Beestat API key (40-character hex string)."
    echo ""
    echo "       Find your key at: https://app.beestat.io -> Menu -> API Key"
    exit 1
fi

if ! command -v curl &>/dev/null; then
    echo "ERROR: curl is required but not installed."
    exit 1
fi

if ! command -v python3 &>/dev/null; then
    HAS_PYTHON=false
else
    HAS_PYTHON=true
fi

echo "BuzzBridge Diagnostic Dump"
echo "=========================="
echo ""

# --------------------------------------------------------------------------
# Helper: make a batch API call
# --------------------------------------------------------------------------
api_batch() {
    local batch_json="$1"
    local description="$2"

    echo -n "  Fetching ${description}... "

    local response
    response=$(curl -s -w "\n%{http_code}" \
        -X POST \
        -H "Content-Type: application/x-www-form-urlencoded" \
        --data-urlencode "api_key=${API_KEY}" \
        --data-urlencode "batch=${batch_json}" \
        "${API_URL}" 2>&1)

    local http_code
    http_code=$(echo "$response" | tail -1)
    local body
    body=$(echo "$response" | sed '$d')

    if [ "$http_code" != "200" ]; then
        echo "FAILED (HTTP ${http_code})"
        echo "  Response: ${body}" >&2
        echo '{"error": "HTTP '"${http_code}"'"}'
        return 1
    fi

    # Check for API-level errors
    if echo "$body" | grep -q '"error_code"'; then
        echo "API ERROR"
        echo "  Response: ${body}" >&2
        echo "$body"
        return 1
    fi

    echo "OK"
    echo "$body"
}

# --------------------------------------------------------------------------
# Fetch fast-poll data (same batch BuzzBridge uses)
# --------------------------------------------------------------------------
echo "Step 1/3: Fetching fast-poll data (thermostats, sensors, ecobee data)..."

FAST_BATCH='[
    {"resource":"thermostat","method":"sync","alias":"thermostat_sync"},
    {"resource":"sensor","method":"sync","alias":"sensor_sync"},
    {"resource":"thermostat","method":"read_id","alias":"thermostats"},
    {"resource":"ecobee_thermostat","method":"read_id","alias":"ecobee_thermostats"},
    {"resource":"sensor","method":"read_id","alias":"sensors"}
]'

FAST_DATA=$(api_batch "$FAST_BATCH" "fast-poll data") || FAST_DATA='{"error":"fast poll failed"}'

# --------------------------------------------------------------------------
# Fetch slow-poll data (runtime summaries)
# --------------------------------------------------------------------------
echo ""
echo "Step 2/3: Fetching slow-poll data (runtime summaries)..."

SLOW_BATCH='[
    {"resource":"runtime","method":"sync","alias":"runtime_sync"},
    {"resource":"runtime_thermostat_summary","method":"read_id","alias":"runtime_summary"}
]'

SLOW_DATA=$(api_batch "$SLOW_BATCH" "slow-poll data") || SLOW_DATA='{"error":"slow poll failed"}'

# --------------------------------------------------------------------------
# Fetch user info (for account context, no sensitive data)
# --------------------------------------------------------------------------
echo ""
echo "Step 3/3: Fetching user info..."

USER_BATCH='[
    {"resource":"user","method":"read_id","alias":"user_info"}
]'

USER_DATA=$(api_batch "$USER_BATCH" "user info") || USER_DATA='{"error":"user read failed"}'

# --------------------------------------------------------------------------
# Combine into output file
# --------------------------------------------------------------------------
echo ""
echo "Writing output..."

if $HAS_PYTHON; then
    python3 -c "
import json, sys
from datetime import datetime

fast = json.loads(sys.argv[1])
slow = json.loads(sys.argv[2])
user = json.loads(sys.argv[3])

# Strip API key from user data if present
if 'data' in user and isinstance(user['data'], dict):
    for uid, udata in user['data'].items():
        if isinstance(udata, dict):
            for key in ['api_key', 'api_key_masked']:
                udata.pop(key, None)
            # Mask email
            email = udata.get('email_address', '')
            if email and '@' in email:
                parts = email.split('@')
                udata['email_address'] = parts[0][:2] + '***@' + parts[1]

output = {
    'buzzbridge_diagnostic': {
        'version': '1.0',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'note': 'Generated by beestat_dump.sh — API key NOT included'
    },
    'fast_poll_data': fast.get('data', fast),
    'slow_poll_data': slow.get('data', slow),
    'user_info': user.get('data', user)
}

with open('${OUTPUT_FILE}', 'w') as f:
    json.dump(output, f, indent=2)
" "$FAST_DATA" "$SLOW_DATA" "$USER_DATA"
else
    # Fallback: write raw JSON without pretty-printing
    echo "{\"fast_poll_data\":${FAST_DATA},\"slow_poll_data\":${SLOW_DATA},\"user_info\":${USER_DATA}}" > "${OUTPUT_FILE}"
fi

echo ""
echo "Done! Output written to: ${OUTPUT_FILE}"
echo ""
echo "File size: $(wc -c < "${OUTPUT_FILE}") bytes"
echo ""
echo "NEXT STEPS:"
echo "  1. Review the file to ensure no sensitive data you're uncomfortable sharing"
echo "  2. Send ${OUTPUT_FILE} to the BuzzBridge developer"
echo "  3. Delete the file when done: rm ${OUTPUT_FILE}"
