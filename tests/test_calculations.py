"""Tests for BuzzBridge calculation functions."""

from __future__ import annotations

import pytest

from custom_components.buzzbridge.calculations import (
    comfort_index,
    cooling_efficiency,
    detect_short_cycling,
    equipment_duty_cycle,
    format_running_equipment,
    heating_efficiency,
    indoor_outdoor_differential,
    recovery_rate,
    temperature_swing,
)


# ---------------------------------------------------------------------------
# cooling_efficiency
# ---------------------------------------------------------------------------

class TestCoolingEfficiency:

    def test_normal(self):
        # 7200 seconds = 2 hours, 12.5 degree days -> 2/12.5 = 0.16
        result = cooling_efficiency(7200, 12.5)
        assert result == 0.16

    def test_zero_degree_days(self):
        assert cooling_efficiency(7200, 0) is None

    def test_negative_degree_days(self):
        assert cooling_efficiency(7200, -1) is None

    def test_none_runtime(self):
        assert cooling_efficiency(None, 12.5) is None

    def test_none_degree_days(self):
        assert cooling_efficiency(7200, None) is None

    def test_both_none(self):
        assert cooling_efficiency(None, None) is None

    def test_zero_runtime(self):
        assert cooling_efficiency(0, 10.0) == 0.0


# ---------------------------------------------------------------------------
# heating_efficiency
# ---------------------------------------------------------------------------

class TestHeatingEfficiency:

    def test_normal(self):
        # 3600 seconds = 1 hour, 5 degree days -> 1/5 = 0.2
        result = heating_efficiency(3600, 5.0)
        assert result == 0.2

    def test_zero_degree_days(self):
        assert heating_efficiency(3600, 0) is None

    def test_none_inputs(self):
        assert heating_efficiency(None, 5.0) is None
        assert heating_efficiency(3600, None) is None


# ---------------------------------------------------------------------------
# equipment_duty_cycle
# ---------------------------------------------------------------------------

class TestEquipmentDutyCycle:

    def test_half_duty(self):
        result = equipment_duty_cycle(1800, 3600)
        assert result == 50.0

    def test_full_duty(self):
        result = equipment_duty_cycle(3600, 3600)
        assert result == 100.0

    def test_over_100_clamped(self):
        # Runtime exceeds period (data error) — clamp to 100
        result = equipment_duty_cycle(7200, 3600)
        assert result == 100.0

    def test_zero_period(self):
        assert equipment_duty_cycle(1800, 0) is None

    def test_negative_period(self):
        assert equipment_duty_cycle(1800, -100) is None

    def test_none_inputs(self):
        assert equipment_duty_cycle(None, 3600) is None
        assert equipment_duty_cycle(1800, None) is None

    def test_zero_runtime(self):
        result = equipment_duty_cycle(0, 3600)
        assert result == 0.0


# ---------------------------------------------------------------------------
# indoor_outdoor_differential
# ---------------------------------------------------------------------------

class TestIndoorOutdoorDifferential:

    def test_warmer_inside(self):
        result = indoor_outdoor_differential(72.0, 30.0)
        assert result == 42.0

    def test_cooler_inside(self):
        result = indoor_outdoor_differential(72.0, 95.0)
        assert result == -23.0

    def test_equal(self):
        result = indoor_outdoor_differential(72.0, 72.0)
        assert result == 0.0

    def test_none_indoor(self):
        assert indoor_outdoor_differential(None, 30.0) is None

    def test_none_outdoor(self):
        assert indoor_outdoor_differential(72.0, None) is None


# ---------------------------------------------------------------------------
# detect_short_cycling
# ---------------------------------------------------------------------------

class TestDetectShortCycling:

    def test_normal_operation(self):
        # 3 cycles in 1 hour, 2700s total = 900s/cycle = 15 min avg
        result = detect_short_cycling(3, 2700, 1.0)
        assert result["is_short_cycling"] is False
        assert result["cycles_per_hour"] == 3.0
        assert result["avg_cycle_minutes"] == 15.0

    def test_too_many_cycles(self):
        # 8 cycles in 1 hour (> 6 max), 4800s = 600s/cycle = 10 min avg
        result = detect_short_cycling(8, 4800, 1.0)
        assert result["is_short_cycling"] is True
        assert result["cycles_per_hour"] == 8.0

    def test_short_duration(self):
        # 4 cycles in 1 hour (ok), but 1200s total = 300s/cycle = 5 min avg (< 10 min)
        result = detect_short_cycling(4, 1200, 1.0)
        assert result["is_short_cycling"] is True
        assert result["avg_cycle_minutes"] == 5.0

    def test_zero_cycles(self):
        result = detect_short_cycling(0, 0, 1.0)
        assert result["is_short_cycling"] is False
        assert result["cycles_per_hour"] == 0.0
        assert result["avg_cycle_minutes"] is None

    def test_none_cycle_count(self):
        result = detect_short_cycling(None, 1000, 1.0)
        assert result["is_short_cycling"] is False

    def test_zero_period(self):
        result = detect_short_cycling(3, 1000, 0)
        assert result["is_short_cycling"] is False

    def test_no_runtime_but_many_cycles(self):
        # High cycle count but no runtime data
        result = detect_short_cycling(10, None, 1.0)
        assert result["is_short_cycling"] is True
        assert result["cycles_per_hour"] == 10.0
        assert result["avg_cycle_minutes"] is None

    def test_two_hour_period(self):
        # 10 cycles in 2 hours = 5/hour (ok)
        result = detect_short_cycling(10, 9000, 2.0)
        assert result["is_short_cycling"] is False
        assert result["cycles_per_hour"] == 5.0
        assert result["avg_cycle_minutes"] == 15.0


