# BuzzBridge - Integration Setup
# Rev: 1.4
#
# Entry point for the BuzzBridge custom integration. Handles:
#   - Creating the BeestatApi client with HA's shared aiohttp session
#   - Setting up Fast and Slow poll coordinators
#   - Forwarding platform setup (sensor, binary_sensor, button)
#   - Options update listener for poll interval changes
#   - Entity ID migration (adds prefix to legacy entity IDs)
#   - Clean unload
#   - Device cleanup (prevents removing active devices)

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant, valid_entity_id
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import slugify

from .api import BeestatApi
from .const import (
    CONF_API_KEY,
    CONF_FAST_POLL_INTERVAL,
    CONF_SLOW_POLL_INTERVAL,
    DATA_SENSORS,
    DATA_THERMOSTATS,
    DEFAULT_FAST_POLL_MINUTES,
    DEFAULT_SLOW_POLL_MINUTES,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import FastPollCoordinator, SlowPollCoordinator
from .entity import BuzzBridgeConfigEntry, BuzzBridgeData, get_device_prefix

_LOGGER = logging.getLogger(__name__)


def _migrate_entity_ids(hass: HomeAssistant, entry: BuzzBridgeConfigEntry) -> None:
    """Migrate entity IDs to include the device prefix if missing.

    When the configurable prefix was added in v1.5, existing entities kept
    their old IDs (e.g. sensor.home_temperature). This renames them to
    include the prefix (e.g. sensor.buzzbridge_home_temperature) so entity
    IDs are consistent with the device names.
    """
    prefix_slug = slugify(get_device_prefix(entry))
    if not prefix_slug:
        return  # No prefix configured, nothing to migrate

    ent_reg = er.async_get(hass)
    entries = er.async_entries_for_config_entry(ent_reg, entry.entry_id)

    _LOGGER.warning(
        "BuzzBridge entity migration: prefix=%r, found %d entities for entry %s",
        prefix_slug, len(entries), entry.entry_id,
    )

    migrated = 0
    skipped = 0
    for entity_entry in entries:
        old_slug = entity_entry.entity_id.split(".", 1)[1]

        if old_slug.startswith(f"{prefix_slug}_"):
            skipped += 1
            continue  # Already has the prefix

        new_entity_id = f"{entity_entry.domain}.{prefix_slug}_{old_slug}"

        if not valid_entity_id(new_entity_id):
            _LOGGER.warning(
                "Skipping migration of %s: %s is not a valid entity ID",
                entity_entry.entity_id, new_entity_id,
            )
            continue

        if ent_reg.async_get(new_entity_id):
            _LOGGER.warning(
                "Skipping migration of %s: %s already exists",
                entity_entry.entity_id, new_entity_id,
            )
            continue

        _LOGGER.warning(
            "Migrating entity ID: %s -> %s", entity_entry.entity_id, new_entity_id
        )
        ent_reg.async_update_entity(
            entity_entry.entity_id, new_entity_id=new_entity_id
        )
        migrated += 1

    _LOGGER.warning(
        "BuzzBridge entity migration complete: %d migrated, %d already correct",
        migrated, skipped,
    )


async def async_setup_entry(hass: HomeAssistant, entry: BuzzBridgeConfigEntry) -> bool:
    """Set up BuzzBridge from a config entry."""
    session = async_get_clientsession(hass)
    api = BeestatApi(session, entry.data[CONF_API_KEY])

    fast_coordinator = FastPollCoordinator(hass, api, entry)
    slow_coordinator = SlowPollCoordinator(hass, api, entry)

    # Store runtime data BEFORE first refresh so async_unload_entry can clean
    # up if ConfigEntryNotReady is raised during refresh
    entry.runtime_data = BuzzBridgeData(
        api=api,
        fast_coordinator=fast_coordinator,
        slow_coordinator=slow_coordinator,
    )

    # Fetch initial data — raises ConfigEntryNotReady on failure
    await fast_coordinator.async_config_entry_first_refresh()
    await slow_coordinator.async_config_entry_first_refresh()

    # Set up all platforms (creates entities in the registry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Migrate entity IDs to include the prefix AFTER entities are created.
    # This handles both upgrades from pre-v1.5 and fresh installs where HA
    # may not include the device name prefix in auto-generated entity IDs.
    _migrate_entity_ids(hass, entry)

    # Listen for options changes (poll intervals)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    _LOGGER.info("BuzzBridge setup complete for entry %s", entry.entry_id)
    return True


async def _async_options_updated(
    hass: HomeAssistant, entry: BuzzBridgeConfigEntry
) -> None:
    """Handle options update — adjust poll intervals without restart."""
    data = entry.runtime_data

    fast_minutes = entry.options.get(
        CONF_FAST_POLL_INTERVAL, DEFAULT_FAST_POLL_MINUTES
    )
    slow_minutes = entry.options.get(
        CONF_SLOW_POLL_INTERVAL, DEFAULT_SLOW_POLL_MINUTES
    )

    data.fast_coordinator.update_poll_interval(fast_minutes)
    data.slow_coordinator.update_poll_interval(slow_minutes)

    _LOGGER.info(
        "BuzzBridge poll intervals updated: fast=%dmin, slow=%dmin",
        fast_minutes,
        slow_minutes,
    )


async def async_unload_entry(
    hass: HomeAssistant, entry: BuzzBridgeConfigEntry
) -> bool:
    """Unload a BuzzBridge config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        _LOGGER.info("BuzzBridge unloaded for entry %s", entry.entry_id)

    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    entry: BuzzBridgeConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Allow manual removal of BuzzBridge devices from the UI.

    Only allows removal if the device is no longer present in coordinator data
    (e.g., a thermostat was removed from the ecobee account or a remote sensor
    was deleted). Active devices cannot be removed.
    """
    fast_coord = entry.runtime_data.fast_coordinator
    if fast_coord.data is None:
        return True  # No data to check against, allow removal

    # Check if any device identifier is still present in coordinator data
    for identifier in device_entry.identifiers:
        if identifier[0] != DOMAIN:
            continue
        device_id = identifier[1]

        # Check thermostats (identifier = tstat_id)
        if device_id in (fast_coord.data.get(DATA_THERMOSTATS) or {}):
            _LOGGER.warning(
                "Cannot remove device %s — thermostat still active", device_id
            )
            return False

        # Check remote sensors (identifier = "sensor_{sensor_id}")
        if device_id.startswith("sensor_"):
            sensor_id = device_id[7:]  # Strip "sensor_" prefix
            sensors = fast_coord.data.get(DATA_SENSORS) or {}
            sensor = sensors.get(sensor_id, {})
            if sensor and not sensor.get("deleted") and not sensor.get("inactive"):
                _LOGGER.warning(
                    "Cannot remove device %s — sensor still active", device_id
                )
                return False

    return True
