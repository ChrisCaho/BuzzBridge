# BuzzBridge - Beestat API Client
# Rev: 1.1
#
# Async HTTP client for the Beestat API. Supports single and batch requests,
# error handling, and all endpoints needed by BuzzBridge.
#
# The Beestat API is a REST API that wraps ecobee's cloud data. Authentication
# is via a 40-character API key passed as a query parameter. The API supports
# batching multiple calls into a single HTTP request using the "batch" parameter,
# which significantly reduces rate limit consumption.
#
# Rate limit: ~30 requests/minute (each batch counts as 1 request).
# Server-side caching: sync methods = 180s, runtime reads = 900s.

from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp

from .const import (
    API_BASE_URL,
    DATA_ECOBEE_THERMOSTATS,
    DATA_RUNTIME_SUMMARY,
    DATA_SENSORS,
    DATA_THERMOSTATS,
    ECOBEE_UNAVAILABLE_VALUE,
)

_LOGGER = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=30)

# Static batch call definitions — reused on every poll cycle
_FAST_POLL_CALLS: list[dict[str, str]] = [
    {"resource": "thermostat", "method": "sync", "alias": "thermostat_sync"},
    {"resource": "sensor", "method": "sync", "alias": "sensor_sync"},
    {"resource": "thermostat", "method": "read_id", "alias": "thermostats"},
    {"resource": "ecobee_thermostat", "method": "read_id", "alias": "ecobee_thermostats"},
    {"resource": "sensor", "method": "read_id", "alias": "sensors"},
]

_SLOW_POLL_CALLS: list[dict[str, str]] = [
    {"resource": "runtime", "method": "sync", "alias": "runtime_sync"},
    {"resource": "runtime_thermostat_summary", "method": "read_id", "alias": "runtime_summary"},
]


