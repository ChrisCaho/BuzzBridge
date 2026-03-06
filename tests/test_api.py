"""Tests for BuzzBridge BeestatApi client."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.buzzbridge.api import (
    BeestatApi,
    BeestatApiError,
    BeestatAuthError,
    BeestatRateLimitError,
)
from custom_components.buzzbridge.const import ECOBEE_UNAVAILABLE_VALUE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(status: int = 200, json_data: dict | None = None, raise_for_status: Exception | None = None):
    """Create a mock aiohttp response context manager."""
    resp = AsyncMock()
    resp.status = status
    if raise_for_status:
        resp.raise_for_status = MagicMock(side_effect=raise_for_status)
    else:
        resp.raise_for_status = MagicMock()
    resp.json = AsyncMock(return_value=json_data)

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _make_session(response_cm):
    """Create a mock session whose .get() returns the given context manager."""
    session = MagicMock(spec=aiohttp.ClientSession)
    session.get = MagicMock(return_value=response_cm)
    return session


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestBeestatApiConstruction:

    def test_valid_key(self):
        session = MagicMock()
        api = BeestatApi(session, "a" * 40)
        assert api._api_key == "a" * 40

    def test_empty_key_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            BeestatApi(MagicMock(), "")

    def test_none_key_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            BeestatApi(MagicMock(), None)


# ---------------------------------------------------------------------------
# validate_api_key
# ---------------------------------------------------------------------------

class TestValidateApiKey:

    @pytest.mark.asyncio
    async def test_validate_api_key_success(self):
        resp_cm = _make_response(json_data={"success": True, "data": {"user_id": 1}})
        session = _make_session(resp_cm)
        api = BeestatApi(session, "a" * 40)

        result = await api.validate_api_key()
        assert result is True
        session.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_api_key_auth_failure(self):
        resp_cm = _make_response(json_data={
            "success": False,
            "data": {"error_code": 10100, "error_message": "Invalid token"},
        })
        session = _make_session(resp_cm)
        api = BeestatApi(session, "b" * 40)

        with pytest.raises(BeestatAuthError, match="Invalid token"):
            await api.validate_api_key()

    @pytest.mark.asyncio
    async def test_validate_api_key_session_expired(self):
        resp_cm = _make_response(json_data={
            "success": False,
            "data": {"error_code": 1505, "error_message": "Session expired"},
        })
        session = _make_session(resp_cm)
        api = BeestatApi(session, "c" * 40)

        with pytest.raises(BeestatAuthError, match="Session expired"):
            await api.validate_api_key()


# ---------------------------------------------------------------------------
# fetch_fast_poll_data
# ---------------------------------------------------------------------------

class TestFetchFastPollData:

    @pytest.mark.asyncio
    async def test_success(self, sample_batch_response):
        resp_cm = _make_response(json_data=sample_batch_response)
        session = _make_session(resp_cm)
        api = BeestatApi(session, "a" * 40)

        data = await api.fetch_fast_poll_data()
        assert "thermostats" in data
        assert "ecobee_thermostats" in data
        assert "sensors" in data

    @pytest.mark.asyncio
    async def test_auth_error(self):
        resp_cm = _make_response(json_data={
            "success": False,
            "data": {"error_code": 10200, "error_message": "Unauthorized"},
        })
        session = _make_session(resp_cm)
        api = BeestatApi(session, "a" * 40)

        with pytest.raises(BeestatAuthError):
            await api.fetch_fast_poll_data()

    @pytest.mark.asyncio
    async def test_rate_limit_http_429(self):
        err = aiohttp.ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=429,
            message="Too Many Requests",
        )
        resp_cm = _make_response(raise_for_status=err)
        session = _make_session(resp_cm)
        api = BeestatApi(session, "a" * 40)

        with pytest.raises(BeestatRateLimitError):
            await api.fetch_fast_poll_data()

    @pytest.mark.asyncio
    async def test_timeout(self):
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(side_effect=TimeoutError("timed out"))
        cm.__aexit__ = AsyncMock(return_value=False)
        session = MagicMock(spec=aiohttp.ClientSession)
        session.get = MagicMock(return_value=cm)
        api = BeestatApi(session, "a" * 40)

        with pytest.raises(BeestatApiError, match="timed out"):
            await api.fetch_fast_poll_data()

    @pytest.mark.asyncio
    async def test_bad_json_response(self):
        resp = AsyncMock()
        resp.raise_for_status = MagicMock()
        resp.json = AsyncMock(side_effect=json.JSONDecodeError("bad", "", 0))

        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=resp)
        cm.__aexit__ = AsyncMock(return_value=False)

        session = MagicMock(spec=aiohttp.ClientSession)
        session.get = MagicMock(return_value=cm)
        api = BeestatApi(session, "a" * 40)

        with pytest.raises(BeestatApiError, match="Invalid JSON"):
            await api.fetch_fast_poll_data()

    @pytest.mark.asyncio
    async def test_non_dict_response(self):
        resp_cm = _make_response(json_data=[1, 2, 3])  # list, not dict
        # Override raise_for_status to not raise
        session = _make_session(resp_cm)
        api = BeestatApi(session, "a" * 40)

        with pytest.raises(BeestatApiError, match="Unexpected response type"):
            await api.fetch_fast_poll_data()

    @pytest.mark.asyncio
    async def test_connection_error(self):
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(side_effect=aiohttp.ClientError("conn refused"))
        cm.__aexit__ = AsyncMock(return_value=False)
        session = MagicMock(spec=aiohttp.ClientSession)
        session.get = MagicMock(return_value=cm)
        api = BeestatApi(session, "a" * 40)

        with pytest.raises(BeestatApiError, match="Connection error"):
            await api.fetch_fast_poll_data()


# ---------------------------------------------------------------------------
# fetch_slow_poll_data
# ---------------------------------------------------------------------------

class TestFetchSlowPollData:

    @pytest.mark.asyncio
    async def test_success(self):
        resp_cm = _make_response(json_data={
            "success": True,
            "data": {
                "runtime_sync": {},
                "runtime_summary": {"501": {"thermostat_id": 12345, "date": "2026-03-05"}},
            },
        })
        session = _make_session(resp_cm)
        api = BeestatApi(session, "a" * 40)

        data = await api.fetch_slow_poll_data()
        assert "runtime_summary" in data

    @pytest.mark.asyncio
    async def test_api_error(self):
        resp_cm = _make_response(json_data={
            "success": False,
            "data": {"error_code": 500, "error_message": "Internal error"},
        })
        session = _make_session(resp_cm)
        api = BeestatApi(session, "a" * 40)

        with pytest.raises(BeestatApiError, match="Internal error"):
            await api.fetch_slow_poll_data()


# ---------------------------------------------------------------------------
# Batch request building
# ---------------------------------------------------------------------------

class TestBatchRequest:

    @pytest.mark.asyncio
    async def test_batch_passes_calls_as_json(self, sample_batch_response):
        resp_cm = _make_response(json_data=sample_batch_response)
        session = _make_session(resp_cm)
        api = BeestatApi(session, "a" * 40)

        await api.fetch_fast_poll_data()

        call_args = session.get.call_args
        params = call_args.kwargs.get("params") or call_args[1].get("params") or call_args[0][1] if len(call_args[0]) > 1 else None
        if params is None:
            # Try positional
            params = call_args.kwargs["params"]
        assert "batch" in params
        batch = json.loads(params["batch"])
        aliases = [c["alias"] for c in batch]
        assert "thermostat_sync" in aliases
        assert "thermostats" in aliases
        assert "sensors" in aliases


# ---------------------------------------------------------------------------
# is_value_available
# ---------------------------------------------------------------------------

class TestIsValueAvailable:

    def test_normal_value(self):
        assert BeestatApi.is_value_available(42) is True

    def test_string_value(self):
        assert BeestatApi.is_value_available("hello") is True

    def test_zero_is_available(self):
        assert BeestatApi.is_value_available(0) is True

    def test_none_unavailable(self):
        assert BeestatApi.is_value_available(None) is False

    def test_ecobee_unavailable_value(self):
        assert BeestatApi.is_value_available(ECOBEE_UNAVAILABLE_VALUE) is False
        assert BeestatApi.is_value_available(-5002) is False

    def test_unknown_string(self):
        assert BeestatApi.is_value_available("unknown") is False
        assert BeestatApi.is_value_available("Unknown") is False
        assert BeestatApi.is_value_available("UNKNOWN") is False

    def test_non_unknown_string(self):
        assert BeestatApi.is_value_available("known") is True


# ---------------------------------------------------------------------------
# ecobee_temp_to_float
# ---------------------------------------------------------------------------

class TestEcobeeTempToFloat:

    def test_none(self):
        assert BeestatApi.ecobee_temp_to_float(None) is None

    def test_unavailable_value(self):
        assert BeestatApi.ecobee_temp_to_float(-5002) is None

    def test_normal_temp(self):
        # Normal temp (not x10 encoded) — under 200
        assert BeestatApi.ecobee_temp_to_float(72.5) == 72.5

    def test_x10_encoded(self):
        # 725 > 200, so should divide by 10
        assert BeestatApi.ecobee_temp_to_float(725) == 72.5

    def test_negative_x10(self):
        # -300 → abs > 200 → divide by 10
        assert BeestatApi.ecobee_temp_to_float(-300) == -30.0

    def test_small_negative(self):
        # -10 → abs < 200 → keep as-is
        assert BeestatApi.ecobee_temp_to_float(-10) == -10.0

    def test_exactly_200(self):
        # 200 → not > 200 → keep as-is
        assert BeestatApi.ecobee_temp_to_float(200) == 200.0

    def test_integer_input(self):
        assert BeestatApi.ecobee_temp_to_float(70) == 70.0
