# BuzzBridge - Sensor Platform
# Rev: 1.4
#
# Creates sensor entities for each thermostat and remote sensor discovered
# via the Beestat API. Entity types include:
#
#   Thermostat sensors (per thermostat):
#     - Temperature, humidity, heat/cool setpoints
#     - HVAC mode, running equipment, fan mode
#     - Hold status (type, heat/cool temps, end time)
#     - Air quality (CO2, VOC, AQ score, accuracy) — Premium models only
#     - Filter status (runtime hours, days remaining)
#     - Weather (outdoor temp, humidity, min/max)
#     - Daily runtimes (cool, heat, fan, etc.) from runtime summary
#     - Degree days (heating, cooling)
#     - Calculated: efficiency, duty cycle, comfort index, differential
#
#   Remote sensor entities (per sensor):
#     - Temperature
#     - Humidity (if available)
#     - Occupancy is handled in binary_sensor.py
#
# Entities use a consistent naming scheme: {thermostat_name} {sensor_name}
# Weather sensors are disabled by default (entity_registry_enabled_default=False).

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.util import dt as dt_util
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .air_quality import (
    get_aq_accuracy_label,
    get_aq_score_level,
    get_co2_level,
    get_voc_level,
)
from .api import BeestatApi
from .calculations import (
    comfort_index,
    cooling_efficiency,
    equipment_duty_cycle,
    format_running_equipment,
    heating_efficiency,
    indoor_outdoor_differential,
    temperature_swing,
)
from .const import (
    DATA_ECOBEE_THERMOSTATS,
    DATA_RUNTIME_SUMMARY,
    DATA_SENSORS,
    DATA_THERMOSTATS,
    DEGREE_DAY_UNIT,
    DOMAIN,
    ECOBEE_MODELS,
    MANUFACTURER,
    SECONDS_PER_HOUR,
)
from .coordinator import FastPollCoordinator, SlowPollCoordinator
from .entity import BuzzBridgeConfigEntry

_LOGGER = logging.getLogger(__name__)

