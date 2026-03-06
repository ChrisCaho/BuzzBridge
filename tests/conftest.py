"""Shared fixtures for BuzzBridge test suite."""

from __future__ import annotations

import sys
from datetime import timedelta
from types import ModuleType
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Stub out homeassistant imports so tests can run outside of HA core
# ---------------------------------------------------------------------------

def _make_module(name: str) -> ModuleType:
    """Create a stub module and register it in sys.modules."""
    mod = ModuleType(name)
    sys.modules[name] = mod
    return mod


def _setup_ha_stubs() -> None:
    """Create minimal stubs for homeassistant packages used by BuzzBridge."""

    # Core
    ha = _make_module("homeassistant")
    ha_core = _make_module("homeassistant.core")
    ha_core.HomeAssistant = MagicMock
    ha_core.callback = lambda fn: fn  # pass-through decorator

    # Exceptions
    ha_exceptions = _make_module("homeassistant.exceptions")

    class ConfigEntryAuthFailed(Exception):
        pass

    ha_exceptions.ConfigEntryAuthFailed = ConfigEntryAuthFailed

    # config_entries
    ha_ce = _make_module("homeassistant.config_entries")

    class _ConfigEntry:
        def __init__(self, **kwargs):
            self.data = kwargs.get("data", {})
            self.options = kwargs.get("options", {})
            self.entry_id = kwargs.get("entry_id", "test_entry_id")
            self.runtime_data = kwargs.get("runtime_data", None)
    ha_ce.ConfigEntry = _ConfigEntry

    class _ConfigFlow:
        DOMAIN = ""
        def __init_subclass__(cls, domain: str = "", **kw):
            cls.DOMAIN = domain
        def __init__(self):
            self.hass = MagicMock()
            self._unique_id = None
        async def async_set_unique_id(self, uid):
            self._unique_id = uid
        def _abort_if_unique_id_configured(self):
            pass
        def async_show_form(self, **kwargs):
            return {"type": "form", **kwargs}
        def async_create_entry(self, **kwargs):
            return {"type": "create_entry", **kwargs}
        def async_abort(self, **kwargs):
            return {"type": "abort", **kwargs}
        def _get_reauth_entry(self):
            return MagicMock(data={"api_key": "old_key"})
        def _get_reconfigure_entry(self):
            return MagicMock(data={"api_key": "old_key"})
        def async_update_reload_and_abort(self, entry, **kwargs):
            return {"type": "abort", "reason": "reauth_successful", **kwargs}

    class _ConfigFlowResult(dict):
        pass

    class _OptionsFlow:
        def __init__(self, config_entry=None):
            self._config_entry = config_entry
            self.hass = MagicMock()
        def async_show_form(self, **kwargs):
            return {"type": "form", **kwargs}
        def async_create_entry(self, **kwargs):
            return {"type": "create_entry", **kwargs}

    ha_ce.ConfigFlow = _ConfigFlow
    ha_ce.ConfigFlowResult = _ConfigFlowResult
    ha_ce.OptionsFlow = _OptionsFlow

    # homeassistant.const
    ha_const = _make_module("homeassistant.const")
    ha_const.PERCENTAGE = "%"
    ha_const.UnitOfTemperature = MagicMock()
    ha_const.UnitOfTemperature.FAHRENHEIT = "°F"
    ha_const.UnitOfTime = MagicMock()
    ha_const.UnitOfTime.HOURS = "h"
    ha_const.EntityCategory = MagicMock()

    # homeassistant.helpers
    _make_module("homeassistant.helpers")

    # aiohttp_client
    ha_aiohttp = _make_module("homeassistant.helpers.aiohttp_client")
    ha_aiohttp.async_get_clientsession = MagicMock()

    # device_registry
    ha_dr = _make_module("homeassistant.helpers.device_registry")
    ha_dr.DeviceEntry = MagicMock

    # entity
    ha_entity = _make_module("homeassistant.helpers.entity")
    ha_entity.DeviceInfo = dict
    ha_entity.EntityCategory = MagicMock()
    ha_entity.EntityCategory.DIAGNOSTIC = "diagnostic"

    # entity_platform
    ha_ep = _make_module("homeassistant.helpers.entity_platform")
    ha_ep.AddEntitiesCallback = MagicMock

    # issue_registry
    ha_ir = _make_module("homeassistant.helpers.issue_registry")
    ha_ir.async_create_issue = MagicMock()
    ha_ir.IssueSeverity = MagicMock()
    ha_ir.IssueSeverity.WARNING = "warning"

    # update_coordinator
    ha_uc = _make_module("homeassistant.helpers.update_coordinator")

    class _DataUpdateCoordinator:
        def __init__(self, hass, logger, *, name="", update_interval=None):
            self.hass = hass
            self.logger = logger
            self.name = name
            self.update_interval = update_interval
            self.data = None
            self._listeners = {}

        async def async_config_entry_first_refresh(self):
            self.data = await self._async_update_data()

        async def async_request_refresh(self):
            self.data = await self._async_update_data()

        async def _async_update_data(self):
            raise NotImplementedError

    class _CoordinatorEntity:
        def __init__(self, coordinator, *args, **kwargs):
            self.coordinator = coordinator

    ha_uc.DataUpdateCoordinator = _DataUpdateCoordinator
    ha_uc.UpdateFailed = type("UpdateFailed", (Exception,), {})
    ha_uc.CoordinatorEntity = _CoordinatorEntity

    # dt util
    ha_util = _make_module("homeassistant.util")
    ha_dt = _make_module("homeassistant.util.dt")
    from datetime import datetime, timezone
    ha_dt.utcnow = lambda: datetime.now(timezone.utc)
    ha_dt.now = lambda: datetime.now()

    # Sensor / binary sensor / button stubs
    ha_sensor = _make_module("homeassistant.components")
    ha_sensor_mod = _make_module("homeassistant.components.sensor")
    ha_sensor_mod.SensorDeviceClass = MagicMock()
    ha_sensor_mod.SensorDeviceClass.TEMPERATURE = "temperature"
    ha_sensor_mod.SensorDeviceClass.HUMIDITY = "humidity"
    ha_sensor_mod.SensorDeviceClass.CO2 = "carbon_dioxide"
    ha_sensor_mod.SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS = "volatile_organic_compounds_parts"
    ha_sensor_mod.SensorEntity = type("SensorEntity", (), {"_attr_has_entity_name": True})
    ha_sensor_mod.SensorStateClass = MagicMock()
    ha_sensor_mod.SensorStateClass.MEASUREMENT = "measurement"
    ha_sensor_mod.SensorStateClass.TOTAL_INCREASING = "total_increasing"

    ha_bs = _make_module("homeassistant.components.binary_sensor")
    ha_bs.BinarySensorDeviceClass = MagicMock()
    ha_bs.BinarySensorDeviceClass.CONNECTIVITY = "connectivity"
    ha_bs.BinarySensorDeviceClass.OCCUPANCY = "occupancy"
    ha_bs.BinarySensorEntity = type("BinarySensorEntity", (), {"_attr_has_entity_name": True})

    ha_btn = _make_module("homeassistant.components.button")
    ha_btn.ButtonEntity = type("ButtonEntity", (), {"_attr_has_entity_name": True})

    # Diagnostics
    ha_diag = _make_module("homeassistant.components.diagnostics")

    def _async_redact_data(data, to_redact):
        """Simple recursive redaction for testing."""
        if isinstance(data, dict):
            return {
                k: ("**REDACTED**" if k in to_redact else _async_redact_data(v, to_redact))
                for k, v in data.items()
            }
        if isinstance(data, list):
            return [_async_redact_data(item, to_redact) for item in data]
        return data

    ha_diag.async_redact_data = _async_redact_data

    # voluptuous — import real one
    # (already available as a dependency)


