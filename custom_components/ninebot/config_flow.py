from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .api import NinebotApiAuthError, NinebotApiConnectionError, NinebotCliClient
from .const import (
    CONF_AMAP_API_KEY,
    CONF_BUSINESS_UID,
    CONF_PASSWORD,
    CONF_POLL_INTERVAL,
    CONF_USERNAME,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    NINEBOT_STORAGE_DIR,
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
    if len(valid_devices) == 1 and (device_name := valid_devices[0].get("name")):
        return str(device_name)
    return "Ninebot"


def _read_business_uid_sync(config_dir: Path) -> str:
    try:
        payload = json.loads((config_dir / "tokens.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        raise NinebotApiConnectionError("Missing business_uid") from err

    business_uid = payload.get("business_uid")
    if not isinstance(business_uid, str) or not business_uid:
        raise NinebotApiConnectionError("Missing business_uid")
    return business_uid


def _move_config_to_permanent(temp_path: Path, permanent_path: Path) -> None:
    if permanent_path.exists():
        shutil.rmtree(permanent_path)
    permanent_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(temp_path), str(permanent_path))


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ninebot."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> OptionsFlow:
        return OptionsFlow(config_entry)

    def _storage_dir(self, business_uid: str) -> Path:
        return Path(self.hass.config.path(".storage", NINEBOT_STORAGE_DIR, business_uid))

    async def _async_validate_credentials(
        self,
        username: str,
        password: str,
    ) -> tuple[list[dict[str, Any]], str, str, Path]:
        temp_path = Path(tempfile.mkdtemp(prefix="ninebot-"))
        try:
            client = NinebotCliClient(temp_path)
            await client.async_login(username, password)
            devices = await client.async_get_device_list()
            business_uid = await self.hass.async_add_executor_job(
                _read_business_uid_sync, temp_path
            )
            permanent_path = self._storage_dir(business_uid)
            await self.hass.async_add_executor_job(
                _move_config_to_permanent, temp_path, permanent_path
            )
        finally:
            if temp_path.exists():
                await self.hass.async_add_executor_job(shutil.rmtree, temp_path)
        return devices, business_uid, _derive_title(devices), permanent_path

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]
            amap_api_key = user_input.get(CONF_AMAP_API_KEY, "").strip()

            try:
                _, business_uid, title, _ = await self._async_validate_credentials(
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
                await self.async_set_unique_id(business_uid)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_BUSINESS_UID: business_uid,
                        CONF_AMAP_API_KEY: amap_api_key,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_AMAP_API_KEY): str,
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
            amap_api_key = user_input.get(CONF_AMAP_API_KEY, "").strip()

            try:
                _, business_uid, _, _ = await self._async_validate_credentials(
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
                    await self.async_set_unique_id(business_uid)
                    self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_BUSINESS_UID: business_uid,
                        CONF_AMAP_API_KEY: amap_api_key,
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
                    vol.Optional(
                        CONF_AMAP_API_KEY,
                        default=entry.options.get(
                            CONF_AMAP_API_KEY,
                            entry.data.get(CONF_AMAP_API_KEY, ""),
                        ),
                    ): str,
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
            user_input[CONF_AMAP_API_KEY] = user_input.get(CONF_AMAP_API_KEY, "").strip()
            return self.async_create_entry(data=user_input)

        poll_interval = self._config_entry.options.get(
            CONF_POLL_INTERVAL,
            DEFAULT_POLL_INTERVAL,
        )
        amap_api_key = self._config_entry.options.get(
            CONF_AMAP_API_KEY,
            self._config_entry.data.get(CONF_AMAP_API_KEY, ""),
        )
        if not isinstance(amap_api_key, str):
            amap_api_key = ""

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_POLL_INTERVAL, default=poll_interval): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=30, max=86400),
                    ),
                    vol.Optional(CONF_AMAP_API_KEY, default=amap_api_key): str,
                }
            ),
        )
