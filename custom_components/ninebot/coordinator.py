from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import NinebotApiAuthError, NinebotApiConnectionError, NinebotCliClient
from .const import CONF_AMAP_API_KEY, CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL, DOMAIN
from .geocode import (
    AMAP_CACHE_DISTANCE_METERS,
    AmapGeocodeError,
    AmapReverseGeocoder,
    distance_meters,
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
        self._address_cache: dict[str, tuple[float, float, dict[str, Any]]] = {}
        amap_api_key = _entry_amap_api_key(entry)
        self._amap_geocoder = (
            AmapReverseGeocoder(async_get_clientsession(hass), amap_api_key)
            if amap_api_key
            else None
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
            payloads = await self._client.async_get_all_device_payloads()
        except NinebotApiAuthError as err:
            raise ConfigEntryAuthFailed from err
        except NinebotApiConnectionError as err:
            raise UpdateFailed(str(err) or "Failed to fetch Ninebot data") from err

        if self._amap_geocoder is not None:
            await self._async_update_addresses(payloads)

        merged_devices = {payload["sn"]: payload for payload in payloads}
        return {"devices": merged_devices}

    async def _async_update_addresses(self, payloads: list[dict[str, Any]]) -> None:
        for payload in payloads:
            sn = payload.get("sn")
            state = payload.get("state")
            if not isinstance(sn, str) or not isinstance(state, dict):
                continue

            location = state.get("location")
            if not isinstance(location, dict):
                continue

            latitude = location.get("latitude")
            longitude = location.get("longitude")
            if not isinstance(latitude, int | float) or not isinstance(longitude, int | float):
                continue

            cached = self._address_cache.get(sn)
            if cached is not None:
                cached_latitude, cached_longitude, cached_address = cached
                if (
                    distance_meters(
                        cached_latitude,
                        cached_longitude,
                        latitude,
                        longitude,
                    )
                    <= AMAP_CACHE_DISTANCE_METERS
                ):
                    state["address"] = cached_address
                    continue

            try:
                address = await self._amap_geocoder.async_reverse_geocode(
                    latitude,
                    longitude,
                )
            except AmapGeocodeError as err:
                LOGGER.debug("Failed to reverse geocode Ninebot location for %s: %s", sn, err)
                state["address"] = {
                    "error": str(err),
                    "latitude": latitude,
                    "longitude": longitude,
                    "provider": "amap",
                }
            else:
                self._address_cache[sn] = (latitude, longitude, address)
                state["address"] = address

    async def async_request_device_status_refresh(self, sn: str) -> None:
        try:
            status = await self._client.async_get_device_status(sn)
        except NinebotApiAuthError as err:
            raise ConfigEntryAuthFailed from err
        except NinebotApiConnectionError as err:
            raise UpdateFailed(str(err) or "Failed to fetch Ninebot status") from err

        data = self.data or {"devices": {}}
        devices = data.get("devices", {})
        if not isinstance(devices, dict):
            return

        device = devices.get(sn)
        if not isinstance(device, dict):
            return

        current_state = device.get("state", {})
        if not isinstance(current_state, dict):
            current_state = {}

        preserved_state = {
            key: value
            for key, value in current_state.items()
            if key.startswith("month_") or key.startswith("last_") or key == "address"
        }
        updated_state = {**preserved_state, **status}
        if self._amap_geocoder is not None:
            payload = {"sn": sn, "state": updated_state}
            await self._async_update_addresses([payload])
            updated_state = payload["state"]

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


def _entry_amap_api_key(entry: ConfigEntry) -> str:
    value = entry.options.get(CONF_AMAP_API_KEY, entry.data.get(CONF_AMAP_API_KEY, ""))
    return value.strip() if isinstance(value, str) else ""