# Run stubs before anything else imports buzzbridge modules
_setup_ha_stubs()


# ---------------------------------------------------------------------------
# Sample API response data
# ---------------------------------------------------------------------------

SAMPLE_THERMOSTAT_ID = "12345"
SAMPLE_ECOBEE_ID = "67890"
SAMPLE_SENSOR_ID = "99001"
SAMPLE_API_KEY = "a" * 40  # valid 40-char hex key


@pytest.fixture
def sample_fast_poll_data() -> dict[str, Any]:
    """Return sample data matching BeestatApi.fetch_fast_poll_data() output."""
    return {
        "thermostats": {
            SAMPLE_THERMOSTAT_ID: {
                "thermostat_id": int(SAMPLE_THERMOSTAT_ID),
                "ecobee_thermostat_id": int(SAMPLE_ECOBEE_ID),
                "name": "Living Room",
                "temperature": 72.5,
                "humidity": 45,
                "setpoint_heat": 68.0,
                "setpoint_cool": 76.0,
                "running_equipment": ["compressor_cool_1", "fan"],
                "filters": {
                    "regular_1": {
                        "runtime": 360000,
                        "life": 3,
                        "life_units": "month",
                        "last_changed": "2026-01-15",
                    }
                },
            },
        },
        "ecobee_thermostats": {
            SAMPLE_ECOBEE_ID: {
                "model_number": "aresSmart",
                "settings": {
                    "hvacMode": "cool",
                    "firmwareVersion": "4.8.7.11",
                },
                "runtime": {
                    "connected": True,
                    "actualTemperature": 725,
                    "actualHumidity": 45,
                    "desiredFanMode": "auto",
                    "actualAQScore": 85,
                    "actualCO2": 520,
                    "actualVOC": 150,
                    "actualAQAccuracy": 3,
                },
                "weather": {
                    "forecasts": [
                        {
                            "temperature": 88,
                            "relativeHumidity": 60,
                            "tempHigh": 92,
                            "tempLow": 78,
                        }
                    ],
                },
                "events": [
                    {
                        "type": "hold",
                        "running": True,
                        "name": "temp",
                        "isIndefinite": False,
                        "endDate": "2026-03-06",
                        "endTime": "18:00:00",
                        "fan": "auto",
                        "coolHoldTemp": 740,
                        "heatHoldTemp": 680,
                    }
                ],
            },
        },
        "sensors": {
            SAMPLE_SENSOR_ID: {
                "sensor_id": int(SAMPLE_SENSOR_ID),
                "thermostat_id": int(SAMPLE_THERMOSTAT_ID),
                "name": "Bedroom",
                "type": "remote_sensor",
                "temperature": 71.0,
                "humidity": 42,
                "occupancy": True,
                "deleted": False,
                "inactive": False,
                "capability": [
                    {"type": "temperature"},
                    {"type": "humidity"},
                    {"type": "occupancy"},
                ],
            },
        },
    }


