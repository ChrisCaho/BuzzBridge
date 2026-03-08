#!/bin/bash
# BuzzBridge Install Validator
# Rev: 1.0
#
# Checks that BuzzBridge is correctly installed in the custom_components
# directory. Validates file structure, JSON syntax, Python syntax, and
# required files. Run BEFORE adding the integration in HA.
#
# Usage:
#   bash validate_install.sh [/path/to/custom_components/buzzbridge]

set -euo pipefail

BB_DIR="${1:-/homeassistant/custom_components/buzzbridge}"

echo "BuzzBridge Install Validator"
echo "============================"
echo ""
echo "Checking: ${BB_DIR}"
echo ""

ERRORS=0
WARNINGS=0

pass() { echo "  PASS: $1"; }
warn() { echo "  WARN: $1"; WARNINGS=$((WARNINGS + 1)); }
fail() { echo "  FAIL: $1"; ERRORS=$((ERRORS + 1)); }

# --------------------------------------------------------------------------
# 1. Directory exists
# --------------------------------------------------------------------------
echo "--- Directory Structure ---"

if [ ! -d "$BB_DIR" ]; then
    fail "Directory does not exist: ${BB_DIR}"
    echo ""
    echo "RESULT: Installation not found. Check the path."
    exit 1
fi
pass "Directory exists"

# --------------------------------------------------------------------------
# 2. Required files
# --------------------------------------------------------------------------
REQUIRED_FILES=(
    "__init__.py"
    "manifest.json"
    "config_flow.py"
    "const.py"
    "api.py"
    "coordinator.py"
    "entity.py"
    "sensor.py"
    "binary_sensor.py"
    "button.py"
    "calculations.py"
    "air_quality.py"
    "strings.json"
    "icons.json"
    "translations/en.json"
)

for f in "${REQUIRED_FILES[@]}"; do
    if [ -f "${BB_DIR}/${f}" ]; then
        pass "Found ${f}"
    else
        fail "Missing ${f}"
    fi
done
echo ""

# --------------------------------------------------------------------------
# 3. Manifest validation
# --------------------------------------------------------------------------
echo "--- Manifest ---"

if [ -f "${BB_DIR}/manifest.json" ]; then
    if python3 -m json.tool "${BB_DIR}/manifest.json" > /dev/null 2>&1; then
        pass "manifest.json is valid JSON"

        VERSION=$(python3 -c "import json; print(json.load(open('${BB_DIR}/manifest.json'))['version'])" 2>/dev/null)
        DOMAIN=$(python3 -c "import json; print(json.load(open('${BB_DIR}/manifest.json'))['domain'])" 2>/dev/null)
        echo "  INFO: Version ${VERSION}, Domain: ${DOMAIN}"

        if [ "$DOMAIN" != "buzzbridge" ]; then
            fail "Domain should be 'buzzbridge', got '${DOMAIN}'"
        fi
    else
        fail "manifest.json is invalid JSON"
    fi
fi
echo ""

# --------------------------------------------------------------------------
# 4. JSON validation
# --------------------------------------------------------------------------
echo "--- JSON Validation ---"

for jsonfile in strings.json icons.json translations/en.json; do
    if [ -f "${BB_DIR}/${jsonfile}" ]; then
        if python3 -m json.tool "${BB_DIR}/${jsonfile}" > /dev/null 2>&1; then
            pass "${jsonfile} is valid JSON"
        else
            fail "${jsonfile} is invalid JSON"
        fi
    fi
done

# Check strings.json == translations/en.json
if [ -f "${BB_DIR}/strings.json" ] && [ -f "${BB_DIR}/translations/en.json" ]; then
    if diff <(python3 -m json.tool "${BB_DIR}/strings.json") <(python3 -m json.tool "${BB_DIR}/translations/en.json") > /dev/null 2>&1; then
        pass "strings.json matches translations/en.json"
    else
        warn "strings.json differs from translations/en.json (translations may be stale)"
    fi
fi
echo ""

# --------------------------------------------------------------------------
# 5. Python syntax validation
# --------------------------------------------------------------------------
echo "--- Python Syntax ---"

PY_FILES=$(find "${BB_DIR}" -name "*.py" -not -path "*__pycache__*" | sort)
for pyfile in $PY_FILES; do
    basename=$(basename "$pyfile")
    if python3 -m py_compile "$pyfile" 2>/dev/null; then
        pass "${basename} compiles"
    else
        fail "${basename} has syntax errors"
    fi
done
echo ""

# --------------------------------------------------------------------------
# 6. Check for __pycache__ (stale bytecode)
# --------------------------------------------------------------------------
echo "--- Bytecode Cache ---"
CACHE_DIR="${BB_DIR}/__pycache__"
if [ -d "$CACHE_DIR" ]; then
    CACHE_COUNT=$(find "$CACHE_DIR" -name "*.pyc" | wc -l)
    if [ "$CACHE_COUNT" -gt 0 ]; then
        warn "${CACHE_COUNT} cached .pyc files found — consider clearing after updates"
        echo "       Run: rm -rf ${CACHE_DIR}"
    fi
else
    pass "No stale bytecode cache"
fi
echo ""

# --------------------------------------------------------------------------
# 7. Check for brand icons
# --------------------------------------------------------------------------
echo "--- Brand Icons ---"
BRAND_DIR="${BB_DIR}/brand"
if [ -d "$BRAND_DIR" ]; then
    for icon in icon.png icon@2x.png; do
        if [ -f "${BRAND_DIR}/${icon}" ]; then
            SIZE=$(wc -c < "${BRAND_DIR}/${icon}")
            if [ "$SIZE" -gt 100 ]; then
                pass "${icon} (${SIZE} bytes)"
            else
                warn "${icon} is suspiciously small (${SIZE} bytes)"
            fi
        else
            warn "Missing ${icon} in brand/"
        fi
    done
else
    warn "No brand/ directory (integration will work but have no icon)"
fi
echo ""

# --------------------------------------------------------------------------
# Result
# --------------------------------------------------------------------------
echo "================================"
if [ "$ERRORS" -gt 0 ]; then
    echo "RESULT: ${ERRORS} error(s), ${WARNINGS} warning(s)"
    echo "Fix errors before adding the integration in HA."
    exit 1
elif [ "$WARNINGS" -gt 0 ]; then
    echo "RESULT: No errors, ${WARNINGS} warning(s)"
    echo "Installation looks good. Warnings are informational."
    exit 0
else
    echo "RESULT: All checks passed!"
    echo "You can add BuzzBridge in HA Settings -> Integrations."
    exit 0
fi
