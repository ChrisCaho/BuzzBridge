# BuzzBridge - Data Coordinators
# Rev: 1.1
#
# Two DataUpdateCoordinators manage polling:
#
#   FastPollCoordinator (default 5 min):
#     - Thermostat state (temperature, humidity, mode, setpoints, equipment)
#     - Remote sensor readings (temperature, humidity, occupancy)
#     - Air quality data (CO2, VOC, AQ score, accuracy)
#     - Supports "boost mode" — 1-minute polls for 60 minutes via button entity
#
#   SlowPollCoordinator (default 30 min):
#     - Runtime summaries (daily equipment runtimes, degree days)
#     - Thermostat settings (name, model, firmware)
#
# Both coordinators share a single BeestatApi instance and use batch requests
# to minimize API rate limit consumption. Device discovery happens on every
# fast poll — new thermostats trigger HA persistent notifications and device
# registry updates.

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.components.persistent_notification import async_create as pn_create
from homeassistant.util import dt as dt_util

from .api import BeestatApi, BeestatApiError, BeestatAuthError, BeestatRateLimitError
from .const import (
    BOOST_DURATION_MINUTES,
    BOOST_POLL_SECONDS,
    CONF_FAST_POLL_INTERVAL,
    CONF_SLOW_POLL_INTERVAL,
    DATA_THERMOSTATS,
    DEFAULT_FAST_POLL_MINUTES,
    DEFAULT_SLOW_POLL_MINUTES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class FastPollCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for fast-poll data (thermostat state, sensors, air quality).

    Supports boost mode: when activated, polls every 60 seconds for 60 minutes,
    then automatically reverts to the configured interval. Pressing the boost
    button again while already boosted resets the 60-minute timer.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        api: BeestatApi,
        entry: ConfigEntry,
    ) -> None:
        interval = entry.options.get(
            CONF_FAST_POLL_INTERVAL, DEFAULT_FAST_POLL_MINUTES
        )
        self._normal_interval = timedelta(minutes=interval)
        self._api = api
        # Use None to distinguish "never polled" from "polled but found 0 thermostats"
        self._known_thermostat_ids: set[str] | None = None
        self._boost_until = None  # UTC datetime or None

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_fast_poll",
            update_interval=self._normal_interval,
        )

    @callback
    def activate_boost(self) -> None:
        """Switch to high-frequency polling for BOOST_DURATION_MINUTES."""
        self._boost_until = dt_util.utcnow() + timedelta(minutes=BOOST_DURATION_MINUTES)
        self.update_interval = timedelta(seconds=BOOST_POLL_SECONDS)
        _LOGGER.info(
            "Boost polling activated — polling every %ds for %d minutes",
            BOOST_POLL_SECONDS,
            BOOST_DURATION_MINUTES,
        )

    @callback
    def deactivate_boost(self) -> None:
        """Revert to normal polling interval."""
        self._boost_until = None
        self.update_interval = self._normal_interval
        _LOGGER.info("Boost polling deactivated — back to normal interval")

    @property
    def is_boosted(self) -> bool:
        """Return True if boost mode is currently active.

        This is a pure check with no side effects. Boost expiry is handled
        explicitly in _async_update_data.
        """
        if self._boost_until is None:
            return False
        return dt_util.utcnow() < self._boost_until

    @callback
    def update_poll_interval(self, minutes: int) -> None:
        """Update the normal poll interval (called when options change)."""
        self._normal_interval = timedelta(minutes=minutes)
        if not self.is_boosted:
            self.update_interval = self._normal_interval

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch fast-poll data from Beestat API."""
        # Check if boost expired and revert
        if self._boost_until is not None and not self.is_boosted:
            self.deactivate_boost()

        try:
            data = await self._api.fetch_fast_poll_data()
        except BeestatAuthError as err:
            raise ConfigEntryAuthFailed(
                f"Authentication failed: {err}"
            ) from err
        except BeestatRateLimitError as err:
            _LOGGER.warning("Beestat rate limit hit — will retry at next interval")
            raise UpdateFailed(f"Rate limited: {err}") from err
        except BeestatApiError as err:
            raise UpdateFailed(f"API error: {err}") from err

        # Device discovery — detect new/removed thermostats
        current_ids = set(str(tid) for tid in data.get(DATA_THERMOSTATS, {}))

        if self._known_thermostat_ids is not None and current_ids != self._known_thermostat_ids:
            new_ids = current_ids - self._known_thermostat_ids
            removed_ids = self._known_thermostat_ids - current_ids

            if new_ids:
                thermostat_data = data.get(DATA_THERMOSTATS, {})
                names = [
                    thermostat_data.get(tid, {}).get("name", tid) for tid in new_ids
                ]
                pn_create(
                    self.hass,
                    (
                        f"BuzzBridge discovered new thermostat(s): {', '.join(names)}. "
                        "Entities will be created automatically."
                    ),
                    title="BuzzBridge — New Thermostat Found",
                    notification_id=f"{DOMAIN}_new_thermostat",
                )
                _LOGGER.info("New thermostat(s) discovered: %s", names)

            if removed_ids:
                pn_create(
                    self.hass,
                    (
                        f"BuzzBridge lost contact with thermostat ID(s): "
                        f"{', '.join(removed_ids)}. Entities may become unavailable."
                    ),
                    title="BuzzBridge — Thermostat Lost",
                    notification_id=f"{DOMAIN}_lost_thermostat",
                )
                _LOGGER.warning("Thermostat(s) lost: %s", removed_ids)

        self._known_thermostat_ids = current_ids

        return data


class SlowPollCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for slow-poll data (runtime summaries, settings)."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: BeestatApi,
        entry: ConfigEntry,
    ) -> None:
        interval = entry.options.get(
            CONF_SLOW_POLL_INTERVAL, DEFAULT_SLOW_POLL_MINUTES
        )
        self._api = api

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_slow_poll",
            update_interval=timedelta(minutes=interval),
        )

    @callback
    def update_poll_interval(self, minutes: int) -> None:
        """Update the poll interval (called when options change)."""
        self.update_interval = timedelta(minutes=minutes)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch slow-poll data from Beestat API."""
        try:
            data = await self._api.fetch_slow_poll_data()
        except BeestatAuthError as err:
            raise ConfigEntryAuthFailed(
                f"Authentication failed: {err}"
            ) from err
        except BeestatRateLimitError as err:
            _LOGGER.warning("Beestat rate limit hit — will retry at next interval")
            raise UpdateFailed(f"Rate limited: {err}") from err
        except BeestatApiError as err:
            raise UpdateFailed(f"API error: {err}") from err

        return data
