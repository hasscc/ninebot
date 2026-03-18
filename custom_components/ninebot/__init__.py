"""The integration of Home Assistant"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NinebotApiClient
from .const import CONF_API_KEY, PLATFORMS
from .coordinator import NinebotDataUpdateCoordinator


type NinebotConfigEntry = ConfigEntry[NinebotDataUpdateCoordinator]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    return True


async def async_setup_entry(hass: HomeAssistant, entry: NinebotConfigEntry) -> bool:
    client = NinebotApiClient(
        async_get_clientsession(hass),
        entry.data[CONF_API_KEY],
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
