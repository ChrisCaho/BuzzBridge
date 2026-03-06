# BuzzBridge - Base Entity
# Rev: 1.0
#
# Shared base entity class for all BuzzBridge platforms.
# Provides common coordinator reference and device info handling.

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import BeestatApi
from .coordinator import FastPollCoordinator, SlowPollCoordinator


@dataclass
class BuzzBridgeData:
    """Runtime data for a BuzzBridge config entry."""

    api: BeestatApi
    fast_coordinator: FastPollCoordinator
    slow_coordinator: SlowPollCoordinator


type BuzzBridgeConfigEntry = ConfigEntry[BuzzBridgeData]


class BuzzBridgeEntity(CoordinatorEntity):
    """Base entity for all BuzzBridge entities.

    Provides _attr_has_entity_name = True so device names are
    automatically prepended to entity names by HA.
    """

    _attr_has_entity_name = True