# Coordinator-based platform: no parallel update limit needed
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BuzzBridgeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BuzzBridge sensor entities."""
    fast_coord = entry.runtime_data.fast_coordinator
    slow_coord = entry.runtime_data.slow_coordinator

    entities: list[SensorEntity] = []

    # Wait for first data fetch
    if fast_coord.data is None:
        _LOGGER.error("BuzzBridge: coordinator data is None during sensor setup")
        return

    thermostats = fast_coord.data.get(DATA_THERMOSTATS, {})
    ecobee_thermostats = fast_coord.data.get(DATA_ECOBEE_THERMOSTATS, {})

    for tstat_id, tstat in thermostats.items():
        tstat_name = tstat.get("name", f"Thermostat {tstat_id}")
        ecobee_id = str(tstat.get("ecobee_thermostat_id", ""))
        ecobee_data = ecobee_thermostats.get(ecobee_id, {})
        model_number = ecobee_data.get("model_number", "unknown")
        model_name = ECOBEE_MODELS.get(model_number, model_number)

        device_info = DeviceInfo(
            identifiers={(DOMAIN, str(tstat_id))},
            name=f"BuzzBridge {tstat_name}",
            manufacturer=MANUFACTURER,
            model=model_name,
            sw_version=(ecobee_data.get("settings") or {}).get("firmwareVersion"),
        )

        # === Core thermostat sensors (fast poll) ===
        entities.extend([
            BuzzBridgeThermostatSensor(
                fast_coord, tstat_id, device_info, tstat_name,
                key="temperature", translation_key="temperature",
                device_class=SensorDeviceClass.TEMPERATURE,
                unit=UnitOfTemperature.FAHRENHEIT,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            BuzzBridgeThermostatSensor(
                fast_coord, tstat_id, device_info, tstat_name,
                key="humidity", translation_key="humidity",
                device_class=SensorDeviceClass.HUMIDITY,
                unit=PERCENTAGE,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            BuzzBridgeThermostatSensor(
                fast_coord, tstat_id, device_info, tstat_name,
                key="setpoint_heat", translation_key="setpoint_heat",
                device_class=SensorDeviceClass.TEMPERATURE,
                unit=UnitOfTemperature.FAHRENHEIT,
            ),
            BuzzBridgeThermostatSensor(
                fast_coord, tstat_id, device_info, tstat_name,
                key="setpoint_cool", translation_key="setpoint_cool",
                device_class=SensorDeviceClass.TEMPERATURE,
                unit=UnitOfTemperature.FAHRENHEIT,
            ),
        ])

        # === HVAC mode & equipment (from ecobee data) ===
        entities.append(
            BuzzBridgeEcobeeSensor(
                fast_coord, tstat_id, ecobee_id, device_info, tstat_name,
                key_path=["settings", "hvacMode"],
                translation_key="hvac_mode",
            )
        )
        entities.append(
            BuzzBridgeRunningEquipmentSensor(
                fast_coord, tstat_id, ecobee_id, device_info, tstat_name,
            )
        )
        entities.append(
            BuzzBridgeEcobeeSensor(
                fast_coord, tstat_id, ecobee_id, device_info, tstat_name,
                key_path=["runtime", "desiredFanMode"],
                translation_key="fan_mode",
            )
        )

        # === Hold status (from events) ===
        entities.append(
            BuzzBridgeHoldSensor(
                fast_coord, tstat_id, ecobee_id, device_info, tstat_name,
            )
        )

        # === Air quality (Premium models only — uses -5002 to indicate N/A) ===
        runtime = ecobee_data.get("runtime") or {}
        has_aq = BeestatApi.is_value_available(runtime.get("actualAQScore"))

        if has_aq:
            entities.extend([
                BuzzBridgeAirQualitySensor(
                    fast_coord, tstat_id, ecobee_id, device_info, tstat_name,
                    aq_key="actualAQScore", translation_key="aq_score",
                    unit=None, device_class=None,
                    aq_type="score",
                ),
                BuzzBridgeAirQualitySensor(
                    fast_coord, tstat_id, ecobee_id, device_info, tstat_name,
                    aq_key="actualCO2", translation_key="co2",
                    unit="ppm", device_class=SensorDeviceClass.CO2,
                    aq_type="co2",
                ),
                BuzzBridgeAirQualitySensor(
                    fast_coord, tstat_id, ecobee_id, device_info, tstat_name,
                    aq_key="actualVOC", translation_key="voc",
                    unit="ppb",
                    device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
                    aq_type="voc",
                ),
                BuzzBridgeAirQualitySensor(
                    fast_coord, tstat_id, ecobee_id, device_info, tstat_name,
                    aq_key="actualAQAccuracy", translation_key="aq_accuracy",
                    unit=None, device_class=None,
                    aq_type="accuracy",
                ),
            ])

        # === Filter status ===
        filters = tstat.get("filters", {})
        if filters:
            entities.append(
                BuzzBridgeFilterSensor(
                    fast_coord, tstat_id, device_info, tstat_name,
                )
            )

        # === Weather sensors (disabled by default) ===
        entities.extend([
            BuzzBridgeWeatherSensor(
                fast_coord, tstat_id, ecobee_id, device_info, tstat_name,
                key_path=["weather", "forecasts", 0, "temperature"],
                translation_key="outdoor_temperature",
                device_class=SensorDeviceClass.TEMPERATURE,
                unit=UnitOfTemperature.FAHRENHEIT,
            ),
            BuzzBridgeWeatherSensor(
                fast_coord, tstat_id, ecobee_id, device_info, tstat_name,
                key_path=["weather", "forecasts", 0, "relativeHumidity"],
                translation_key="outdoor_humidity",
                device_class=SensorDeviceClass.HUMIDITY,
                unit=PERCENTAGE,
            ),
        ])

        # === Runtime summary sensors (slow poll) ===
        entities.extend([
            BuzzBridgeRuntimeSensor(
                slow_coord, tstat_id, device_info, tstat_name,
                runtime_key="sum_compressor_cool_1",
                translation_key="cooling_runtime",
            ),
            BuzzBridgeRuntimeSensor(
                slow_coord, tstat_id, device_info, tstat_name,
                runtime_key="sum_compressor_heat_1",
                translation_key="heating_runtime",
            ),
            BuzzBridgeRuntimeSensor(
                slow_coord, tstat_id, device_info, tstat_name,
                runtime_key="sum_fan",
                translation_key="fan_runtime",
            ),
            BuzzBridgeDegreeDaySensor(
                slow_coord, tstat_id, device_info, tstat_name,
                key="sum_cooling_degree_days",
                translation_key="cooling_degree_days",
            ),
            BuzzBridgeDegreeDaySensor(
                slow_coord, tstat_id, device_info, tstat_name,
                key="sum_heating_degree_days",
                translation_key="heating_degree_days",
            ),
        ])

        # === Calculated sensors ===
        entities.extend([
            BuzzBridgeComfortSensor(
                fast_coord, tstat_id, device_info, tstat_name,
            ),
            BuzzBridgeDifferentialSensor(
                fast_coord, tstat_id, ecobee_id, device_info, tstat_name,
            ),
        ])

    # === Remote sensor entities ===
    sensors = fast_coord.data.get(DATA_SENSORS, {})
    for sensor_id, sensor_data in sensors.items():
        if sensor_data.get("deleted") or sensor_data.get("inactive"):
            continue

        sensor_name = sensor_data.get("name", f"Sensor {sensor_id}")
        parent_tstat_id = str(sensor_data.get("thermostat_id", ""))
        parent_tstat = thermostats.get(parent_tstat_id, {})
        parent_name = parent_tstat.get("name", "Unknown")
        sensor_type = sensor_data.get("type", "")

        # Avoid "Studio Studio" when sensor name matches parent thermostat name
        if sensor_name.lower() == parent_name.lower():
            remote_device_name = f"BuzzBridge {sensor_name} Sensor"
        else:
            remote_device_name = f"BuzzBridge {parent_name} {sensor_name}"

        device_info = DeviceInfo(
            identifiers={(DOMAIN, f"sensor_{sensor_id}")},
            name=remote_device_name,
            manufacturer=MANUFACTURER,
            model=sensor_type.replace("_", " ").title(),
            via_device=(DOMAIN, parent_tstat_id),
        )

        # Temperature (always available on remote sensors)
        entities.append(
            BuzzBridgeRemoteSensorEntity(
                fast_coord, sensor_id, device_info,
                parent_name, sensor_name,
                value_key="temperature",
                translation_key="remote_temperature",
                device_class=SensorDeviceClass.TEMPERATURE,
                unit=UnitOfTemperature.FAHRENHEIT,
                state_class=SensorStateClass.MEASUREMENT,
            )
        )

        # Humidity (only on thermostat built-in sensors, not all remotes)
        if sensor_data.get("humidity") is not None:
            entities.append(
                BuzzBridgeRemoteSensorEntity(
                    fast_coord, sensor_id, device_info,
                    parent_name, sensor_name,
                    value_key="humidity",
                    translation_key="remote_humidity",
                    device_class=SensorDeviceClass.HUMIDITY,
                    unit=PERCENTAGE,
                    state_class=SensorStateClass.MEASUREMENT,
                )
            )

    async_add_entities(entities)


# =============================================================================
# Base entity classes
# =============================================================================


class BuzzBridgeThermostatSensor(CoordinatorEntity, SensorEntity):
    """Sensor that reads a top-level key from thermostat data."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FastPollCoordinator,
        tstat_id: str,
        device_info: DeviceInfo,
        tstat_name: str,
        *,
        key: str,
        translation_key: str,
        device_class: SensorDeviceClass | None = None,
        unit: str | None = None,
        state_class: SensorStateClass | None = None,
        entity_category: EntityCategory | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._tstat_id = str(tstat_id)
        self._key = key
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{DOMAIN}_{tstat_id}_{key}"
        self._attr_device_info = device_info
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = state_class
        self._attr_entity_category = entity_category

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        if self.coordinator.data is None:
            return None
        tstat = self.coordinator.data.get(DATA_THERMOSTATS, {}).get(self._tstat_id, {})
        return tstat.get(self._key)


