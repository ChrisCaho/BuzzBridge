# BuzzBridge - Button Platform
# Rev: 1.1
#
# Provides a "Boost Polling" button entity per thermostat.
# When pressed, switches fast polling to every 60 seconds for 60 minutes,
# then automatically reverts to the configured interval.
# Useful for debugging and monitoring real-time changes.

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    BOOST_DURATION_MINUTES,
    BOOST_POLL_SECONDS,
    DATA_ECOBEE_THERMOSTATS,
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
    """Set up BuzzBridge button entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    fast_coord: FastPollCoordinator = data["fast_coordinator"]

    entities: list[ButtonEntity] = []

    if fast_coord.data is None:
        _LOGGER.error("BuzzBridge: coordinator data is None during button setup")
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
            name=tstat_name,
            manufacturer=MANUFACTURER,
            model=model_name,
        )

        entities.append(
            BuzzBridgeBoostButton(fast_coord, tstat_id, device_info, tstat_name)
        )

    async_add_entities(entities)


class BuzzBridgeBoostButton(CoordinatorEntity, ButtonEntity):
    """Button to activate boost polling mode.

    Pressing this button switches fast polling from the configured interval
    (default 5 min) to every 60 seconds for 60 minutes, then automatically
    reverts. Pressing again while boosted resets the 60-minute timer.
    """

    def __init__(
        self,
        coordinator: FastPollCoordinator,
        tstat_id: str,
        device_info: DeviceInfo,
        tstat_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._tstat_id = str(tstat_id)
        self._attr_name = f"{tstat_name} Boost Polling"
        self._attr_unique_id = f"{DOMAIN}_{tstat_id}_boost_polling"
        self._attr_device_info = device_info
        self._attr_icon = "mdi:rocket-launch"

    async def async_press(self) -> None:
        """Activate boost mode."""
        self.coordinator.activate_boost()
        # Trigger an immediate refresh
        await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Show boost status."""
        return {
            "boosted": self.coordinator.is_boosted,
            "boost_interval_seconds": BOOST_POLL_SECONDS,
            "boost_duration_minutes": BOOST_DURATION_MINUTES,
        }
