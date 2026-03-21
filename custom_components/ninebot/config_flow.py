from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    NinebotApiAuthError,
    NinebotApiClient,
    NinebotApiConnectionError,
    NinebotTokens,
)
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_ACCESS_TOKEN_VALIDITY,
    CONF_PASSWORD,
    CONF_POLL_INTERVAL,
    CONF_REFRESH_TOKEN,
    CONF_USERNAME,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
)


def _device_sort_key(device: dict[str, Any]) -> str:
    sn = device.get("sn")
    return str(sn) if isinstance(sn, str) else ""


def _valid_devices(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        device
        for device in sorted(devices, key=_device_sort_key)
        if isinstance(device.get("sn"), str) and device["sn"]
    ]


def _derive_title(devices: list[dict[str, Any]]) -> str:
    valid_devices = _valid_devices(devices)
    if len(valid_devices) == 1 and (device_name := valid_devices[0].get("deviceName")):
        return str(device_name)
    return "Ninebot"


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ninebot."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> OptionsFlow:
        return OptionsFlow(config_entry)

    async def _async_validate_credentials(
        self,
        username: str,
        password: str,
    ) -> tuple[list[dict[str, Any]], NinebotTokens, str, str]:
        client = NinebotApiClient(
            async_get_clientsession(self.hass),
            username=username,
            password=password,
        )
        tokens = await client.async_login()
        user_uuid = client.user_uuid
        if user_uuid is None:
            raise NinebotApiConnectionError("Missing user UUID after login")
        devices = await client.async_get_device_list()
        return devices, tokens, user_uuid, _derive_title(devices)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]

            try:
                _, tokens, unique_id, title = await self._async_validate_credentials(
                    username,
                    password,
                )
            except NinebotApiAuthError:
                errors["base"] = "invalid_auth"
            except NinebotApiConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_ACCESS_TOKEN: tokens.access_token,
                        CONF_REFRESH_TOKEN: tokens.refresh_token,
                        CONF_ACCESS_TOKEN_VALIDITY: tokens.access_token_validity,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]

            try:
                _, tokens, unique_id, _ = await self._async_validate_credentials(
                    username,
                    password,
                )
            except NinebotApiAuthError:
                errors["base"] = "invalid_auth"
            except NinebotApiConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"
            else:
                if entry.unique_id is not None:
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_ACCESS_TOKEN: tokens.access_token,
                        CONF_REFRESH_TOKEN: tokens.refresh_token,
                        CONF_ACCESS_TOKEN_VALIDITY: tokens.access_token_validity,
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=entry.data.get(CONF_USERNAME, ""),
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
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
