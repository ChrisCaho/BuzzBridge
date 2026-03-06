# BuzzBridge - Calculated Sensor Logic
# Rev: 1.2
#
# Pure functions that derive useful metrics from raw thermostat data.
# These power the "calculated sensor" entities in BuzzBridge.
#
# All functions accept raw data dicts (as returned by the Beestat API) and
# return computed values. They are stateless — no side effects, no API calls.

from __future__ import annotations

from typing import Any

from .const import (
    COMFORT_HUMIDITY_WEIGHT,
    COMFORT_IDEAL_HUMIDITY_HIGH,
    COMFORT_IDEAL_HUMIDITY_LOW,
    COMFORT_TEMP_WEIGHT,
    EQUIPMENT_MAP,
    SECONDS_PER_HOUR,
    SHORT_CYCLE_MAX_PER_HOUR,
    SHORT_CYCLE_MIN_DURATION_MINUTES,
)

# Temperature tolerance for comfort index, in Fahrenheit.
# At ±5°F from setpoint, the temperature comfort component drops to 0.
# Note: All temperature calculations assume Fahrenheit (ecobee default).
COMFORT_TEMP_TOLERANCE_F = 5.0


def cooling_efficiency(
    cool_runtime_seconds: float | None,
    cooling_degree_days: float | None,
) -> float | None:
    """Calculate cooling efficiency: runtime hours per cooling degree day.

    Lower values = more efficient system (less runtime needed per degree day).
    Useful for comparing across days with different weather conditions.

    Args:
        cool_runtime_seconds: Total cooling runtime in seconds for the period.
        cooling_degree_days: Cooling degree days for the same period.

    Returns:
        Hours of cooling per degree day, or None if data insufficient.
    """
    if cool_runtime_seconds is None or cooling_degree_days is None:
        return None
    if cooling_degree_days <= 0:
        return None
    hours = cool_runtime_seconds / SECONDS_PER_HOUR
    return round(hours / cooling_degree_days, 2)


def heating_efficiency(
    heat_runtime_seconds: float | None,
    heating_degree_days: float | None,
) -> float | None:
    """Calculate heating efficiency: runtime hours per heating degree day.

    Lower values = more efficient. Same concept as cooling_efficiency but
    for heating equipment.

    Args:
        heat_runtime_seconds: Total heating runtime in seconds (all stages).
        heating_degree_days: Heating degree days for the same period.

    Returns:
        Hours of heating per degree day, or None if data insufficient.
    """
    if heat_runtime_seconds is None or heating_degree_days is None:
        return None
    if heating_degree_days <= 0:
        return None
    hours = heat_runtime_seconds / SECONDS_PER_HOUR
    return round(hours / heating_degree_days, 2)


def equipment_duty_cycle(
    equipment_runtime_seconds: float | None,
    total_period_seconds: float | None,
) -> float | None:
    """Calculate equipment duty cycle as a percentage.

    Duty cycle = what fraction of the period the equipment was running.
    100% means running the entire time (possible oversizing or extreme weather).
    Normal cooling: 30-60%. Normal heating: 20-50%.

    Args:
        equipment_runtime_seconds: How long the equipment ran.
        total_period_seconds: Total length of the measurement period.

    Returns:
        Duty cycle as percentage (0-100), or None.
    """
    if equipment_runtime_seconds is None or total_period_seconds is None:
        return None
    if total_period_seconds <= 0:
        return None
    pct = (equipment_runtime_seconds / total_period_seconds) * 100
    return round(min(pct, 100.0), 1)


def indoor_outdoor_differential(
    indoor_temp: float | None,
    outdoor_temp: float | None,
) -> float | None:
    """Calculate the temperature differential between indoors and outdoors.

    Positive = indoor is warmer than outdoor (typical in winter).
    Negative = indoor is cooler than outdoor (typical in summer with AC).

    Useful for evaluating insulation performance — a well-insulated home
    maintains a large differential with less energy.

    Args:
        indoor_temp: Current indoor temperature.
        outdoor_temp: Current outdoor temperature.

    Returns:
        Temperature difference (indoor - outdoor), or None.
    """
    if indoor_temp is None or outdoor_temp is None:
        return None
    return round(indoor_temp - outdoor_temp, 1)


def detect_short_cycling(
    cycle_count: int | None,
    total_runtime_seconds: float | None,
    period_hours: float = 1.0,
) -> dict[str, Any]:
    """Detect short cycling conditions.

    Short cycling is when HVAC equipment turns on and off too frequently,
    indicating potential problems: oversized equipment, refrigerant leak,
    dirty filter, or thermostat issues.

    Normal: 2-3 cycles/hour, 15-20 minutes each.
    Short cycling: >6 cycles/hour or <10 min average duration.

    Args:
        cycle_count: Number of on/off cycles in the period.
        total_runtime_seconds: Total runtime in seconds during the period.
        period_hours: Length of the period in hours.

    Returns:
        Dict with "is_short_cycling" (bool), "cycles_per_hour" (float),
        "avg_cycle_minutes" (float or None).
    """
    result: dict[str, Any] = {
        "is_short_cycling": False,
        "cycles_per_hour": 0.0,
        "avg_cycle_minutes": None,
    }

    if cycle_count is None or cycle_count <= 0 or period_hours <= 0:
        return result

    cycles_per_hour = cycle_count / period_hours
    result["cycles_per_hour"] = round(cycles_per_hour, 1)

    if total_runtime_seconds and cycle_count > 0:
        avg_minutes = (total_runtime_seconds / cycle_count) / 60
        result["avg_cycle_minutes"] = round(avg_minutes, 1)

        if (
            cycles_per_hour > SHORT_CYCLE_MAX_PER_HOUR
            or avg_minutes < SHORT_CYCLE_MIN_DURATION_MINUTES
        ):
            result["is_short_cycling"] = True
    elif cycles_per_hour > SHORT_CYCLE_MAX_PER_HOUR:
        result["is_short_cycling"] = True

    return result


