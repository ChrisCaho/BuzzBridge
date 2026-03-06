# BuzzBridge - Constants and Configuration
# Rev: 1.1
#
# Central definition of all constants, thresholds, entity configurations,
# and human-readable air quality guidelines used throughout BuzzBridge.

from __future__ import annotations

from typing import Final

# =============================================================================
# Integration identifiers
# =============================================================================
DOMAIN: Final = "buzzbridge"
MANUFACTURER: Final = "ecobee (via Beestat)"

# =============================================================================
# Configuration keys
# =============================================================================
CONF_API_KEY: Final = "api_key"
CONF_DEVICE_PREFIX: Final = "device_prefix"
CONF_FAST_POLL_INTERVAL: Final = "fast_poll_interval"
CONF_SLOW_POLL_INTERVAL: Final = "slow_poll_interval"

DEFAULT_DEVICE_PREFIX: Final = "BuzzBridge"

# =============================================================================
# Polling defaults and limits
# =============================================================================
DEFAULT_FAST_POLL_MINUTES: Final = 5
DEFAULT_SLOW_POLL_MINUTES: Final = 30
MIN_POLL_MINUTES: Final = 3       # Beestat server-side cache on sync = 180s
MAX_POLL_MINUTES: Final = 60

# Boost mode: press button → 1 min polls for 60 minutes, then revert
BOOST_POLL_SECONDS: Final = 60
BOOST_DURATION_MINUTES: Final = 60

# =============================================================================
# Beestat API
# =============================================================================
API_BASE_URL: Final = "https://api.beestat.io/"
API_RATE_LIMIT_PER_MINUTE: Final = 30

# Values that indicate "sensor not available" in ecobee data
ECOBEE_UNAVAILABLE_VALUE: Final = -5002

# =============================================================================
# Platforms
# =============================================================================
PLATFORMS: Final = ("sensor", "binary_sensor", "button")

# =============================================================================
# Data keys used in coordinator data dict
# =============================================================================
DATA_THERMOSTATS: Final = "thermostats"
DATA_ECOBEE_THERMOSTATS: Final = "ecobee_thermostats"
DATA_SENSORS: Final = "sensors"
DATA_RUNTIME_SUMMARY: Final = "runtime_summary"

# =============================================================================
# Air Quality Thresholds
#
# The ecobee Premium uses a Bosch BME680 gas sensor to measure VOCs and
# estimate CO2. The raw air quality score from ecobee is 0-350 (lower = better).
# Beestat normalizes this to 0-100 (higher = better).
#
# CO2 is measured in parts per million (ppm). Fresh outdoor air is ~400 ppm.
# Indoor levels rise with occupancy and poor ventilation.
#
# VOCs (Volatile Organic Compounds) are measured in parts per billion (ppb).
# Sources include cleaning products, paint, furniture off-gassing, cooking.
# =============================================================================

# Air Quality Score (0-100, beestat normalized, higher = better)
AQ_SCORE_THRESHOLDS: Final = [
    # (min_score, level, description, health_note, icon_color)
    (81, "Excellent", "Clean air", "No action needed", "green"),
    (61, "Good", "Acceptable air quality", "Most people comfortable", "lightgreen"),
    (41, "Fair", "Moderate air quality", "Consider ventilation. Sensitive individuals may notice.", "yellow"),
    (21, "Poor", "Unhealthy air quality", "Open windows, run ventilation, identify source.", "orange"),
    (0, "Hazardous", "Dangerous air quality", "Ventilate immediately. Check for chemical sources.", "red"),
]

# CO2 levels in parts per million (ppm)
# Reference: EPA recommends under 1000 ppm indoors.
# Fresh outdoor air: ~400 ppm. Exhaled breath: ~40,000 ppm.
# At 1000+ ppm, cognitive performance measurably declines (PMC3548274).
# OSHA 8-hour workplace limit: 5000 ppm.
CO2_THRESHOLDS: Final = [
    # (max_ppm, level, description, health_note)
    (400, "Excellent", "Fresh outdoor air levels", "No action needed"),
    (700, "Good", "Well-ventilated indoor space", "No action needed"),
    (1000, "Fair", "Acceptable, getting stuffy", "EPA recommended maximum. Consider ventilating."),
    (1500, "Warning", "Stuffy air", "Cognitive performance begins to decline. Ventilate."),
    (2500, "Poor", "Unhealthy indoor air", "Drowsiness, headaches, poor concentration likely."),
    (5000, "Dangerous", "Approaching OSHA workplace limit", "Serious health effects possible. Ventilate now."),
    (99999, "Critical", "Extremely dangerous CO2 level", "Leave the area immediately."),
]