class BeestatApiError(Exception):
    """Base exception for Beestat API errors."""

    def __init__(self, message: str, error_code: int | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code


class BeestatAuthError(BeestatApiError):
    """Authentication error — invalid or expired API key."""


class BeestatRateLimitError(BeestatApiError):
    """Rate limit exceeded."""


class BeestatApi:
    """Async client for the Beestat API.

    Usage (in Home Assistant):
        from homeassistant.helpers.aiohttp_client import async_get_clientsession
        session = async_get_clientsession(hass)
        api = BeestatApi(session, api_key)
        data = await api.fetch_fast_poll_data()

    Note: The Beestat API passes the API key as a query parameter. This is
    inherent to the API design. If aiohttp debug logging is enabled, the key
    will appear in log output.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        api_key: str,
    ) -> None:
        if not api_key or not isinstance(api_key, str):
            raise ValueError("api_key must be a non-empty string")
        self._session = session
        self._api_key = api_key

    # =========================================================================
    # Low-level request methods
    # =========================================================================

    async def _request(
        self,
        resource: str,
        method: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a single API request.

        Args:
            resource: API resource (e.g., "thermostat").
            method: Method on the resource (e.g., "read_id").
            arguments: Optional dict of arguments for the call.

        Returns:
            The "data" portion of the API response.

        Raises:
            BeestatAuthError: If the API key is invalid or session expired.
            BeestatRateLimitError: If rate limit is exceeded.
            BeestatApiError: For all other API errors.
        """
        params: dict[str, str] = {
            "api_key": self._api_key,
            "resource": resource,
            "method": method,
        }
        if arguments:
            params["arguments"] = json.dumps(arguments)

        return await self._execute(params)

    async def _batch_request(
        self,
        calls: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Make a batch API request — multiple calls in a single HTTP request.

        Each call in the batch must have an "alias" field to identify its
        response. This is the preferred method for polling, as it counts as
        only 1 request against the rate limit regardless of how many calls
        are batched.

        Args:
            calls: List of dicts, each with "resource", "method", "alias",
                   and optionally "arguments".

        Returns:
            Dict keyed by alias, each containing the response data for that call.
        """
        params: dict[str, str] = {
            "api_key": self._api_key,
            "batch": json.dumps(calls),
        }

        return await self._execute(params)

    async def _execute(self, params: dict[str, str]) -> dict[str, Any]:
        """Execute an HTTP request to the Beestat API.

        Handles response parsing, error code detection, and exception mapping.
        """
        try:
            async with self._session.get(
                API_BASE_URL, params=params, timeout=_TIMEOUT
            ) as response:
                response.raise_for_status()
                # content_type=None: Beestat sometimes returns text/html for JSON
                result = await response.json(content_type=None)
        except TimeoutError as err:
            raise BeestatApiError(f"Request timed out: {err}") from err
        except aiohttp.ClientResponseError as err:
            if err.status == 429:
                raise BeestatRateLimitError(
                    "Rate limit exceeded", error_code=429
                ) from err
            raise BeestatApiError(
                f"HTTP {err.status}: {err.message}", error_code=err.status
            ) from err
        except aiohttp.ClientError as err:
            raise BeestatApiError(f"Connection error: {err}") from err
        except (json.JSONDecodeError, ValueError) as err:
            raise BeestatApiError(f"Invalid JSON response: {err}") from err

        # Guard against non-dict responses (e.g., API returning a JSON array)
        if not isinstance(result, dict):
            raise BeestatApiError(f"Unexpected response type: {type(result).__name__}")

        # Check for API-level errors
        if not result.get("success", False):
            error_data = result.get("data", {})
            error_code = error_data.get("error_code")
            error_message = error_data.get("error_message", "Unknown API error")

            # Map error codes to specific exceptions
            if error_code == 1505:
                raise BeestatAuthError("Session expired", error_code=error_code)
            if error_code and 10000 <= error_code <= 10508:
                raise BeestatAuthError(error_message, error_code=error_code)

            raise BeestatApiError(error_message, error_code=error_code)

        return result.get("data", {})

    # =========================================================================
    # Validation
    # =========================================================================

    async def validate_api_key(self) -> bool:
        """Test that the API key is valid by fetching user info.

        Returns:
            True if the key is valid.

        Raises:
            BeestatAuthError: If the key is invalid.
        """
        await self._request("user", "read_id")
        return True

    # =========================================================================
    # High-level data fetching — Fast Poll
    #
    # These are batched into a single HTTP request to minimize rate limit use.
    # Called every 5 minutes (configurable).
    # =========================================================================

    async def fetch_fast_poll_data(self) -> dict[str, Any]:
        """Fetch all fast-poll data in a single batch request.

        Sends sync + read calls together as one HTTP request. The server
        processes them in order (syncs first, then reads), but from the
        client's perspective it is a single atomic request.

        Returns:
            Dict with keys matching DATA_THERMOSTATS, DATA_ECOBEE_THERMOSTATS,
            DATA_SENSORS constants.
        """
        result = await self._batch_request(_FAST_POLL_CALLS)

        return {
            DATA_THERMOSTATS: result.get("thermostats", {}),
            DATA_ECOBEE_THERMOSTATS: result.get("ecobee_thermostats", {}),
            DATA_SENSORS: result.get("sensors", {}),
        }

    # =========================================================================
    # High-level data fetching — Slow Poll
    #
    # Called every 30 minutes (configurable). Fetches daily runtime summaries
    # which include equipment runtimes, degree days, and averages.
    # =========================================================================

    async def fetch_slow_poll_data(self) -> dict[str, Any]:
        """Fetch all slow-poll data in a single batch request.

        Returns:
            Dict with key matching DATA_RUNTIME_SUMMARY constant.
        """
        result = await self._batch_request(_SLOW_POLL_CALLS)

        return {
            DATA_RUNTIME_SUMMARY: result.get("runtime_summary", {}),
        }

    # =========================================================================
    # Utility methods
    # =========================================================================

    @staticmethod
    def is_value_available(value: Any) -> bool:
        """Check if an ecobee value is actually available.

        ecobee uses -5002 to indicate "sensor not present" for air quality
        and other optional capabilities. Values of "unknown" in sensor
        capabilities also indicate unavailability.
        """
        if value is None:
            return False
        if value == ECOBEE_UNAVAILABLE_VALUE:
            return False
        if isinstance(value, str) and value.lower() == "unknown":
            return False
        return True

    @staticmethod
    def ecobee_temp_to_float(raw_temp: int | float | None) -> float | None:
        """Convert ecobee raw temperature (x10) to actual degrees.

        ecobee stores temperatures multiplied by 10 in some contexts
        (e.g., extended_runtime, events). The beestat API already divides
        by 10 in thermostat.read_id, but raw ecobee data may not.

        Args:
            raw_temp: Temperature value, possibly x10.

        Returns:
            Temperature as float, or None if unavailable.
        """
        if raw_temp is None or raw_temp == ECOBEE_UNAVAILABLE_VALUE:
            return None
        # Values over 200 are likely x10 encoded (200°F would be extreme)
        if isinstance(raw_temp, (int, float)) and abs(raw_temp) > 200:
            return round(raw_temp / 10.0, 1)
        return round(float(raw_temp), 1)
