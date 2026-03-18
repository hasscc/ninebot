from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import NinebotApiAuthError, NinebotApiClient, NinebotApiConnectionError
from .const import CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL, DOMAIN

LOGGER = logging.getLogger(__package__)


class NinebotDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate Ninebot API polling."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: NinebotApiClient,
    ) -> None:
        self.config_entry = entry
        self._client = client
        update_interval = timedelta(
            seconds=entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
        )
        super().__init__(
            hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            devices = await self._client.async_get_device_list()
            results = await asyncio.gather(
                *(self._async_fetch_device_payload(device) for device in devices)
            )
        except NinebotApiAuthError as err:
            raise ConfigEntryAuthFailed from err
        except NinebotApiConnectionError as err:
            raise UpdateFailed(str(err) or "Failed to fetch Ninebot data") from err

        merged_devices: dict[str, dict[str, Any]] = {}
        for result in results:
            if result is None:
                continue
            sn, payload = result
            merged_devices[sn] = payload

        return {"devices": merged_devices}

    async def _async_fetch_device_payload(
        self, device: dict[str, Any]
    ) -> tuple[str, dict[str, Any]] | None:
        sn = device.get("sn")
        if not isinstance(sn, str) or not sn:
            return None

        dynamic = await self._client.async_get_device_dynamic_info(sn)
        return sn, {
            "info": device,
            "dynamic": dynamic,
        }