# VOC levels in parts per billion (ppb)
# VOCs include formaldehyde, benzene, toluene, and hundreds of other compounds.
# Indoor levels are typically 2-5x higher than outdoors (EPA).
# Sources: cleaning products, paint, new furniture/carpet, cooking, personal care.
# Long-term exposure linked to cancer, liver/kidney damage (EPA/WHO).
VOC_THRESHOLDS: Final = [
    # (max_ppb, level, description, health_note)
    (100, "Excellent", "Very clean air", "No action needed"),
    (400, "Good", "Normal indoor levels", "No action needed"),
    (800, "Fair", "Slightly elevated", "Common after cleaning, cooking, new furniture."),
    (1500, "Warning", "Elevated VOC levels", "Short-term irritation possible. Ventilate and identify source."),
    (2200, "Poor", "Unhealthy VOC levels", "Headaches, nausea, eye/throat irritation likely."),
    (99999, "Dangerous", "Dangerous VOC levels", "Dizziness, loss of coordination. Ventilate immediately."),
]

# Air Quality Accuracy (BME680 sensor calibration state)
# The ecobee Premium's gas sensor needs time after power-on to calibrate.
# Accuracy improves as the sensor builds a baseline over hours/days.
AQ_ACCURACY_LEVELS: Final = {
    0: ("Stabilizing", "Sensor warming up, readings unreliable"),
    1: ("Low", "Limited calibration data, take readings with caution"),
    2: ("Medium", "Reasonable confidence in readings"),
    3: ("High", "Well-calibrated, trustworthy readings"),
    4: ("Full", "Fully calibrated, maximum confidence"),
}

# =============================================================================
# Heating & Cooling Degree Days
#
# Degree days measure how much heating or cooling demand exists based on
# outdoor temperature. They use a base of 65°F (the temperature below which
# buildings typically need heating, above which they need cooling).
#
# Example: If the average outdoor temp is 55°F, that day has 10 Heating
# Degree Days (65 - 55 = 10). If it's 80°F, that's 15 Cooling Degree Days
# (80 - 65 = 15). A mild 65°F day has 0 of both.
#
# Higher numbers = more energy needed. Useful for:
#   - Comparing energy use across days with different weather
#   - Detecting efficiency changes ("same degree days, more runtime = problem")
#   - Seasonal energy planning
# =============================================================================
DEGREE_DAY_BASE_F: Final = 65.0
DEGREE_DAY_UNIT: Final = "°F·d"

# =============================================================================
# Calculated sensor thresholds
# =============================================================================

# Short cycling detection
# Normal: 2-3 cycles/hour, 15-20 min each.
# Short cycling: >6 cycles/hour or <10 min average duration.
# Causes: oversized equipment, refrigerant leak, dirty filter, thermostat issues.
SHORT_CYCLE_MAX_PER_HOUR: Final = 6
SHORT_CYCLE_MIN_DURATION_MINUTES: Final = 10

# Comfort index weights (0-100 scale)
# Perfect comfort = at setpoint with humidity 30-50%
COMFORT_IDEAL_HUMIDITY_LOW: Final = 30
COMFORT_IDEAL_HUMIDITY_HIGH: Final = 50
COMFORT_TEMP_WEIGHT: Final = 0.7    # 70% weight on temperature accuracy
COMFORT_HUMIDITY_WEIGHT: Final = 0.3  # 30% weight on humidity comfort

# =============================================================================
# Equipment mapping
#
# Maps ecobee equipment status strings to human-readable names.
# The running_equipment array from beestat contains these values when
# the corresponding equipment is actively running.
# =============================================================================
EQUIPMENT_MAP: Final = {
    "compressor_cool_1": "Cooling Stage 1",
    "compressor_cool_2": "Cooling Stage 2",
    "compressor_heat_1": "Heat Pump Stage 1",
    "compressor_heat_2": "Heat Pump Stage 2",
    "auxiliary_heat_1": "Aux Heat Stage 1",
    "auxiliary_heat_2": "Aux Heat Stage 2",
    "fan": "Fan",
    "humidifier": "Humidifier",
    "dehumidifier": "Dehumidifier",
    "ventilator": "Ventilator",
    "economizer": "Economizer",
}

# =============================================================================
# Filter runtime conversion
# Runtime from beestat is in seconds. We display in hours.
# =============================================================================
SECONDS_PER_HOUR: Final = 3600

# =============================================================================
# ecobee model names
# =============================================================================
ECOBEE_MODELS: Final = {
    "apolloSmart": "ecobee SmartThermostat",
    "aresSmart": "ecobee Smart Thermostat Premium",
    "nikeSmart": "ecobee Smart Thermostat Enhanced",
    "vulcanSmart": "ecobee Smart Thermostat Essential",
    "corSmart": "Carrier Cor",
    "siSmart": "ecobee Si",
    "athenaSmart": "ecobee3",
    "idtSmart": "ecobee3 lite",
}