class BuzzBridgeEcobeeSensor(CoordinatorEntity, SensorEntity):
    """Sensor that reads a nested key path from ecobee thermostat data."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FastPollCoordinator,
        tstat_id: str,
        ecobee_id: str,
        device_info: DeviceInfo,
        tstat_name: str,
        *,
        key_path: list[str | int],
        translation_key: str,
        device_class: SensorDeviceClass | None = None,
        unit: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._tstat_id = str(tstat_id)
        self._ecobee_id = ecobee_id
        self._key_path = key_path
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{DOMAIN}_{tstat_id}_{'_'.join(str(k) for k in key_path)}"
        self._attr_device_info = device_info
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit

    def _get_ecobee_data(self) -> dict[str, Any]:
        """Get the ecobee thermostat data dict. Safe if any key is null."""
        if self.coordinator.data is None:
            return {}
        ecobee_all = self.coordinator.data.get(DATA_ECOBEE_THERMOSTATS) or {}
        return ecobee_all.get(self._ecobee_id) or {}

    @property
    def native_value(self) -> Any:
        """Navigate the key path to find the value."""
        data = self._get_ecobee_data()
        for key in self._key_path:
            if isinstance(data, dict):
                data = data.get(key)
            elif isinstance(data, list) and isinstance(key, int) and key < len(data):
                data = data[key]
            else:
                return None
            if data is None:
                return None
        return data


class BuzzBridgeRunningEquipmentSensor(CoordinatorEntity, SensorEntity):
    """Shows currently running equipment in human-readable form."""

    _attr_has_entity_name = True
    _attr_translation_key = "running_equipment"

    def __init__(
        self,
        coordinator: FastPollCoordinator,
        tstat_id: str,
        ecobee_id: str,
        device_info: DeviceInfo,
        tstat_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._tstat_id = str(tstat_id)
        self._ecobee_id = ecobee_id
        self._attr_unique_id = f"{DOMAIN}_{tstat_id}_running_equipment"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> str:
        """Return human-readable equipment string."""
        if self.coordinator.data is None:
            return "Unknown"
        tstat = self.coordinator.data.get(DATA_THERMOSTATS, {}).get(self._tstat_id, {})
        equipment = tstat.get("running_equipment") or []
        if isinstance(equipment, str):
            equipment = [e.strip() for e in equipment.split(",") if e.strip()]
        return format_running_equipment(equipment)


class BuzzBridgeHoldSensor(CoordinatorEntity, SensorEntity):
    """Shows the current hold status with details as attributes."""

    _attr_has_entity_name = True
    _attr_translation_key = "hold_status"

    def __init__(
        self,
        coordinator: FastPollCoordinator,
        tstat_id: str,
        ecobee_id: str,
        device_info: DeviceInfo,
        tstat_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._tstat_id = str(tstat_id)
        self._ecobee_id = ecobee_id
        self._attr_unique_id = f"{DOMAIN}_{tstat_id}_hold_status"
        self._attr_device_info = device_info

    def _get_active_hold(self) -> dict[str, Any] | None:
        """Find the first running hold event."""
        if self.coordinator.data is None:
            return None
        ecobee_all = self.coordinator.data.get(DATA_ECOBEE_THERMOSTATS) or {}
        ecobee = ecobee_all.get(self._ecobee_id) or {}
        for event in (ecobee.get("events") or []):
            if event.get("type") == "hold" and event.get("running"):
                return event
        return None

    @property
    def native_value(self) -> str:
        """Return simple hold state — details are in attributes."""
        hold = self._get_active_hold()
        if hold is None:
            return "None"
        if hold.get("isIndefinite"):
            return "Indefinite Hold"
        return "Hold"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return hold details as attributes."""
        hold = self._get_active_hold()
        if hold is None:
            return {"active": False}

        attrs: dict[str, Any] = {
            "active": True,
            "type": hold.get("name", "unknown"),
            "indefinite": hold.get("isIndefinite", False),
            "fan": hold.get("fan", "auto"),
        }

        if not hold.get("isIndefinite"):
            attrs["end_date"] = hold.get("endDate")
            attrs["end_time"] = hold.get("endTime")

        # Hold temperatures are x10 in ecobee events
        cool_hold = hold.get("coolHoldTemp")
        heat_hold = hold.get("heatHoldTemp")
        if cool_hold is not None:
            attrs["cool_hold_temp"] = BeestatApi.ecobee_temp_to_float(cool_hold)
        if heat_hold is not None:
            attrs["heat_hold_temp"] = BeestatApi.ecobee_temp_to_float(heat_hold)

        return attrs