@pytest.fixture
def sample_slow_poll_data() -> dict[str, Any]:
    """Return sample data matching BeestatApi.fetch_slow_poll_data() output."""
    return {
        "runtime_summary": {
            "501": {
                "runtime_thermostat_summary_id": 501,
                "thermostat_id": int(SAMPLE_THERMOSTAT_ID),
                "date": "2026-03-05",
                "sum_compressor_cool_1": 7200,
                "sum_compressor_heat_1": 0,
                "sum_fan": 10800,
                "sum_auxiliary_heat_1": 0,
                "sum_cooling_degree_days": 12.5,
                "sum_heating_degree_days": 0.0,
            },
            "502": {
                "runtime_thermostat_summary_id": 502,
                "thermostat_id": int(SAMPLE_THERMOSTAT_ID),
                "date": "2026-03-04",
                "sum_compressor_cool_1": 5400,
                "sum_compressor_heat_1": 1800,
                "sum_fan": 9000,
                "sum_auxiliary_heat_1": 0,
                "sum_cooling_degree_days": 8.0,
                "sum_heating_degree_days": 3.0,
            },
        },
    }


@pytest.fixture
def sample_batch_response() -> dict[str, Any]:
    """Return a raw successful batch API response (before parsing)."""
    return {
        "success": True,
        "data": {
            "thermostat_sync": {},
            "sensor_sync": {},
            "thermostats": {
                SAMPLE_THERMOSTAT_ID: {
                    "thermostat_id": int(SAMPLE_THERMOSTAT_ID),
                    "name": "Living Room",
                    "temperature": 72.5,
                },
            },
            "ecobee_thermostats": {
                SAMPLE_ECOBEE_ID: {
                    "model_number": "aresSmart",
                },
            },
            "sensors": {
                SAMPLE_SENSOR_ID: {
                    "sensor_id": int(SAMPLE_SENSOR_ID),
                    "name": "Bedroom",
                    "temperature": 71.0,
                },
            },
        },
    }


@pytest.fixture
def mock_api_key() -> str:
    return SAMPLE_API_KEY


@pytest.fixture
def mock_hass() -> MagicMock:
    """Create a minimal mock Home Assistant instance."""
    hass = MagicMock()
    hass.config_entries = MagicMock()
    return hass


@pytest.fixture
def mock_config_entry(mock_api_key: str) -> MagicMock:
    """Create a mock config entry."""
    entry = MagicMock()
    entry.data = {"api_key": mock_api_key}
    entry.options = {"fast_poll_interval": 5, "slow_poll_interval": 30}
    entry.entry_id = "test_entry_id"
    entry.runtime_data = None
    return entry


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock aiohttp.ClientSession."""
    return AsyncMock()
