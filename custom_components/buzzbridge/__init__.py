# BuzzBridge - Integration Setup
# Rev: 1.1
#
# Entry point for the BuzzBridge custom integration. Handles:
#   - Creating the BeestatApi client with HA's shared aiohttp session
#   - Setting up Fast and Slow poll coordinators
#   - Forwarding platform setup (sensor, binary_sensor, button)
#   - Options update listener for poll interval changes
#   - Clean unload

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BeestatApi
from .const import (
    CONF_API_KEY,
    CONF_FAST_POLL_INTERVAL,
    CONF_SLOW_POLL_INTERVAL,
    DEFAULT_FAST_POLL_MINUTES,
    DEFAULT_SLOW_POLL_MINUTES,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import FastPollCoordinator, SlowPollCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BuzzBridge from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)
    api = BeestatApi(session, entry.data[CONF_API_KEY])

    fast_coordinator = FastPollCoordinator(hass, api, entry)
    slow_coordinator = SlowPollCoordinator(hass, api, entry)

    # Store data BEFORE first refresh so async_unload_entry can clean up
    # if ConfigEntryNotReady is raised during refresh
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "fast_coordinator": fast_coordinator,
        "slow_coordinator": slow_coordinator,
    }

    # Fetch initial data — raises ConfigEntryNotReady on failure
    await fast_coordinator.async_config_entry_first_refresh()
    await slow_coordinator.async_config_entry_first_refresh()

    # Set up all platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Listen for options changes (poll intervals)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    _LOGGER.info("BuzzBridge setup complete for entry %s", entry.entry_id)
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update — adjust poll intervals without restart."""
    data = hass.data[DOMAIN].get(entry.entry_id)
    if not data:
        return

    fast_coord: FastPollCoordinator = data["fast_coordinator"]
    slow_coord: SlowPollCoordinator = data["slow_coordinator"]

    fast_minutes = entry.options.get(
        CONF_FAST_POLL_INTERVAL, DEFAULT_FAST_POLL_MINUTES
    )
    slow_minutes = entry.options.get(
        CONF_SLOW_POLL_INTERVAL, DEFAULT_SLOW_POLL_MINUTES
    )

    fast_coord.update_poll_interval(fast_minutes)
    slow_coord.update_poll_interval(slow_minutes)

    _LOGGER.info(
        "BuzzBridge poll intervals updated: fast=%dmin, slow=%dmin",
        fast_minutes,
        slow_minutes,
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a BuzzBridge config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        _LOGGER.info("BuzzBridge unloaded for entry %s", entry.entry_id)

    return unload_ok