class BuzzBridgeAirQualitySensor(CoordinatorEntity, SensorEntity):
    """Air quality sensor with human-readable level as attributes.

    The ecobee Premium's Bosch BME680 gas sensor measures VOCs and estimates
    CO2. Beestat normalizes the raw AQ score to 0-100 (higher = better).
    CO2 is in ppm, VOC in ppb.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FastPollCoordinator,
        tstat_id: str,
        ecobee_id: str,
        device_info: DeviceInfo,
        tstat_name: str,
        *,
        aq_key: str,
        translation_key: str,
        unit: str | None,
        device_class: SensorDeviceClass | None,
        aq_type: str,
    ) -> None:
        super().__init__(coordinator)
        self._tstat_id = str(tstat_id)
        self._ecobee_id = ecobee_id
        self._aq_key = aq_key
        self._aq_type = aq_type
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{DOMAIN}_{tstat_id}_{aq_key}"
        self._attr_device_info = device_info
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        if unit:
            self._attr_state_class = SensorStateClass.MEASUREMENT

    def _get_runtime(self) -> dict[str, Any]:
        """Get the ecobee runtime dict. Safe if any key is null."""
        if self.coordinator.data is None:
            return {}
        ecobee_all = self.coordinator.data.get(DATA_ECOBEE_THERMOSTATS) or {}
        ecobee = ecobee_all.get(self._ecobee_id) or {}
        return ecobee.get("runtime") or {}

    @property
    def native_value(self) -> float | int | str | None:
        """Return the air quality value."""
        runtime = self._get_runtime()
        value = runtime.get(self._aq_key)

        if not BeestatApi.is_value_available(value):
            return None

        if self._aq_type == "accuracy":
            label = get_aq_accuracy_label(value)
            return label[0] if label else None

        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return human-readable air quality interpretation."""
        runtime = self._get_runtime()
        value = runtime.get(self._aq_key)

        if not BeestatApi.is_value_available(value):
            return {}

        if self._aq_type == "score":
            level = get_aq_score_level(value)
            return level if level else {}

        if self._aq_type == "co2":
            level = get_co2_level(value)
            return level if level else {}

        if self._aq_type == "voc":
            level = get_voc_level(value)
            return level if level else {}

        if self._aq_type == "accuracy":
            label = get_aq_accuracy_label(value)
            if label:
                return {"level": label[0], "description": label[1]}
            return {}

        return {}


