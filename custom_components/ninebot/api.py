from __future__ import annotations

from http import HTTPStatus
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession

from .const import API_TIMEOUT, BASE_URL


class NinebotApiError(Exception):
    """Base exception for Ninebot API errors."""


class NinebotApiAuthError(NinebotApiError):
    """Raised when authentication fails."""


class NinebotApiConnectionError(NinebotApiError):
    """Raised when the API request fails."""


class NinebotApiClient:
    """Async client for the Ninebot cloud API."""

    def __init__(self, session: ClientSession, api_key: str) -> None:
        self._session = session
        self._api_key = api_key

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    async def async_get_device_list(self) -> list[dict[str, Any]]:
        payload = await self._async_request(
            "get",
            "/ai-skill/api/device/info/get-device-list",
        )
        data = payload.get("data")
        if isinstance(data, list):
            return [device for device in data if isinstance(device, dict)]
        return []

    async def async_get_device_dynamic_info(self, sn: str) -> dict[str, Any]:
        payload = await self._async_request(
            "post",
            "/ai-skill/api/device/info/get-device-dynamic-info",
            json={"sn": sn},
        )
        data = payload.get("data")
        if isinstance(data, dict):
            return data
        return {}

    async def _async_request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = f"{BASE_URL}{path}"

        try:
            response = await self._session.request(
                method,
                url,
                headers=self._headers,
                timeout=API_TIMEOUT,
                **kwargs,
            )
            response.raise_for_status()
        except ClientResponseError as err:
            if err.status in {HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN}:
                raise NinebotApiAuthError from err
            raise NinebotApiConnectionError from err
        except ClientError as err:
            raise NinebotApiConnectionError from err

        try:
            payload = await response.json(content_type=None)
        except (ClientError, ValueError) as err:
            raise NinebotApiConnectionError from err

        if not isinstance(payload, dict):
            raise NinebotApiConnectionError

        if payload.get("code") == 1:
            return payload

        desc = str(payload.get("desc", ""))
        if self._is_auth_error(desc):
            raise NinebotApiAuthError(desc)
        raise NinebotApiConnectionError(desc)

    @staticmethod
    def _is_auth_error(desc: str) -> bool:
        normalized = desc.lower()
        return any(
            marker in normalized
            for marker in (
                "auth",
                "token",
                "unauthorized",
                "forbidden",
                "invalid api key",
                "api key",
                "鉴权",
                "认证",
                "授权",
                "令牌",
            )
        )
