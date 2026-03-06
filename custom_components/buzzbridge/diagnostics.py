# BuzzBridge - Diagnostics Platform
# Rev: 1.1
#
# Provides a "Download Diagnostics" button in the HA UI that exports
# coordinator data with sensitive fields (API key, ecobee tokens) redacted.
# Used for troubleshooting without exposing secrets.

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_API_KEY
from .entity import BuzzBridgeConfigEntry

# Keys to redact from config entry data and coordinator payloads
TO_REDACT = {
    CONF_API_KEY,
    "api_key",
    "token",
    "access_token",
    "refresh_token",
    "ecobee_auth_token",
    "address",
    "latitude",
    "longitude",
    "mac_address",
    "wifi_mac",
    "serial_number",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: BuzzBridgeConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a BuzzBridge config entry."""
    data = entry.runtime_data
    fast_coord = data.fast_coordinator
    slow_coord = data.slow_coordinator

    return {
        "config_entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "fast_poll_data": async_redact_data(
            fast_coord.data or {}, TO_REDACT
        ),
        "slow_poll_data": async_redact_data(
            slow_coord.data or {}, TO_REDACT
        ),
        "fast_poll_interval": str(fast_coord.update_interval),
        "slow_poll_interval": str(slow_coord.update_interval),
        "boost_active": fast_coord.is_boosted,
    }
