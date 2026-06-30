from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import NinebotApiAuthError, NinebotApiConnectionError, NinebotCliClient
from .const import (
    CONF_DEVICE_DELAY,
    CONF_KEEP_LAST_DATA_ON_ERROR,
    CONF_POLL_INTERVAL,
    CONF_REQUEST_DELAY,
    DEFAULT_DEVICE_DELAY,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_REQUEST_DELAY,
    DOMAIN,
)

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
        self._keep_last_data_on_error = bool(
            entry.options.get(CONF_KEEP_LAST_DATA_ON_ERROR, False)
        )
        self._request_delay = _entry_delay(
            entry,
            CONF_REQUEST_DELAY,
            DEFAULT_REQUEST_DELAY,
        )
        self._device_delay = _entry_delay(
            entry,
            CONF_DEVICE_DELAY,
            DEFAULT_DEVICE_DELAY,
        )
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
            payloads = await self._async_get_device_payloads()
        except NinebotApiAuthError as err:
            raise ConfigEntryAuthFailed from err
        except NinebotApiConnectionError as err:
            if self._keep_last_data_on_error and self.data:
                LOGGER.warning("Keeping previous Ninebot data after update failure: %s", err)
                return self.data
            raise UpdateFailed(str(err) or "Failed to fetch Ninebot data") from err

        merged_devices = {payload["sn"]: payload for payload in payloads}
        return {"devices": merged_devices}

    async def _async_get_device_payloads(self) -> list[dict[str, Any]]:
        devices = await self._client.async_get_device_list()
        await self._async_request_delay()
        previous_devices = self._previous_devices
        results: list[dict[str, Any]] = []

        for index, device in enumerate(devices):
            sn = device.get("sn")
            if not isinstance(sn, str) or not sn:
                continue

            if index > 0:
                await self._async_device_delay()

            try:
                state = await self._async_get_device_state(sn)
            except NinebotApiConnectionError as err:
                previous_payload = previous_devices.get(sn)
                if self._keep_last_data_on_error and isinstance(previous_payload, dict):
                    LOGGER.warning(
                        "Keeping previous Ninebot data for %s after update failure: %s",
                        sn,
                        err,
                    )
                    results.append(previous_payload)
                    continue
                raise

            results.append({
                "sn": sn,
                "info": device,
                "state": state,
            })

        return results

    async def _async_get_device_state(self, sn: str) -> dict[str, Any]:
        state = await self._client.async_get_device_status(sn)
        await self._async_request_delay()

        try:
            travel = await self._client.async_get_device_travel(sn)
        except NinebotApiConnectionError as err:
            LOGGER.debug("Failed to fetch Ninebot travel data for %s: %s", sn, err)
        else:
            if isinstance(travel, dict):
                state.update(self._client.normalize_travel(travel))
        return state

    async def _async_request_delay(self) -> None:
        if self._request_delay > 0:
            await asyncio.sleep(self._request_delay)

    async def _async_device_delay(self) -> None:
        if self._device_delay > 0:
            await asyncio.sleep(self._device_delay)

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

    @property
    def _previous_devices(self) -> dict[str, Any]:
        if not isinstance(self.data, dict):
            return {}
        devices = self.data.get("devices")
        return devices if isinstance(devices, dict) else {}


def _entry_delay(entry: ConfigEntry, key: str, default: int) -> int:
    try:
        return max(0, int(entry.options.get(key, default)))
    except (TypeError, ValueError):
        return default
