"""Tests for BuzzBridge config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.buzzbridge.config_flow import (
    BuzzBridgeConfigFlow,
    BuzzBridgeOptionsFlow,
)
from custom_components.buzzbridge.const import (
    CONF_API_KEY,
    CONF_FAST_POLL_INTERVAL,
    CONF_SLOW_POLL_INTERVAL,
    DEFAULT_FAST_POLL_MINUTES,
    DEFAULT_SLOW_POLL_MINUTES,
)

VALID_KEY = "a" * 40
SHORT_KEY = "a" * 10
NON_HEX_KEY = "g" * 40

MODULE_PATH = "custom_components.buzzbridge.config_flow"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_flow() -> BuzzBridgeConfigFlow:
    """Create a config flow instance with mocked hass."""
    flow = BuzzBridgeConfigFlow()
    flow.hass = MagicMock()
    return flow


# ---------------------------------------------------------------------------
# User step
# ---------------------------------------------------------------------------

class TestUserStep:

    @pytest.mark.asyncio
    async def test_user_step_shows_form_on_none_input(self):
        flow = _make_flow()
        result = await flow.async_step_user(None)
        assert result["step_id"] == "user"
        assert result["type"] == "form"

    @pytest.mark.asyncio
    @patch(f"{MODULE_PATH}.async_get_clientsession")
    @patch(f"{MODULE_PATH}.BeestatApi")
    async def test_user_step_success(self, mock_api_cls, mock_session):
        mock_api = AsyncMock()
        mock_api.validate_api_key = AsyncMock(return_value=True)
        mock_api_cls.return_value = mock_api

        flow = _make_flow()
        result = await flow.async_step_user({CONF_API_KEY: VALID_KEY})

        assert result["type"] == "create_entry"
        assert result["data"][CONF_API_KEY] == VALID_KEY
        assert result["options"][CONF_FAST_POLL_INTERVAL] == DEFAULT_FAST_POLL_MINUTES
        assert result["options"][CONF_SLOW_POLL_INTERVAL] == DEFAULT_SLOW_POLL_MINUTES

    @pytest.mark.asyncio
    async def test_user_step_invalid_format_short(self):
        flow = _make_flow()
        result = await flow.async_step_user({CONF_API_KEY: SHORT_KEY})
        assert result["type"] == "form"
        assert result["errors"][CONF_API_KEY] == "invalid_api_key_format"

    @pytest.mark.asyncio
    async def test_user_step_invalid_format_non_hex(self):
        flow = _make_flow()
        result = await flow.async_step_user({CONF_API_KEY: NON_HEX_KEY})
        assert result["type"] == "form"
        assert result["errors"][CONF_API_KEY] == "invalid_api_key_format"

    @pytest.mark.asyncio
    @patch(f"{MODULE_PATH}.async_get_clientsession")
    @patch(f"{MODULE_PATH}.BeestatApi")
    async def test_user_step_auth_error(self, mock_api_cls, mock_session):
        from custom_components.buzzbridge.api import BeestatAuthError
        mock_api = AsyncMock()
        mock_api.validate_api_key = AsyncMock(side_effect=BeestatAuthError("bad key"))
        mock_api_cls.return_value = mock_api

        flow = _make_flow()
        result = await flow.async_step_user({CONF_API_KEY: VALID_KEY})
        assert result["type"] == "form"
        assert result["errors"][CONF_API_KEY] == "invalid_auth"

    @pytest.mark.asyncio
    @patch(f"{MODULE_PATH}.async_get_clientsession")
    @patch(f"{MODULE_PATH}.BeestatApi")
    async def test_user_step_connection_error(self, mock_api_cls, mock_session):
        from custom_components.buzzbridge.api import BeestatApiError
        mock_api = AsyncMock()
        mock_api.validate_api_key = AsyncMock(side_effect=BeestatApiError("timeout"))
        mock_api_cls.return_value = mock_api

        flow = _make_flow()
        result = await flow.async_step_user({CONF_API_KEY: VALID_KEY})
        assert result["type"] == "form"
        assert result["errors"]["base"] == "cannot_connect"

    @pytest.mark.asyncio
    @patch(f"{MODULE_PATH}.async_get_clientsession")
    @patch(f"{MODULE_PATH}.BeestatApi")
    async def test_user_step_unknown_error(self, mock_api_cls, mock_session):
        mock_api = AsyncMock()
        mock_api.validate_api_key = AsyncMock(side_effect=RuntimeError("surprise"))
        mock_api_cls.return_value = mock_api

        flow = _make_flow()
        result = await flow.async_step_user({CONF_API_KEY: VALID_KEY})
        assert result["type"] == "form"
        assert result["errors"]["base"] == "unknown"

    @pytest.mark.asyncio
    @patch(f"{MODULE_PATH}.async_get_clientsession")
    @patch(f"{MODULE_PATH}.BeestatApi")
    async def test_user_step_duplicate_aborts(self, mock_api_cls, mock_session):
        mock_api = AsyncMock()
        mock_api.validate_api_key = AsyncMock(return_value=True)
        mock_api_cls.return_value = mock_api

        flow = _make_flow()
        # Simulate _abort_if_unique_id_configured raising abort
        from homeassistant.config_entries import ConfigFlow
        original = ConfigFlow._abort_if_unique_id_configured

        def abort_configured(self):
            raise Exception("already_configured")

        with patch.object(type(flow), "_abort_if_unique_id_configured", abort_configured):
            with pytest.raises(Exception, match="already_configured"):
                await flow.async_step_user({CONF_API_KEY: VALID_KEY})


# ---------------------------------------------------------------------------
# Reauth step
# ---------------------------------------------------------------------------

class TestReauthStep:

    @pytest.mark.asyncio
    async def test_reauth_shows_form(self):
        flow = _make_flow()
        result = await flow.async_step_reauth({"api_key": "old"})
        assert result["type"] == "form"
        assert result["step_id"] == "reauth_confirm"

    @pytest.mark.asyncio
    @patch(f"{MODULE_PATH}.async_get_clientsession")
    @patch(f"{MODULE_PATH}.BeestatApi")
    async def test_reauth_confirm_success(self, mock_api_cls, mock_session):
        mock_api = AsyncMock()
        mock_api.validate_api_key = AsyncMock(return_value=True)
        mock_api_cls.return_value = mock_api

        flow = _make_flow()
        # Mock _get_reauth_entry
        mock_entry = MagicMock()
        mock_entry.data = {"api_key": "old_key"}
        flow._get_reauth_entry = MagicMock(return_value=mock_entry)

        result = await flow.async_step_reauth_confirm({CONF_API_KEY: VALID_KEY})
        assert result["type"] == "abort"
        assert result["reason"] == "reauth_successful"

    @pytest.mark.asyncio
    async def test_reauth_confirm_invalid_key_format(self):
        flow = _make_flow()
        result = await flow.async_step_reauth_confirm({CONF_API_KEY: SHORT_KEY})
        assert result["type"] == "form"
        assert result["errors"][CONF_API_KEY] == "invalid_api_key_format"

    @pytest.mark.asyncio
    @patch(f"{MODULE_PATH}.async_get_clientsession")
    @patch(f"{MODULE_PATH}.BeestatApi")
    async def test_reauth_confirm_auth_error(self, mock_api_cls, mock_session):
        from custom_components.buzzbridge.api import BeestatAuthError
        mock_api = AsyncMock()
        mock_api.validate_api_key = AsyncMock(side_effect=BeestatAuthError("bad"))
        mock_api_cls.return_value = mock_api

        flow = _make_flow()
        result = await flow.async_step_reauth_confirm({CONF_API_KEY: VALID_KEY})
        assert result["type"] == "form"
        assert result["errors"][CONF_API_KEY] == "invalid_auth"


# ---------------------------------------------------------------------------
# Reconfigure step
# ---------------------------------------------------------------------------

class TestReconfigureStep:

    @pytest.mark.asyncio
    async def test_reconfigure_shows_form(self):
        flow = _make_flow()
        result = await flow.async_step_reconfigure(None)
        assert result["type"] == "form"
        assert result["step_id"] == "reconfigure"

    @pytest.mark.asyncio
    @patch(f"{MODULE_PATH}.async_get_clientsession")
    @patch(f"{MODULE_PATH}.BeestatApi")
    async def test_reconfigure_success(self, mock_api_cls, mock_session):
        mock_api = AsyncMock()
        mock_api.validate_api_key = AsyncMock(return_value=True)
        mock_api_cls.return_value = mock_api

        flow = _make_flow()
        mock_entry = MagicMock()
        mock_entry.data = {"api_key": "old_key"}
        flow._get_reconfigure_entry = MagicMock(return_value=mock_entry)

        result = await flow.async_step_reconfigure({CONF_API_KEY: VALID_KEY})
        assert result["type"] == "abort"
        assert result["reason"] == "reauth_successful"

    @pytest.mark.asyncio
    async def test_reconfigure_invalid_key_format(self):
        flow = _make_flow()
        result = await flow.async_step_reconfigure({CONF_API_KEY: NON_HEX_KEY})
        assert result["type"] == "form"
        assert result["errors"][CONF_API_KEY] == "invalid_api_key_format"

    @pytest.mark.asyncio
    @patch(f"{MODULE_PATH}.async_get_clientsession")
    @patch(f"{MODULE_PATH}.BeestatApi")
    async def test_reconfigure_auth_error(self, mock_api_cls, mock_session):
        from custom_components.buzzbridge.api import BeestatAuthError
        mock_api = AsyncMock()
        mock_api.validate_api_key = AsyncMock(side_effect=BeestatAuthError("nope"))
        mock_api_cls.return_value = mock_api

        flow = _make_flow()
        result = await flow.async_step_reconfigure({CONF_API_KEY: VALID_KEY})
        assert result["type"] == "form"
        assert result["errors"][CONF_API_KEY] == "invalid_auth"


# ---------------------------------------------------------------------------
# Options flow
# ---------------------------------------------------------------------------

class TestOptionsFlow:

    @pytest.mark.asyncio
    async def test_options_flow_shows_form(self):
        entry = MagicMock()
        entry.options = {
            CONF_FAST_POLL_INTERVAL: 5,
            CONF_SLOW_POLL_INTERVAL: 30,
        }
        flow = BuzzBridgeOptionsFlow(entry)
        result = await flow.async_step_init(None)
        assert result["type"] == "form"
        assert result["step_id"] == "init"

    @pytest.mark.asyncio
    async def test_options_flow_success(self):
        entry = MagicMock()
        entry.options = {
            CONF_FAST_POLL_INTERVAL: 5,
            CONF_SLOW_POLL_INTERVAL: 30,
        }
        flow = BuzzBridgeOptionsFlow(entry)
        result = await flow.async_step_init({
            CONF_FAST_POLL_INTERVAL: 10,
            CONF_SLOW_POLL_INTERVAL: 45,
        })
        assert result["type"] == "create_entry"
        assert result["data"][CONF_FAST_POLL_INTERVAL] == 10
        assert result["data"][CONF_SLOW_POLL_INTERVAL] == 45
