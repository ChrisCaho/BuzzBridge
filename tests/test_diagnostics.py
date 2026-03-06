"""Tests for BuzzBridge diagnostics."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest

from custom_components.buzzbridge.diagnostics import (
    TO_REDACT,
    async_get_config_entry_diagnostics,
)


def _make_coordinator(data: dict, interval: timedelta, is_boosted: bool = False):
    """Create a mock coordinator."""
    coord = MagicMock()
    coord.data = data
    coord.update_interval = interval
    coord.is_boosted = is_boosted
    return coord


def _make_entry(
    data: dict,
    options: dict,
    fast_data: dict,
    slow_data: dict,
    fast_interval: timedelta = timedelta(minutes=5),
    slow_interval: timedelta = timedelta(minutes=30),
    is_boosted: bool = False,
) -> MagicMock:
    """Create a mock config entry with runtime_data."""
    entry = MagicMock()
    entry.data = data
    entry.options = options

    fast_coord = _make_coordinator(fast_data, fast_interval, is_boosted)
    slow_coord = _make_coordinator(slow_data, slow_interval)

    runtime_data = MagicMock()
    runtime_data.fast_coordinator = fast_coord
    runtime_data.slow_coordinator = slow_coord
    entry.runtime_data = runtime_data

    return entry


class TestDiagnostics:

    @pytest.mark.asyncio
    async def test_diagnostics_output_structure(self):
        entry = _make_entry(
            data={"api_key": "secret_key_value"},
            options={"fast_poll_interval": 5, "slow_poll_interval": 30},
            fast_data={"thermostats": {"123": {"name": "Test"}}},
            slow_data={"runtime_summary": {}},
        )
        hass = MagicMock()

        result = await async_get_config_entry_diagnostics(hass, entry)

        assert "config_entry" in result
        assert "fast_poll_data" in result
        assert "slow_poll_data" in result
        assert "fast_poll_interval" in result
        assert "slow_poll_interval" in result
        assert "boost_active" in result

    @pytest.mark.asyncio
    async def test_api_key_is_redacted(self):
        entry = _make_entry(
            data={"api_key": "my_super_secret_key"},
            options={},
            fast_data={},
            slow_data={},
        )
        hass = MagicMock()

        result = await async_get_config_entry_diagnostics(hass, entry)

        assert result["config_entry"]["data"]["api_key"] == "**REDACTED**"

    @pytest.mark.asyncio
    async def test_sensitive_fields_redacted_in_fast_data(self):
        entry = _make_entry(
            data={"api_key": "secret"},
            options={},
            fast_data={
                "thermostats": {
                    "123": {
                        "name": "Test",
                        "serial_number": "ABC123",
                        "mac_address": "AA:BB:CC:DD:EE:FF",
                        "latitude": 37.7749,
                        "longitude": -122.4194,
                        "address": "123 Main St",
                    }
                }
            },
            slow_data={},
        )
        hass = MagicMock()

        result = await async_get_config_entry_diagnostics(hass, entry)

        fast = result["fast_poll_data"]
        tstat = fast["thermostats"]["123"]
        assert tstat["serial_number"] == "**REDACTED**"
        assert tstat["mac_address"] == "**REDACTED**"
        assert tstat["latitude"] == "**REDACTED**"
        assert tstat["longitude"] == "**REDACTED**"
        assert tstat["address"] == "**REDACTED**"
        # Non-sensitive fields should be preserved
        assert tstat["name"] == "Test"

    @pytest.mark.asyncio
    async def test_token_fields_redacted(self):
        entry = _make_entry(
            data={"api_key": "secret"},
            options={},
            fast_data={
                "ecobee_thermostats": {
                    "456": {
                        "token": "tok_abc",
                        "access_token": "at_abc",
                        "refresh_token": "rt_abc",
                        "ecobee_auth_token": "eat_abc",
                        "model_number": "aresSmart",
                    }
                }
            },
            slow_data={},
        )
        hass = MagicMock()

        result = await async_get_config_entry_diagnostics(hass, entry)

        ecobee = result["fast_poll_data"]["ecobee_thermostats"]["456"]
        assert ecobee["token"] == "**REDACTED**"
        assert ecobee["access_token"] == "**REDACTED**"
        assert ecobee["refresh_token"] == "**REDACTED**"
        assert ecobee["ecobee_auth_token"] == "**REDACTED**"
        assert ecobee["model_number"] == "aresSmart"

    @pytest.mark.asyncio
    async def test_options_not_redacted(self):
        entry = _make_entry(
            data={"api_key": "secret"},
            options={"fast_poll_interval": 5, "slow_poll_interval": 30},
            fast_data={},
            slow_data={},
        )
        hass = MagicMock()

        result = await async_get_config_entry_diagnostics(hass, entry)

        assert result["config_entry"]["options"]["fast_poll_interval"] == 5
        assert result["config_entry"]["options"]["slow_poll_interval"] == 30

    @pytest.mark.asyncio
    async def test_boost_active_reflected(self):
        entry = _make_entry(
            data={"api_key": "secret"},
            options={},
            fast_data={},
            slow_data={},
            is_boosted=True,
        )
        hass = MagicMock()

        result = await async_get_config_entry_diagnostics(hass, entry)
        assert result["boost_active"] is True

    @pytest.mark.asyncio
    async def test_none_coordinator_data(self):
        entry = _make_entry(
            data={"api_key": "secret"},
            options={},
            fast_data=None,
            slow_data=None,
        )
        # When data is None, diagnostics uses {} via `or {}`
        entry.runtime_data.fast_coordinator.data = None
        entry.runtime_data.slow_coordinator.data = None
        hass = MagicMock()

        result = await async_get_config_entry_diagnostics(hass, entry)
        assert result["fast_poll_data"] == {}
        assert result["slow_poll_data"] == {}

    @pytest.mark.asyncio
    async def test_all_redacted_keys_covered(self):
        """Verify that every key in TO_REDACT actually gets redacted."""
        # Build a flat dict with each key in TO_REDACT
        test_data = {key: f"secret_{key}" for key in TO_REDACT}
        entry = _make_entry(
            data={"api_key": "secret"},
            options={},
            fast_data=test_data,
            slow_data={},
        )
        hass = MagicMock()

        result = await async_get_config_entry_diagnostics(hass, entry)

        for key in TO_REDACT:
            if key in result["fast_poll_data"]:
                assert result["fast_poll_data"][key] == "**REDACTED**", (
                    f"Key '{key}' was not redacted"
                )
