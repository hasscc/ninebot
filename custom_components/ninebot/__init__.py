"""The integration of Home Assistant"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NinebotApiClient, NinebotTokens
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_ACCESS_TOKEN_VALIDITY,
    CONF_PASSWORD,
    CONF_REFRESH_TOKEN,
    CONF_USERNAME,
    PLATFORMS,
)
from .coordinator import NinebotDataUpdateCoordinator

LOGGER = logging.getLogger(__name__)


type NinebotConfigEntry = ConfigEntry[NinebotDataUpdateCoordinator]


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    return True

async def async_setup_entry(hass: HomeAssistant, entry: NinebotConfigEntry) -> bool:
    async def _async_handle_token_update(tokens: NinebotTokens) -> None:
        updated_data = {
            **entry.data,
            CONF_ACCESS_TOKEN: tokens.access_token,
            CONF_REFRESH_TOKEN: tokens.refresh_token,
            CONF_ACCESS_TOKEN_VALIDITY: tokens.access_token_validity,
        }
        if updated_data != entry.data:
            hass.config_entries.async_update_entry(entry, data=updated_data)

    client = NinebotApiClient(
        async_get_clientsession(hass),
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        access_token=entry.data.get(CONF_ACCESS_TOKEN),
        refresh_token=entry.data.get(CONF_REFRESH_TOKEN),
        access_token_validity=entry.data.get(CONF_ACCESS_TOKEN_VALIDITY),
        token_update_callback=_async_handle_token_update,
    )
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