# ---------------------------------------------------------------------------
# comfort_index
# ---------------------------------------------------------------------------

class TestComfortIndex:

    def test_perfect_comfort(self):
        # At setpoint, humidity in ideal range
        result = comfort_index(72.0, 72.0, 40.0)
        assert result == 100.0

    def test_at_setpoint_no_humidity(self):
        # At setpoint, no humidity data -> humidity defaults to 100
        result = comfort_index(72.0, 72.0, None)
        # temp_score = 100, humidity_score = 100
        # 100 * 0.7 + 100 * 0.3 = 100
        assert result == 100.0

    def test_far_from_setpoint(self):
        # 5°F off -> temp_score = 0
        result = comfort_index(77.0, 72.0, 40.0)
        # temp_score = 0, humidity_score = 100
        # 0 * 0.7 + 100 * 0.3 = 30
        assert result == 30.0

    def test_beyond_tolerance(self):
        # More than 5°F off -> temp_score = 0
        result = comfort_index(80.0, 72.0, 40.0)
        assert result <= 30.0  # Only humidity component

    def test_low_humidity(self):
        # At setpoint but very low humidity (10%)
        result = comfort_index(72.0, 72.0, 10.0)
        # temp_score = 100, humidity_score = max(0, 100 - (30 - 10) * 2) = 60
        # 100 * 0.7 + 60 * 0.3 = 70 + 18 = 88
        assert result == 88.0

    def test_high_humidity(self):
        # At setpoint but very high humidity (80%)
        result = comfort_index(72.0, 72.0, 80.0)
        # humidity_score = max(0, 100 - (80 - 50) * 2) = max(0, 40) = 40
        # 100 * 0.7 + 40 * 0.3 = 70 + 12 = 82
        assert result == 82.0

    def test_extreme_humidity(self):
        # 100% humidity
        result = comfort_index(72.0, 72.0, 100.0)
        # humidity_score = max(0, 100 - 50 * 2) = 0
        # 100 * 0.7 + 0 * 0.3 = 70
        assert result == 70.0

    def test_none_temps(self):
        assert comfort_index(None, 72.0, 40.0) is None
        assert comfort_index(72.0, None, 40.0) is None

    def test_partial_offset(self):
        # 2.5°F off -> temp_score = 100 - (2.5/5)*100 = 50
        result = comfort_index(74.5, 72.0, 40.0)
        # 50 * 0.7 + 100 * 0.3 = 35 + 30 = 65
        assert result == 65.0


# ---------------------------------------------------------------------------
# recovery_rate
# ---------------------------------------------------------------------------

class TestRecoveryRate:

    def test_normal(self):
        # 5°F in 30 minutes = 10°F/hour
        result = recovery_rate(68.0, 73.0, 30.0)
        assert result == 10.0

    def test_cooling_recovery(self):
        # Cooling: 80 -> 74 in 60 min = 6°F/hour
        result = recovery_rate(80.0, 74.0, 60.0)
        assert result == 6.0

    def test_zero_minutes(self):
        assert recovery_rate(68.0, 73.0, 0) is None

    def test_negative_minutes(self):
        assert recovery_rate(68.0, 73.0, -10) is None

    def test_none_inputs(self):
        assert recovery_rate(None, 73.0, 30.0) is None
        assert recovery_rate(68.0, None, 30.0) is None
        assert recovery_rate(68.0, 73.0, None) is None

    def test_no_change(self):
        result = recovery_rate(72.0, 72.0, 30.0)
        assert result == 0.0


# ---------------------------------------------------------------------------
# temperature_swing
# ---------------------------------------------------------------------------

class TestTemperatureSwing:

    def test_normal(self):
        result = temperature_swing(76.0, 68.0)
        assert result == 8.0

    def test_reversed_inputs(self):
        # Uses abs(), so order doesn't matter
        result = temperature_swing(68.0, 76.0)
        assert result == 8.0

    def test_no_swing(self):
        result = temperature_swing(72.0, 72.0)
        assert result == 0.0

    def test_none_inputs(self):
        assert temperature_swing(None, 68.0) is None
        assert temperature_swing(76.0, None) is None


# ---------------------------------------------------------------------------
# format_running_equipment
# ---------------------------------------------------------------------------

class TestFormatRunningEquipment:

    def test_idle(self):
        assert format_running_equipment(None) == "Idle"
        assert format_running_equipment([]) == "Idle"

    def test_single_known(self):
        assert format_running_equipment(["fan"]) == "Fan"

    def test_multiple_known(self):
        result = format_running_equipment(["compressor_cool_1", "fan"])
        assert result == "Cooling Stage 1, Fan"

    def test_unknown_code(self):
        # Unknown codes get title-cased
        result = format_running_equipment(["some_new_thing"])
        assert result == "Some New Thing"

    def test_mixed_known_unknown(self):
        result = format_running_equipment(["compressor_cool_1", "mystery_device"])
        assert "Cooling Stage 1" in result
        assert "Mystery Device" in result

    def test_all_equipment_types(self):
        from custom_components.buzzbridge.const import EQUIPMENT_MAP
        for code, name in EQUIPMENT_MAP.items():
            result = format_running_equipment([code])
            assert result == name
