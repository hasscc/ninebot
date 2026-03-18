from __future__ import annotations

import hashlib
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NinebotApiAuthError, NinebotApiClient, NinebotApiConnectionError
from .const import CONF_API_KEY, CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL, DOMAIN


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ninebot."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> OptionsFlow:
        return OptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            unique_id = _hash_api_key(api_key)
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            client = NinebotApiClient(
                async_get_clientsession(self.hass),
                api_key,
            )

            try:
                await client.async_get_device_list()
            except NinebotApiAuthError:
                errors["base"] = "invalid_auth"
            except NinebotApiConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"Ninebot {unique_id[:6]}",
                    data={CONF_API_KEY: api_key},
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


class OptionsFlow(config_entries.OptionsFlow):
    """Handle Ninebot options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        poll_interval = self._config_entry.options.get(
            CONF_POLL_INTERVAL,
            DEFAULT_POLL_INTERVAL,
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_POLL_INTERVAL, default=poll_interval): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=30, max=86400),
                    )
                }
            ),
        )


def _hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()
