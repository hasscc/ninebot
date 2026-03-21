from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession

from .const import (
    API_TIMEOUT,
    CLIENT_ID,
    DEFAULT_LANGUAGE,
    DEVICE_BASE_URL,
    DEVICE_DYNAMIC_PATH,
    DEVICE_LIST_PATH,
    LOGIN_BASE_URL,
    LOGIN_PATH,
)


type TokenUpdateCallback = Callable[[NinebotTokens], Awaitable[None]]


@dataclass(slots=True)
class NinebotTokens:
    """Authentication tokens returned by the Ninebot API."""

    access_token: str
    refresh_token: str
    access_token_validity: int | None


class NinebotApiError(Exception):
    """Base exception for Ninebot API errors."""


class NinebotApiAuthError(NinebotApiError):
    """Raised when authentication fails."""


class NinebotApiConnectionError(NinebotApiError):
    """Raised when the API request fails."""


class NinebotApiClient:
    """Async client for the Ninebot cloud API."""

    def __init__(
        self,
        session: ClientSession,
        username: str,
        password: str,
        access_token: str | None = None,
        refresh_token: str | None = None,
        access_token_validity: int | None = None,
        token_update_callback: TokenUpdateCallback | None = None,
    ) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._access_token_validity = access_token_validity
        self._token_update_callback = token_update_callback
        self._user_uuid: str | None = None

    @property
    def tokens(self) -> NinebotTokens:
        """Return the current token state."""
        return NinebotTokens(
            access_token=self._access_token or "",
            refresh_token=self._refresh_token or "",
            access_token_validity=self._access_token_validity,
        )

    @property
    def user_uuid(self) -> str | None:
        """Return the user UUID from the most recent successful login."""
        return self._user_uuid

    async def async_login(self) -> NinebotTokens:
        """Authenticate with username and password and store returned tokens."""
        payload = await self._async_raw_request(
            "post",
            LOGIN_BASE_URL,
            LOGIN_PATH,
            json={
                "username": self._username,
                "password": self._password,
            },
        )

        if payload.get("resultCode") != "90000":
            message = str(payload.get("resultDesc", "Authentication failed"))
            raise NinebotApiAuthError(message)

        data = payload.get("data")
        if not isinstance(data, dict):
            raise NinebotApiConnectionError("Missing login response data")

        user_uuid = data.get("uuid")
        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token")
        access_token_validity = data.get("accessTokenValidity")

        if not isinstance(user_uuid, str) or not user_uuid:
            raise NinebotApiConnectionError("Missing user UUID in login response")
        if not isinstance(access_token, str) or not access_token:
            raise NinebotApiConnectionError("Missing access token in login response")
        if not isinstance(refresh_token, str):
            refresh_token = ""
        if not isinstance(access_token_validity, int):
            access_token_validity = None

        self._user_uuid = user_uuid

        tokens = NinebotTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            access_token_validity=access_token_validity,
        )
        await self._async_set_tokens(tokens)
        return tokens

    async def async_get_device_list(self) -> list[dict[str, Any]]:
        payload = await self._async_device_request(
            DEVICE_LIST_PATH,
            json={},
        )
        data = payload.get("data")
        if isinstance(data, list):
            return [device for device in data if isinstance(device, dict)]
        return []

    async def async_get_device_dynamic_info(self, sn: str) -> dict[str, Any]:
        payload = await self._async_device_request(
            DEVICE_DYNAMIC_PATH,
            json={"sn": sn},
        )
        data = payload.get("data")
        if isinstance(data, dict):
            return data
        return {}

    async def _async_device_request(self, path: str, json: dict[str, Any]) -> dict[str, Any]:
        if not self._access_token:
            await self.async_login()

        request_body = {
            "lang": DEFAULT_LANGUAGE,
            "access_token": self._access_token,
            **json,
        }

        try:
            return await self._async_raw_request(
                "post",
                DEVICE_BASE_URL,
                path,
                json=request_body,
            )
        except NinebotApiAuthError:
            await self.async_login()
            retry_body = {
                "lang": DEFAULT_LANGUAGE,
                "access_token": self._access_token,
                **json,
            }
            try:
                return await self._async_raw_request(
                    "post",
                    DEVICE_BASE_URL,
                    path,
                    json=retry_body,
                )
            except NinebotApiAuthError as err:
                raise NinebotApiAuthError(str(err) or "Authentication failed") from err

    async def _async_raw_request(
        self,
        method: str,
        base_url: str,
        path: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        url = f"{base_url}{path}"

        try:
            response = await self._session.request(
                method,
                url,
                headers={
                    "clientId": CLIENT_ID,
                    "Content-Type": "application/json",
                },
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
            raise NinebotApiConnectionError("Unexpected response payload")

        if "resultCode" in payload:
            if payload.get("resultCode") == "90000":
                return payload
            desc = str(payload.get("resultDesc", ""))
            raise NinebotApiAuthError(desc or "Authentication failed")

        if payload.get("code") == 1:
            return payload

        desc = str(payload.get("desc", ""))
        if self._is_auth_error(desc):
            raise NinebotApiAuthError(desc or "Authentication failed")
        raise NinebotApiConnectionError(desc or "Request failed")

    async def _async_set_tokens(self, tokens: NinebotTokens) -> None:
        previous_tokens = self.tokens
        self._access_token = tokens.access_token
        self._refresh_token = tokens.refresh_token
        self._access_token_validity = tokens.access_token_validity

        if self._token_update_callback is not None and tokens != previous_tokens:
            await self._token_update_callback(tokens)

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
                "login",
                "expired",
                "invalid",
                "鉴权",
                "认证",
                "授权",
                "令牌",
                "登录",
                "失效",
                "过期",
            )
        )
