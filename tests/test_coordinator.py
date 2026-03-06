"""Tests for BuzzBridge data coordinators."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.buzzbridge.api import (
    BeestatApiError,
    BeestatAuthError,
    BeestatRateLimitError,
)
from custom_components.buzzbridge.const import (
    BOOST_DURATION_MINUTES,
    BOOST_POLL_SECONDS,
    CONF_FAST_POLL_INTERVAL,
    CONF_SLOW_POLL_INTERVAL,
    DATA_THERMOSTATS,
    DEFAULT_FAST_POLL_MINUTES,
    DEFAULT_SLOW_POLL_MINUTES,
)
from custom_components.buzzbridge.coordinator import (
    FastPollCoordinator,
    SlowPollCoordinator,
)

# Import the stubbed exception classes
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entry(fast_interval: int = 5, slow_interval: int = 30) -> MagicMock:
    entry = MagicMock()
    entry.options = {
        CONF_FAST_POLL_INTERVAL: fast_interval,
        CONF_SLOW_POLL_INTERVAL: slow_interval,
    }
    entry.entry_id = "test_entry"
    return entry


def _make_api(fast_data: dict | None = None, slow_data: dict | None = None) -> AsyncMock:
    api = AsyncMock()
    if fast_data is not None:
        api.fetch_fast_poll_data = AsyncMock(return_value=fast_data)
    if slow_data is not None:
        api.fetch_slow_poll_data = AsyncMock(return_value=slow_data)
    return api


# ---------------------------------------------------------------------------
# FastPollCoordinator
# ---------------------------------------------------------------------------

class TestFastPollCoordinator:

    @pytest.mark.asyncio
    async def test_normal_fetch(self, sample_fast_poll_data, mock_hass):
        api = _make_api(fast_data=sample_fast_poll_data)
        entry = _make_entry()
        coord = FastPollCoordinator(mock_hass, api, entry)

        data = await coord._async_update_data()

        assert data is sample_fast_poll_data
        api.fetch_fast_poll_data.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_auth_error_raises_config_entry_auth_failed(self, mock_hass):
        api = AsyncMock()
        api.fetch_fast_poll_data = AsyncMock(
            side_effect=BeestatAuthError("Invalid token")
        )
        entry = _make_entry()
        coord = FastPollCoordinator(mock_hass, api, entry)

        with pytest.raises(ConfigEntryAuthFailed, match="Authentication failed"):
            await coord._async_update_data()

    @pytest.mark.asyncio
    async def test_rate_limit_raises_update_failed(self, mock_hass):
        api = AsyncMock()
        api.fetch_fast_poll_data = AsyncMock(
            side_effect=BeestatRateLimitError("Rate limited")
        )
        entry = _make_entry()
        coord = FastPollCoordinator(mock_hass, api, entry)

        with pytest.raises(UpdateFailed, match="Rate limited"):
            await coord._async_update_data()

    @pytest.mark.asyncio
    async def test_api_error_raises_update_failed(self, mock_hass):
        api = AsyncMock()
        api.fetch_fast_poll_data = AsyncMock(
            side_effect=BeestatApiError("Connection error")
        )
        entry = _make_entry()
        coord = FastPollCoordinator(mock_hass, api, entry)

        with pytest.raises(UpdateFailed, match="API error"):
            await coord._async_update_data()

    # ----- Boost mode -----

    def test_activate_boost(self, mock_hass):
        api = AsyncMock()
        entry = _make_entry()
        coord = FastPollCoordinator(mock_hass, api, entry)

        assert coord.is_boosted is False

        coord.activate_boost()

        assert coord.is_boosted is True
        assert coord.update_interval == timedelta(seconds=BOOST_POLL_SECONDS)

    def test_deactivate_boost(self, mock_hass):
        api = AsyncMock()
        entry = _make_entry()
        coord = FastPollCoordinator(mock_hass, api, entry)

        coord.activate_boost()
        assert coord.is_boosted is True

        coord.deactivate_boost()
        assert coord.is_boosted is False
        assert coord.update_interval == timedelta(minutes=DEFAULT_FAST_POLL_MINUTES)

    @pytest.mark.asyncio
    async def test_boost_expiry_deactivates(self, sample_fast_poll_data, mock_hass):
        api = _make_api(fast_data=sample_fast_poll_data)
        entry = _make_entry()
        coord = FastPollCoordinator(mock_hass, api, entry)

        # Activate boost and set expiry in the past
        coord.activate_boost()
        coord._boost_until = datetime.now(timezone.utc) - timedelta(minutes=1)

        assert coord.is_boosted is False  # time has passed

        # Fetching data should deactivate boost
        await coord._async_update_data()
        assert coord._boost_until is None
        assert coord.update_interval == timedelta(minutes=DEFAULT_FAST_POLL_MINUTES)

    def test_update_poll_interval_not_boosted(self, mock_hass):
        api = AsyncMock()
        entry = _make_entry()
        coord = FastPollCoordinator(mock_hass, api, entry)

        coord.update_poll_interval(10)
        assert coord._normal_interval == timedelta(minutes=10)
        assert coord.update_interval == timedelta(minutes=10)

    def test_update_poll_interval_while_boosted(self, mock_hass):
        api = AsyncMock()
        entry = _make_entry()
        coord = FastPollCoordinator(mock_hass, api, entry)

        coord.activate_boost()
        coord.update_poll_interval(10)

        # Normal interval updated but current interval stays at boost rate
        assert coord._normal_interval == timedelta(minutes=10)
        assert coord.update_interval == timedelta(seconds=BOOST_POLL_SECONDS)

    # ----- Device discovery -----

    @pytest.mark.asyncio
    async def test_device_discovery_first_poll(self, sample_fast_poll_data, mock_hass):
        """First poll establishes known thermostat IDs — no issues created."""
        api = _make_api(fast_data=sample_fast_poll_data)
        entry = _make_entry()
        coord = FastPollCoordinator(mock_hass, api, entry)

        assert coord._known_thermostat_ids is None

        await coord._async_update_data()

        assert coord._known_thermostat_ids == {"12345"}

    @pytest.mark.asyncio
    @patch("custom_components.buzzbridge.coordinator.ir.async_create_issue")
    async def test_device_discovery_new_thermostat(self, mock_create_issue, mock_hass):
        """Second poll discovers a new thermostat."""
        initial_data = {
            "thermostats": {
                "12345": {"name": "Living Room"},
            },
            "ecobee_thermostats": {},
            "sensors": {},
        }
        new_data = {
            "thermostats": {
                "12345": {"name": "Living Room"},
                "67890": {"name": "Bedroom"},
            },
            "ecobee_thermostats": {},
            "sensors": {},
        }

        api = AsyncMock()
        api.fetch_fast_poll_data = AsyncMock(side_effect=[initial_data, new_data])
        entry = _make_entry()
        coord = FastPollCoordinator(mock_hass, api, entry)

        # First poll
        await coord._async_update_data()
        assert coord._known_thermostat_ids == {"12345"}

        # Second poll — new thermostat
        await coord._async_update_data()
        assert coord._known_thermostat_ids == {"12345", "67890"}
        mock_create_issue.assert_called()

    @pytest.mark.asyncio
    @patch("custom_components.buzzbridge.coordinator.ir.async_create_issue")
    async def test_device_discovery_removed_thermostat(self, mock_create_issue, mock_hass):
        """Thermostat disappears between polls."""
        initial_data = {
            "thermostats": {
                "12345": {"name": "Living Room"},
                "67890": {"name": "Bedroom"},
            },
            "ecobee_thermostats": {},
            "sensors": {},
        }
        reduced_data = {
            "thermostats": {
                "12345": {"name": "Living Room"},
            },
            "ecobee_thermostats": {},
            "sensors": {},
        }

        api = AsyncMock()
        api.fetch_fast_poll_data = AsyncMock(side_effect=[initial_data, reduced_data])
        entry = _make_entry()
        coord = FastPollCoordinator(mock_hass, api, entry)

        await coord._async_update_data()
        assert coord._known_thermostat_ids == {"12345", "67890"}

        await coord._async_update_data()
        assert coord._known_thermostat_ids == {"12345"}
        mock_create_issue.assert_called()

    # ----- Unavailability logging transitions -----

    @pytest.mark.asyncio
    async def test_previously_unavailable_recovery(self, sample_fast_poll_data, mock_hass):
        """After failure, success logs recovery."""
        api = AsyncMock()
        api.fetch_fast_poll_data = AsyncMock(side_effect=[
            BeestatRateLimitError("rate limit"),
            sample_fast_poll_data,
        ])
        entry = _make_entry()
        coord = FastPollCoordinator(mock_hass, api, entry)

        # First call fails
        with pytest.raises(UpdateFailed):
            await coord._async_update_data()
        assert coord._previously_unavailable is True

        # Second call succeeds — recovery
        data = await coord._async_update_data()
        assert coord._previously_unavailable is False
        assert data is sample_fast_poll_data

    @pytest.mark.asyncio
    async def test_repeated_failures_log_once(self, mock_hass):
        """Only the first failure sets _previously_unavailable."""
        api = AsyncMock()
        api.fetch_fast_poll_data = AsyncMock(
            side_effect=BeestatApiError("down")
        )
        entry = _make_entry()
        coord = FastPollCoordinator(mock_hass, api, entry)

        with pytest.raises(UpdateFailed):
            await coord._async_update_data()
        assert coord._previously_unavailable is True

        # Second failure — flag stays True (logs suppressed)
        with pytest.raises(UpdateFailed):
            await coord._async_update_data()
        assert coord._previously_unavailable is True

    @pytest.mark.asyncio
    async def test_auth_error_sets_previously_unavailable(self, mock_hass):
        api = AsyncMock()
        api.fetch_fast_poll_data = AsyncMock(
            side_effect=BeestatAuthError("expired")
        )
        entry = _make_entry()
        coord = FastPollCoordinator(mock_hass, api, entry)

        with pytest.raises(ConfigEntryAuthFailed):
            await coord._async_update_data()
        assert coord._previously_unavailable is True


# ---------------------------------------------------------------------------
# SlowPollCoordinator
# ---------------------------------------------------------------------------

class TestSlowPollCoordinator:

    @pytest.mark.asyncio
    async def test_normal_fetch(self, sample_slow_poll_data, mock_hass):
        api = _make_api(slow_data=sample_slow_poll_data)
        entry = _make_entry()
        coord = SlowPollCoordinator(mock_hass, api, entry)

        data = await coord._async_update_data()

        assert data is sample_slow_poll_data
        api.fetch_slow_poll_data.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_auth_error_raises_config_entry_auth_failed(self, mock_hass):
        api = AsyncMock()
        api.fetch_slow_poll_data = AsyncMock(
            side_effect=BeestatAuthError("Invalid token")
        )
        entry = _make_entry()
        coord = SlowPollCoordinator(mock_hass, api, entry)

        with pytest.raises(ConfigEntryAuthFailed, match="Authentication failed"):
            await coord._async_update_data()

    @pytest.mark.asyncio
    async def test_rate_limit_raises_update_failed(self, mock_hass):
        api = AsyncMock()
        api.fetch_slow_poll_data = AsyncMock(
            side_effect=BeestatRateLimitError("Rate limited")
        )
        entry = _make_entry()
        coord = SlowPollCoordinator(mock_hass, api, entry)

        with pytest.raises(UpdateFailed, match="Rate limited"):
            await coord._async_update_data()

    @pytest.mark.asyncio
    async def test_api_error_raises_update_failed(self, mock_hass):
        api = AsyncMock()
        api.fetch_slow_poll_data = AsyncMock(
            side_effect=BeestatApiError("Failure")
        )
        entry = _make_entry()
        coord = SlowPollCoordinator(mock_hass, api, entry)

        with pytest.raises(UpdateFailed, match="API error"):
            await coord._async_update_data()

    def test_update_poll_interval(self, mock_hass):
        api = AsyncMock()
        entry = _make_entry()
        coord = SlowPollCoordinator(mock_hass, api, entry)

        coord.update_poll_interval(45)
        assert coord.update_interval == timedelta(minutes=45)

    @pytest.mark.asyncio
    async def test_previously_unavailable_recovery(self, sample_slow_poll_data, mock_hass):
        api = AsyncMock()
        api.fetch_slow_poll_data = AsyncMock(side_effect=[
            BeestatRateLimitError("rate limit"),
            sample_slow_poll_data,
        ])
        entry = _make_entry()
        coord = SlowPollCoordinator(mock_hass, api, entry)

        with pytest.raises(UpdateFailed):
            await coord._async_update_data()
        assert coord._previously_unavailable is True

        data = await coord._async_update_data()
        assert coord._previously_unavailable is False
        assert data is sample_slow_poll_data

    @pytest.mark.asyncio
    async def test_repeated_failures_stay_unavailable(self, mock_hass):
        api = AsyncMock()
        api.fetch_slow_poll_data = AsyncMock(
            side_effect=BeestatApiError("down")
        )
        entry = _make_entry()
        coord = SlowPollCoordinator(mock_hass, api, entry)

        with pytest.raises(UpdateFailed):
            await coord._async_update_data()
        assert coord._previously_unavailable is True

        with pytest.raises(UpdateFailed):
            await coord._async_update_data()
        assert coord._previously_unavailable is True
