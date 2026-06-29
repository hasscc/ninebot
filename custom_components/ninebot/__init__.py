"""The integration of Home Assistant"""
from __future__ import annotations

import json
import logging
from pathlib import Path
import shutil
import tempfile
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .api import NinebotApiAuthError, NinebotApiConnectionError, NinebotCliClient
from .const import (
    CONF_BUSINESS_UID,
    CONF_PASSWORD,
    CONF_USERNAME,
    NINEBOT_STORAGE_DIR,
    PLATFORMS,
)
from .coordinator import NinebotDataUpdateCoordinator

LOGGER = logging.getLogger(__name__)


type NinebotConfigEntry = ConfigEntry[NinebotDataUpdateCoordinator]


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    return True


async def async_setup_entry(hass: HomeAssistant, entry: NinebotConfigEntry) -> bool:
    business_uid = entry.data.get(CONF_BUSINESS_UID)
    if not isinstance(business_uid, str) or not business_uid:
        business_uid = await _async_upgrade_entry(hass, entry)

    config_dir = _storage_dir(hass, business_uid)
    client = NinebotCliClient(config_dir)
    coordinator = NinebotDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NinebotConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: NinebotConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _storage_dir(hass: HomeAssistant, business_uid: str) -> Path:
    return Path(hass.config.path(".storage", NINEBOT_STORAGE_DIR, business_uid))


async def _async_upgrade_entry(hass: HomeAssistant, entry: NinebotConfigEntry) -> str:
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    temp_path = Path(tempfile.mkdtemp(prefix="ninebot-"))
    try:
        client = NinebotCliClient(temp_path)
        try:
            await client.async_login(username, password)
            await client.async_get_device_list()
        except (NinebotApiAuthError, NinebotApiConnectionError) as err:
            raise ConfigEntryAuthFailed from err

        business_uid = await hass.async_add_executor_job(
            _read_business_uid_sync, temp_path
        )
        permanent_path = _storage_dir(hass, business_uid)
        await hass.async_add_executor_job(
            _move_config_to_permanent, temp_path, permanent_path
        )
    finally:
        if temp_path.exists():
            await hass.async_add_executor_job(shutil.rmtree, temp_path)

    hass.config_entries.async_update_entry(
        entry,
        data={
            CONF_USERNAME: username,
            CONF_PASSWORD: password,
            CONF_BUSINESS_UID: business_uid,
        },
        unique_id=business_uid,
    )
    return business_uid


def _read_business_uid_sync(config_dir: Path) -> str:
    try:
        payload = json.loads((config_dir / "tokens.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        raise ConfigEntryAuthFailed from err

    business_uid = payload.get("business_uid")
    if not isinstance(business_uid, str) or not business_uid:
        raise ConfigEntryAuthFailed
    return business_uid


def _move_config_to_permanent(temp_path: Path, permanent_path: Path) -> None:
    if permanent_path.exists():
        shutil.rmtree(permanent_path)
    permanent_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(temp_path), str(permanent_path))