def comfort_index(
    current_temp: float | None,
    setpoint_heat: float | None,
    setpoint_cool: float | None,
    current_humidity: float | None,
) -> float | None:
    """Calculate a 0-100 comfort index.

    Perfect comfort (100) = within the setpoint range with humidity 30-50%.
    Combines temperature accuracy (70% weight) and humidity comfort (30%).

    Temperature scoring by HVAC mode:
    - Auto (both setpoints): 100 anywhere within heat-cool range, degrades
      linearly when outside the range up to TOLERANCE beyond.
    - Heat only: 100 at or above heat setpoint, degrades below.
    - Cool only: 100 at or below cool setpoint, degrades above.
    - Off (no setpoints): returns None.

    The tolerance is 5°F — beyond that distance outside the range,
    the temperature component drops to 0. Humidity uses a linear ramp
    outside the 30-50% ideal range.

    Args:
        current_temp: Actual indoor temperature.
        setpoint_heat: Heat setpoint (None if not heating).
        setpoint_cool: Cool setpoint (None if not cooling).
        current_humidity: Current relative humidity percentage.

    Returns:
        Comfort score 0-100, or None if insufficient data.
    """
    if current_temp is None:
        return None
    if setpoint_heat is None and setpoint_cool is None:
        return None

    # Temperature component: how far outside the comfort range
    if setpoint_heat is not None and setpoint_cool is not None:
        # Auto mode: comfort range is [heat, cool]
        if current_temp < setpoint_heat:
            temp_diff = setpoint_heat - current_temp
        elif current_temp > setpoint_cool:
            temp_diff = current_temp - setpoint_cool
        else:
            temp_diff = 0.0  # Within range = perfect
    elif setpoint_heat is not None:
        # Heat only: comfortable at or above setpoint
        temp_diff = max(0.0, setpoint_heat - current_temp)
    else:
        # Cool only: comfortable at or below setpoint
        temp_diff = max(0.0, current_temp - setpoint_cool)

    temp_score = max(0.0, 100.0 - (temp_diff / COMFORT_TEMP_TOLERANCE_F) * 100.0)

    # Humidity component: 100 within 30-50%, degrading linearly outside
    humidity_score = 100.0
    if current_humidity is not None:
        if current_humidity < COMFORT_IDEAL_HUMIDITY_LOW:
            # 0% humidity → score ~40
            humidity_score = max(
                0.0,
                100.0 - (COMFORT_IDEAL_HUMIDITY_LOW - current_humidity) * 2.0,
            )
        elif current_humidity > COMFORT_IDEAL_HUMIDITY_HIGH:
            # 100% humidity → score ~0
            humidity_score = max(
                0.0,
                100.0 - (current_humidity - COMFORT_IDEAL_HUMIDITY_HIGH) * 2.0,
            )

    score = (temp_score * COMFORT_TEMP_WEIGHT) + (
        humidity_score * COMFORT_HUMIDITY_WEIGHT
    )
    return round(max(0.0, min(100.0, score)), 1)


def recovery_rate(
    start_temp: float | None,
    end_temp: float | None,
    elapsed_minutes: float | None,
) -> float | None:
    """Calculate temperature recovery rate in degrees per hour.

    How fast the system brings temperature toward setpoint after a setback
    or hold ends. Higher = faster recovery = better sized equipment.

    Args:
        start_temp: Temperature when recovery started.
        end_temp: Temperature when recovery ended (or current).
        elapsed_minutes: Time elapsed in minutes.

    Returns:
        Degrees per hour of temperature change, or None.
    """
    if start_temp is None or end_temp is None or elapsed_minutes is None:
        return None
    if elapsed_minutes <= 0:
        return None
    delta = abs(end_temp - start_temp)
    rate = (delta / elapsed_minutes) * 60.0
    return round(rate, 1)


def temperature_swing(
    high_temp: float | None,
    low_temp: float | None,
) -> float | None:
    """Calculate the temperature swing (max - min) for a period.

    Large swings indicate thermostat overshoot/undershoot, poor equipment
    sizing, or aggressive setback schedules.

    Args:
        high_temp: Maximum temperature in the period.
        low_temp: Minimum temperature in the period.

    Returns:
        Temperature range, or None.
    """
    if high_temp is None or low_temp is None:
        return None
    return round(abs(high_temp - low_temp), 1)


def format_running_equipment(equipment_list: list[str] | None) -> str:
    """Convert ecobee equipment status codes to human-readable string.

    Args:
        equipment_list: List of equipment code strings from ecobee
                       (e.g., ["compressor_cool_1", "fan"]).

    Returns:
        Human-readable string (e.g., "Cooling Stage 1, Fan") or "Idle".
    """
    if not equipment_list:
        return "Idle"

    names = []
    for code in equipment_list:
        name = EQUIPMENT_MAP.get(code, code.replace("_", " ").title())
        names.append(name)

    return ", ".join(names)
