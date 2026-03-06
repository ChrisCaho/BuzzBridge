# BuzzBridge - Binary Sensor Platform
# Rev: 1.1
#
# Binary sensors for:
#   - Remote sensor occupancy (motion detection via ecobee sensors)
#   - Thermostat online/connected status

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DATA_ECOBEE_THERMOSTATS,
    DATA_SENSORS,
    DATA_THERMOSTATS,
    DOMAIN,
    ECOBEE_MODELS,
    MANUFACTURER,
)
from .coordinator import FastPollCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BuzzBridge binary sensor entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    fast_coord: FastPollCoordinator = data["fast_coordinator"]

    entities: list[BinarySensorEntity] = []

    if fast_coord.data is None:
        _LOGGER.error("BuzzBridge: coordinator data is None during binary_sensor setup")
        return

    thermostats = fast_coord.data.get(DATA_THERMOSTATS, {})
    ecobee_thermostats = fast_coord.data.get(DATA_ECOBEE_THERMOSTATS, {})

    # Thermostat online status
    for tstat_id, tstat in thermostats.items():
        tstat_name = tstat.get("name", f"Thermostat {tstat_id}")
        ecobee_id = str(tstat.get("ecobee_thermostat_id", ""))
        ecobee_data = ecobee_thermostats.get(ecobee_id, {})
        model_number = ecobee_data.get("model_number", "unknown")
        model_name = ECOBEE_MODELS.get(model_number, model_number)

        device_info = DeviceInfo(
            identifiers={(DOMAIN, str(tstat_id))},
            name=tstat_name,
            manufacturer=MANUFACTURER,
            model=model_name,
        )

        entities.append(
            BuzzBridgeOnlineSensor(
                fast_coord, tstat_id, ecobee_id, device_info, tstat_name,
            )
        )

    # Remote sensor occupancy
    sensors = fast_coord.data.get(DATA_SENSORS, {})
    for sensor_id, sensor_data in sensors.items():
        if sensor_data.get("deleted") or sensor_data.get("inactive"):
            continue

        # Only add occupancy if the sensor has it
        has_occupancy = any(
            cap.get("type") == "occupancy"
            for cap in sensor_data.get("capability", [])
        )
        if not has_occupancy:
            continue

        sensor_name = sensor_data.get("name", f"Sensor {sensor_id}")
        parent_tstat_id = str(sensor_data.get("thermostat_id", ""))
        parent_tstat = thermostats.get(parent_tstat_id, {})
        parent_name = parent_tstat.get("name", "Unknown")

        device_info = DeviceInfo(
            identifiers={(DOMAIN, f"sensor_{sensor_id}")},
            name=f"{parent_name} {sensor_name}",
            manufacturer=MANUFACTURER,
            model=sensor_data.get("type", "").replace("_", " ").title(),
            via_device=(DOMAIN, parent_tstat_id),
        )

        entities.append(
            BuzzBridgeOccupancySensor(
                fast_coord, sensor_id, device_info, parent_name, sensor_name,
            )
        )

    async_add_entities(entities)


class BuzzBridgeOnlineSensor(CoordinatorEntity, BinarySensorEntity):
    """Thermostat connectivity status."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

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
        self._attr_name = f"{tstat_name} Online"
        self._attr_unique_id = f"{DOMAIN}_{tstat_id}_online"
        self._attr_device_info = device_info

    @property
    def is_on(self) -> bool | None:
        """Return True if thermostat is connected."""
        if self.coordinator.data is None:
            return None
        ecobee = (
            self.coordinator.data
            .get(DATA_ECOBEE_THERMOSTATS, {})
            .get(self._ecobee_id, {})
        )
        connected = ecobee.get("runtime", {}).get("connected")
        if isinstance(connected, bool):
            return connected
        if isinstance(connected, str):
            return connected.lower() == "true"
        return None


class BuzzBridgeOccupancySensor(CoordinatorEntity, BinarySensorEntity):
    """Remote sensor occupancy/motion detection."""

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(
        self,
        coordinator: FastPollCoordinator,
        sensor_id: str,
        device_info: DeviceInfo,
        parent_name: str,
        sensor_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._sensor_id = str(sensor_id)
        self._attr_name = f"{parent_name} {sensor_name} Occupancy"
        self._attr_unique_id = f"{DOMAIN}_sensor_{sensor_id}_occupancy"
        self._attr_device_info = device_info

    @property
    def is_on(self) -> bool | None:
        """Return True if occupancy detected."""
        if self.coordinator.data is None:
            return None
        sensor = self.coordinator.data.get(DATA_SENSORS, {}).get(self._sensor_id, {})
        occ = sensor.get("occupancy")
        if isinstance(occ, bool):
            return occ
        if isinstance(occ, str):
            return occ.lower() == "true"
        return None
