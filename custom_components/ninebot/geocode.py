from __future__ import annotations

from math import atan2, cos, pi, sin, sqrt
from typing import Any

from aiohttp import ClientError, ClientSession

from .const import API_TIMEOUT

AMAP_REVERSE_GEOCODE_URL = "https://restapi.amap.com/v3/geocode/regeo"
AMAP_CACHE_DISTANCE_METERS = 50.0

_GCJ_A = 6378245.0
_GCJ_EE = 0.00669342162296594323


class AmapGeocodeError(Exception):
    """Raised when AMap reverse geocoding fails."""


class AmapReverseGeocoder:
    """Reverse geocode WGS-84 coordinates with AMap."""

    def __init__(self, session: ClientSession, api_key: str) -> None:
        self._session = session
        self._api_key = api_key

    async def async_reverse_geocode(self, latitude: float, longitude: float) -> dict[str, Any]:
        amap_longitude, amap_latitude = wgs84_to_gcj02(longitude, latitude)
        params = {
            "key": self._api_key,
            "location": f"{amap_longitude:.7f},{amap_latitude:.7f}",
            "extensions": "base",
            "radius": "1000",
            "roadlevel": "0",
            "output": "json",
        }

        try:
            response = await self._session.get(
                AMAP_REVERSE_GEOCODE_URL,
                params=params,
                timeout=API_TIMEOUT,
            )
            response.raise_for_status()
            payload = await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            raise AmapGeocodeError(str(err)) from err

        if not isinstance(payload, dict):
            raise AmapGeocodeError("Unexpected AMap response")

        if payload.get("status") != "1":
            message = payload.get("info") or payload.get("infocode") or "AMap request failed"
            raise AmapGeocodeError(str(message))

        regeocode = payload.get("regeocode")
        if not isinstance(regeocode, dict):
            raise AmapGeocodeError("Missing AMap regeocode")

        address = regeocode.get("formatted_address")
        if not isinstance(address, str) or not address:
            raise AmapGeocodeError("Missing AMap formatted address")

        address_component = regeocode.get("addressComponent")
        if not isinstance(address_component, dict):
            address_component = {}

        return {
            "formatted_address": address,
            "provider": "amap",
            "source_coordinate_system": "wgs84",
            "coordinate_system": "gcj02",
            "latitude": latitude,
            "longitude": longitude,
            "amap_latitude": amap_latitude,
            "amap_longitude": amap_longitude,
            "province": _string_value(address_component.get("province")),
            "city": _string_value(address_component.get("city")),
            "district": _string_value(address_component.get("district")),
            "township": _string_value(address_component.get("township")),
            "adcode": _string_value(address_component.get("adcode")),
        }


def distance_meters(
    first_latitude: float,
    first_longitude: float,
    second_latitude: float,
    second_longitude: float,
) -> float:
    """Return approximate distance between two WGS-84 coordinates."""
    radius = 6371000.0
    first_lat = first_latitude * pi / 180.0
    second_lat = second_latitude * pi / 180.0
    delta_lat = (second_latitude - first_latitude) * pi / 180.0
    delta_lon = (second_longitude - first_longitude) * pi / 180.0

    haversine = (
        sin(delta_lat / 2.0) ** 2
        + cos(first_lat) * cos(second_lat) * sin(delta_lon / 2.0) ** 2
    )
    return radius * 2.0 * _atan2_sqrt(haversine)


def wgs84_to_gcj02(longitude: float, latitude: float) -> tuple[float, float]:
    """Convert WGS-84 coordinates to GCJ-02 for mainland China map providers."""
    if _out_of_china(longitude, latitude):
        return longitude, latitude

    delta_latitude = _transform_latitude(longitude - 105.0, latitude - 35.0)
    delta_longitude = _transform_longitude(longitude - 105.0, latitude - 35.0)
    rad_latitude = latitude / 180.0 * pi
    magic = sin(rad_latitude)
    magic = 1 - _GCJ_EE * magic * magic
    sqrt_magic = sqrt(magic)
    delta_latitude = (
        delta_latitude
        * 180.0
        / ((_GCJ_A * (1 - _GCJ_EE)) / (magic * sqrt_magic) * pi)
    )
    delta_longitude = (
        delta_longitude
        * 180.0
        / (_GCJ_A / sqrt_magic * cos(rad_latitude) * pi)
    )
    return longitude + delta_longitude, latitude + delta_latitude


def _string_value(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _atan2_sqrt(value: float) -> float:
    value = min(1.0, max(0.0, value))
    return atan2(sqrt(value), sqrt(1.0 - value))


def _out_of_china(longitude: float, latitude: float) -> bool:
    return not (73.66 <= longitude <= 135.05 and 3.86 <= latitude <= 53.55)


def _transform_latitude(longitude: float, latitude: float) -> float:
    ret = (
        -100.0
        + 2.0 * longitude
        + 3.0 * latitude
        + 0.2 * latitude * latitude
        + 0.1 * longitude * latitude
        + 0.2 * sqrt(abs(longitude))
    )
    ret += (
        20.0 * sin(6.0 * longitude * pi)
        + 20.0 * sin(2.0 * longitude * pi)
    ) * 2.0 / 3.0
    ret += (
        20.0 * sin(latitude * pi)
        + 40.0 * sin(latitude / 3.0 * pi)
    ) * 2.0 / 3.0
    ret += (
        160.0 * sin(latitude / 12.0 * pi)
        + 320.0 * sin(latitude * pi / 30.0)
    ) * 2.0 / 3.0
    return ret


def _transform_longitude(longitude: float, latitude: float) -> float:
    ret = (
        300.0
        + longitude
        + 2.0 * latitude
        + 0.1 * longitude * longitude
        + 0.1 * longitude * latitude
        + 0.1 * sqrt(abs(longitude))
    )
    ret += (
        20.0 * sin(6.0 * longitude * pi)
        + 20.0 * sin(2.0 * longitude * pi)
    ) * 2.0 / 3.0
    ret += (
        20.0 * sin(longitude * pi)
        + 40.0 * sin(longitude / 3.0 * pi)
    ) * 2.0 / 3.0
    ret += (
        150.0 * sin(longitude / 12.0 * pi)
        + 300.0 * sin(longitude / 30.0 * pi)
    ) * 2.0 / 3.0
    return ret