class BuzzBridgeFilterSensor(CoordinatorEntity, SensorEntity):
    """Filter runtime and estimated days remaining."""

    _attr_has_entity_name = True
    _attr_translation_key = "filter_runtime"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: FastPollCoordinator,
        tstat_id: str,
        device_info: DeviceInfo,
        tstat_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._tstat_id = str(tstat_id)
        self._attr_unique_id = f"{DOMAIN}_{tstat_id}_filter_runtime"
        self._attr_device_info = device_info
        self._attr_native_unit_of_measurement = UnitOfTime.HOURS
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self) -> float | None:
        """Return filter runtime in hours."""
        if self.coordinator.data is None:
            return None
        tstat = self.coordinator.data.get(DATA_THERMOSTATS, {}).get(self._tstat_id, {})
        filters = tstat.get("filters", {})
        for _filter_type, fdata in filters.items():
            runtime_seconds = fdata.get("runtime")
            if runtime_seconds is not None:
                return round(runtime_seconds / SECONDS_PER_HOUR, 1)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return filter details."""
        if self.coordinator.data is None:
            return {}
        tstat = self.coordinator.data.get(DATA_THERMOSTATS, {}).get(self._tstat_id, {})
        filters = tstat.get("filters", {})
        attrs: dict[str, Any] = {}
        for filter_type, fdata in filters.items():
            attrs["filter_type"] = filter_type
            attrs["life"] = fdata.get("life")
            attrs["life_units"] = fdata.get("life_units")
            attrs["last_changed"] = fdata.get("last_changed")

            # Estimate days remaining
            life = fdata.get("life")
            life_units = fdata.get("life_units")
            runtime_seconds = fdata.get("runtime", 0)
            last_changed = fdata.get("last_changed")

            if life and life_units and last_changed:
                try:
                    from datetime import datetime
                    changed_date = datetime.strptime(last_changed, "%Y-%m-%d")
                    now = dt_util.now().replace(tzinfo=None)
                    days_used = (now - changed_date).days
                    total_days = life * (30 if life_units == "month" else 1)
                    remaining = max(0, total_days - days_used)
                    attrs["days_remaining"] = remaining
                except (ValueError, TypeError):
                    pass

        return attrs


class BuzzBridgeWeatherSensor(BuzzBridgeEcobeeSensor):
    """Weather sensor — disabled by default."""

    _attr_entity_registry_enabled_default = False


class BuzzBridgeRuntimeSensor(CoordinatorEntity, SensorEntity):
    """Daily equipment runtime from the slow-poll runtime summary."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SlowPollCoordinator,
        tstat_id: str,
        device_info: DeviceInfo,
        tstat_name: str,
        *,
        runtime_key: str,
        translation_key: str,
    ) -> None:
        super().__init__(coordinator)
        self._tstat_id = str(tstat_id)
        self._runtime_key = runtime_key
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{DOMAIN}_{tstat_id}_{runtime_key}"
        self._attr_device_info = device_info
        self._attr_native_unit_of_measurement = UnitOfTime.HOURS
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    def _get_latest_summary(self) -> dict[str, Any]:
        """Get the most recent runtime summary for this thermostat."""
        if self.coordinator.data is None:
            return {}
        summaries = self.coordinator.data.get(DATA_RUNTIME_SUMMARY, {})
        # Summaries are keyed by ID; find the latest for our thermostat
        latest: dict[str, Any] = {}
        latest_date = ""
        for _sid, summary in summaries.items():
            if str(summary.get("thermostat_id")) == self._tstat_id:
                date = summary.get("date", "")
                if date > latest_date:
                    latest_date = date
                    latest = summary
        return latest

    @property
    def native_value(self) -> float | None:
        """Return runtime in hours."""
        summary = self._get_latest_summary()
        seconds = summary.get(self._runtime_key)
        if seconds is None:
            return None
        return round(seconds / SECONDS_PER_HOUR, 2)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the date this summary covers."""
        summary = self._get_latest_summary()
        date = summary.get("date")
        if date:
            return {"date": date}
        return {}


class BuzzBridgeDegreeDaySensor(CoordinatorEntity, SensorEntity):
    """Heating or Cooling Degree Days from runtime summary.

    Degree days measure energy demand based on outdoor temperature.
    Base: 65°F. If avg outdoor temp is 55°F → 10 Heating Degree Days.
    If 80°F → 15 Cooling Degree Days. Higher = more energy needed.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SlowPollCoordinator,
        tstat_id: str,
        device_info: DeviceInfo,
        tstat_name: str,
        *,
        key: str,
        translation_key: str,
    ) -> None:
        super().__init__(coordinator)
        self._tstat_id = str(tstat_id)
        self._key = key
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{DOMAIN}_{tstat_id}_{key}"
        self._attr_device_info = device_info
        self._attr_native_unit_of_measurement = DEGREE_DAY_UNIT
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    def _get_latest_summary(self) -> dict[str, Any]:
        """Get the most recent runtime summary for this thermostat."""
        if self.coordinator.data is None:
            return {}
        summaries = self.coordinator.data.get(DATA_RUNTIME_SUMMARY, {})
        latest: dict[str, Any] = {}
        latest_date = ""
        for _sid, summary in summaries.items():
            if str(summary.get("thermostat_id")) == self._tstat_id:
                date = summary.get("date", "")
                if date > latest_date:
                    latest_date = date
                    latest = summary
        return latest

    @property
    def native_value(self) -> float | None:
        """Return degree days value."""
        summary = self._get_latest_summary()
        value = summary.get(self._key)
        if value is None:
            return None
        return round(float(value), 1)


