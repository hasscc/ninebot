from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import NinebotApiAuthError, NinebotApiConnectionError, NinebotCliClient
from .const import CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL, DOMAIN

LOGGER = logging.getLogger(__package__)


class NinebotDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate Ninebot API polling."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: NinebotCliClient,
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
            payloads = await self._client.async_get_all_device_payloads()
        except NinebotApiAuthError as err:
            raise ConfigEntryAuthFailed from err
        except NinebotApiConnectionError as err:
            raise UpdateFailed(str(err) or "Failed to fetch Ninebot data") from err

        merged_devices = {payload["sn"]: payload for payload in payloads}
        return {"devices": merged_devices}

    async def async_request_device_status_refresh(self, sn: str) -> None:
        try:
            status = await self._client.async_get_device_status(sn)
        except NinebotApiAuthError as err:
            raise ConfigEntryAuthFailed from err
        except NinebotApiConnectionError as err:
            raise UpdateFailed(str(err) or "Failed to fetch Ninebot status") from err

        data = self.data or {"devices": {}}
        devices = data.get("devices", {})
        device = devices.get(sn)
        if device is None:
            return

        current_state = device.get("state", {})
        travel_state = {
            key: value
            for key, value in current_state.items()
            if key.startswith("month_") or key.startswith("last_")
        }
        updated_state = {**travel_state, **status}
        current_visible_state = {
            key: value for key, value in current_state.items() if key != "raw"
        }
        updated_visible_state = {
            key: value for key, value in updated_state.items() if key != "raw"
        }
        if updated_visible_state == current_visible_state:
            return

        updated_device = {
            **device,
            "state": updated_state,
        }
        self.async_set_updated_data({
            **data,
            "devices": {
                **devices,
                sn: updated_device,
            },
        })
