# BuzzBridge - Integration Setup
# Rev: 1.6
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


def _migrate_naming(hass: HomeAssistant, entry: BuzzBridgeConfigEntry) -> None:
    """Migrate device names and entity IDs to the standardized convention.

    Device naming: {prefix} {type} {room}
      - Thermostats:      {prefix} Thermostat {name}
      - Base sensors:     {prefix} Base {name}
      - Remote sensors:   {prefix} Remote {name}

    Entity IDs follow from device name + entity name:
      sensor.{prefix_slug}_thermostat_{room_slug}_{measurement}

    NOTE: HA automatically updates device.name from DeviceInfo during platform
    setup, which runs BEFORE this function. Therefore we CANNOT rely on
    device.name differing from expected to detect stale entity IDs. Instead,
    we compute each entity's expected entity_id directly and compare against
    the actual entity_id.

    Also runs on prefix changes (reconfigure) to update all names.
    """
    prefix = get_device_prefix(entry)

    fast_coord = entry.runtime_data.fast_coordinator
    if fast_coord.data is None:
        return

    thermostats = fast_coord.data.get(DATA_THERMOSTATS, {})
    sensors = fast_coord.data.get(DATA_SENSORS, {})

    # Build expected device names keyed by device identifier
    expected_names: dict[str, str] = {}

    for tstat_id, tstat in thermostats.items():
        tstat_name = tstat.get("name") or f"Thermostat {tstat_id}"
        expected_names[str(tstat_id)] = (
            f"{prefix} Thermostat {tstat_name}" if prefix
            else f"Thermostat {tstat_name}"
        )

    for sensor_id, sensor_data in sensors.items():
        if sensor_data.get("deleted") or sensor_data.get("inactive"):
            continue
        sensor_name = sensor_data.get("name") or f"Sensor {sensor_id}"
        sensor_type = sensor_data.get("type", "")
        type_prefix = "Base" if sensor_type == "thermostat" else "Remote"
        expected_names[f"sensor_{sensor_id}"] = (
            f"{prefix} {type_prefix} {sensor_name}" if prefix
            else f"{type_prefix} {sensor_name}"
        )

    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    devices = dr.async_entries_for_config_entry(dev_reg, entry.entry_id)
    all_entities = er.async_entries_for_config_entry(ent_reg, entry.entry_id)

    # Map device_id -> expected device name for entity lookups
    device_expected_name: dict[str, str] = {}

    # Group entities by device_id for efficient lookup
    entities_by_device: dict[str, list] = {}
    for ent in all_entities:
        if ent.device_id:
            entities_by_device.setdefault(ent.device_id, []).append(ent)

    migrated_devices = 0
    migrated_entities = 0

    # --- Phase 1: Fix device names and name_by_user ---
    for device in devices:
        # Find expected name from device identifiers
        expected = None
        for ident_domain, ident_id in device.identifiers:
            if ident_domain == DOMAIN and ident_id in expected_names:
                expected = expected_names[ident_id]
                break
        if expected is None:
            continue

        # Record the mapping for phase 2
        device_expected_name[device.id] = expected

        # Clear stale name_by_user so integration-provided name takes effect
        if device.name_by_user:
            _LOGGER.info(
                "Clearing name_by_user %r for device %r",
                device.name_by_user, device.name,
            )
            dev_reg.async_update_device(device.id, name_by_user=None)

        # Update device name if it differs
        if device.name != expected:
            _LOGGER.info("Updating device name: %r -> %r", device.name, expected)
            dev_reg.async_update_device(device.id, name=expected)
            migrated_devices += 1

    # --- Phase 2: Fix entity IDs based on expected device name + original_name ---
    # This does NOT depend on whether device.name matched — it compares each
    # entity's actual ID against the computed expected ID directly, so it works
    # even when HA has already updated device.name during platform setup.
    for device_id, expected_dev_name in device_expected_name.items():
        expected_dev_slug = slugify(expected_dev_name)

        for ent in entities_by_device.get(device_id, []):
            # If there is no original_name we cannot compute the expected ID
            if ent.original_name is None:
                continue

            expected_entity_id = (
                f"{ent.domain}.{expected_dev_slug}_{slugify(ent.original_name)}"
            )
            old_eid = ent.entity_id

            if old_eid == expected_entity_id:
                continue  # Already correct

            if not valid_entity_id(expected_entity_id):
                _LOGGER.warning(
                    "Skipping entity migration: %s -> %s (invalid entity ID)",
                    old_eid, expected_entity_id,
                )
                continue

            if ent_reg.async_get(expected_entity_id):
                _LOGGER.warning(
                    "Skipping entity migration: %s -> %s (target already exists)",
                    old_eid, expected_entity_id,
                )
                continue

            _LOGGER.info("Migrating entity ID: %s -> %s", old_eid, expected_entity_id)
            ent_reg.async_update_entity(old_eid, new_entity_id=expected_entity_id)
            migrated_entities += 1

    if migrated_devices or migrated_entities:
        _LOGGER.info(
            "BuzzBridge naming migration: %d devices, %d entities updated",
            migrated_devices, migrated_entities,
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

    # Migrate device names and entity IDs to standardized convention AFTER
    # entities are created. Handles upgrades from any previous naming scheme
    # and prefix changes from reconfigure.
    _migrate_naming(hass, entry)

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