class BuzzBridgeComfortSensor(CoordinatorEntity, SensorEntity):
    """Comfort index: 0-100 based on temperature accuracy and humidity."""

    _attr_has_entity_name = True
    _attr_translation_key = "comfort_index"

    def __init__(
        self,
        coordinator: FastPollCoordinator,
        tstat_id: str,
        device_info: DeviceInfo,
        tstat_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._tstat_id = str(tstat_id)
        self._attr_unique_id = f"{DOMAIN}_{tstat_id}_comfort_index"
        self._attr_device_info = device_info
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Calculate comfort index from current readings."""
        if self.coordinator.data is None:
            return None
        tstat = self.coordinator.data.get(DATA_THERMOSTATS, {}).get(self._tstat_id, {})
        return comfort_index(
            tstat.get("temperature"),
            tstat.get("setpoint_cool") or tstat.get("setpoint_heat"),
            tstat.get("humidity"),
        )


class BuzzBridgeDifferentialSensor(CoordinatorEntity, SensorEntity):
    """Indoor vs outdoor temperature differential."""

    _attr_has_entity_name = True
    _attr_translation_key = "temp_differential"

    def __init__(
        self,
        coordinator: FastPollCoordinator,
        tstat_id: str,
        ecobee_id: str,
        device_info: DeviceInfo,
        tstat_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._tstat_id = str(tstat_id)
        self._ecobee_id = ecobee_id
        self._attr_unique_id = f"{DOMAIN}_{tstat_id}_temp_differential"
        self._attr_device_info = device_info
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float | None:
        """Calculate indoor - outdoor temperature."""
        if self.coordinator.data is None:
            return None
        tstat = self.coordinator.data.get(DATA_THERMOSTATS, {}).get(self._tstat_id, {})
        indoor = tstat.get("temperature")

        ecobee_all = self.coordinator.data.get(DATA_ECOBEE_THERMOSTATS) or {}
        ecobee = ecobee_all.get(self._ecobee_id) or {}
        weather = ecobee.get("weather") or {}
        forecasts = weather.get("forecasts") or []
        first = forecasts[0] if forecasts else None
        outdoor = first.get("temperature") if isinstance(first, dict) else None

        return indoor_outdoor_differential(indoor, outdoor)


class BuzzBridgeRemoteSensorEntity(CoordinatorEntity, SensorEntity):
    """Sensor entity for a remote sensor (temperature, humidity)."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FastPollCoordinator,
        sensor_id: str,
        device_info: DeviceInfo,
        parent_name: str,
        sensor_name: str,
        *,
        value_key: str,
        translation_key: str,
        device_class: SensorDeviceClass | None = None,
        unit: str | None = None,
        state_class: SensorStateClass | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._sensor_id = str(sensor_id)
        self._value_key = value_key
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{DOMAIN}_sensor_{sensor_id}_{value_key}"
        self._attr_device_info = device_info
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = state_class

    @property
    def native_value(self) -> Any:
        """Return the sensor reading."""
        if self.coordinator.data is None:
            return None
        sensor = self.coordinator.data.get(DATA_SENSORS, {}).get(self._sensor_id, {})
        return sensor.get(self._value_key)
