# BuzzBridge - Config Flow
# Rev: 1.3
#
# Handles the UI setup flow for BuzzBridge:
#   1. User enters their Beestat API key (40-character hex string)
#   2. Key is validated against the Beestat API
#   3. Entry is created; poll intervals configurable via Options flow
#
# The API key is stored in HA's .storage (encrypted at rest by HA).

from __future__ import annotations

import hashlib
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BeestatApi, BeestatApiError, BeestatAuthError
from .const import (
    CONF_API_KEY,
    CONF_FAST_POLL_INTERVAL,
    CONF_SLOW_POLL_INTERVAL,
    DEFAULT_FAST_POLL_MINUTES,
    DEFAULT_SLOW_POLL_MINUTES,
    DOMAIN,
    MAX_POLL_MINUTES,
    MIN_POLL_MINUTES,
)

_LOGGER = logging.getLogger(__name__)

API_KEY_LENGTH = 40


class BuzzBridgeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for BuzzBridge."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step — API key entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip().lower()

            # Basic format validation (40 hex characters)
            if len(api_key) != API_KEY_LENGTH or not all(
                c in "0123456789abcdef" for c in api_key
            ):
                errors[CONF_API_KEY] = "invalid_api_key_format"
            else:
                # Validate against the Beestat API using HA's shared session
                try:
                    session = async_get_clientsession(self.hass)
                    api = BeestatApi(session, api_key)
                    await api.validate_api_key()
                except BeestatAuthError:
                    errors[CONF_API_KEY] = "invalid_auth"
                except BeestatApiError:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected error during API key validation")
                    errors["base"] = "unknown"

            if not errors:
                # Use a hash of the full key as unique ID to prevent duplicates
                # without exposing the raw key in the config entry ID
                unique = hashlib.sha256(api_key.encode()).hexdigest()[:32]
                await self.async_set_unique_id(unique)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="BuzzBridge",
                    data={CONF_API_KEY: api_key},
                    options={
                        CONF_FAST_POLL_INTERVAL: DEFAULT_FAST_POLL_MINUTES,
                        CONF_SLOW_POLL_INTERVAL: DEFAULT_SLOW_POLL_MINUTES,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication when the API key becomes invalid."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth confirmation — prompt for new API key."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip().lower()

            if len(api_key) != API_KEY_LENGTH or not all(
                c in "0123456789abcdef" for c in api_key
            ):
                errors[CONF_API_KEY] = "invalid_api_key_format"
            else:
                try:
                    session = async_get_clientsession(self.hass)
                    api = BeestatApi(session, api_key)
                    await api.validate_api_key()
                except BeestatAuthError:
                    errors[CONF_API_KEY] = "invalid_auth"
                except BeestatApiError:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected error during reauth validation")
                    errors["base"] = "unknown"

            if not errors:
                reauth_entry = self._get_reauth_entry()
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={**reauth_entry.data, CONF_API_KEY: api_key},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration — allow changing API key from Configure menu."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip().lower()

            if len(api_key) != API_KEY_LENGTH or not all(
                c in "0123456789abcdef" for c in api_key
            ):
                errors[CONF_API_KEY] = "invalid_api_key_format"
            else:
                try:
                    session = async_get_clientsession(self.hass)
                    api = BeestatApi(session, api_key)
                    await api.validate_api_key()
                except BeestatAuthError:
                    errors[CONF_API_KEY] = "invalid_auth"
                except BeestatApiError:
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected error during reconfigure")
                    errors["base"] = "unknown"

            if not errors:
                reconfigure_entry = self._get_reconfigure_entry()
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data={**reconfigure_entry.data, CONF_API_KEY: api_key},
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> BuzzBridgeOptionsFlow:
        """Get the options flow handler."""
        return BuzzBridgeOptionsFlow(config_entry)


class BuzzBridgeOptionsFlow(OptionsFlow):
    """Options flow for BuzzBridge — poll interval configuration."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options step."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_fast = self._config_entry.options.get(
            CONF_FAST_POLL_INTERVAL, DEFAULT_FAST_POLL_MINUTES
        )
        current_slow = self._config_entry.options.get(
            CONF_SLOW_POLL_INTERVAL, DEFAULT_SLOW_POLL_MINUTES
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_FAST_POLL_INTERVAL,
                        default=current_fast,
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_POLL_MINUTES, max=MAX_POLL_MINUTES),
                    ),
                    vol.Required(
                        CONF_SLOW_POLL_INTERVAL,
                        default=current_slow,
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_POLL_MINUTES, max=MAX_POLL_MINUTES),
                    ),
                }
            ),
        )
