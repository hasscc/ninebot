from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import json
import logging
from pathlib import Path
import sys
from typing import Any

from .const import API_TIMEOUT, NINECLI_MODULE

LOGGER = logging.getLogger(__package__)


class NinebotApiError(Exception):
    """Base exception for Ninebot API errors."""


class NinebotApiAuthError(NinebotApiError):
    """Raised when authentication fails."""


class NinebotApiConnectionError(NinebotApiError):
    """Raised when the API request fails."""


class NinebotCliClient:
    """Async subprocess client for the ninecli package."""

    def __init__(self, config_dir: Path) -> None:
        self._config_dir = config_dir
        self._command_lock = asyncio.Lock()
        self._cycle_lock = asyncio.Lock()

    async def async_login(self, username: str, password: str) -> dict[str, Any]:
        payload = await self._async_run_json_command(
            ["login", "-u", username, "-p", password, "--json"]
        )
        return payload if isinstance(payload, dict) else {}

    async def async_get_device_list(self) -> list[dict[str, Any]]:
        payload = await self._async_run_json_command(["vehicles", "--json"])
        vehicles = payload if isinstance(payload, list) else payload.get("data") if isinstance(payload, dict) else []
        if not isinstance(vehicles, list):
            return []
        return [
            normalized
            for vehicle in vehicles
            if isinstance(vehicle, dict)
            if (normalized := self._normalize_vehicle(vehicle)) is not None
        ]

    async def async_get_device_state(self, sn: str, *, month: str | None = None) -> dict[str, Any]:
        month = month or datetime.now(UTC).strftime("%Y%m")
        status = await self._async_run_json_command(["status", sn, "--json"])
        if not isinstance(status, dict):
            status = {}

        state = self._normalize_status(status)
        try:
            travel = await self._async_run_json_command(
                ["travel", sn, "--month", month, "--json"]
            )
        except NinebotApiConnectionError as err:
            LOGGER.debug("Failed to fetch Ninebot travel data for %s: %s", sn, err)
        else:
            if isinstance(travel, dict):
                state.update(self._normalize_travel(travel))
        return state

    async def async_get_all_device_payloads(self) -> list[dict[str, Any]]:
        async with self._cycle_lock:
            devices = await self.async_get_device_list()
            results: list[dict[str, Any]] = []
            for device in devices:
                sn = device.get("sn")
                if not isinstance(sn, str) or not sn:
                    continue
                state = await self.async_get_device_state(sn)
                results.append({
                    "sn": sn,
                    "info": device,
                    "state": state,
                })
            return results

    async def _async_run_json_command(self, args: list[str]) -> Any:
        command = [
            sys.executable,
            "-m",
            NINECLI_MODULE,
            "--config",
            str(self._config_dir),
            *args,
        ]
        async with self._command_lock:
            try:
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            except OSError as err:
                raise NinebotApiConnectionError(str(err)) from err

            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=API_TIMEOUT)
            except TimeoutError as err:
                process.kill()
                await process.communicate()
                raise NinebotApiConnectionError("ninecli command timed out") from err

        stdout_text = stdout.decode(errors="replace").strip()
        stderr_text = stderr.decode(errors="replace").strip()

        if process.returncode != 0:
            raise self._exception_from_cli_failure(process.returncode, stdout_text, stderr_text)

        try:
            return json.loads(stdout_text or "{}")
        except ValueError as err:
            raise NinebotApiConnectionError("Invalid JSON from ninecli") from err

    def _exception_from_cli_failure(
        self,
        returncode: int,
        stdout: str,
        stderr: str,
    ) -> NinebotApiError:
        message = stderr or stdout or f"ninecli exited with {returncode}"
        normalized = message.lower()
        if any(
            marker in normalized
            for marker in (
                "login first",
                "business_login auto-fallback failed",
                "refresh access_token",
                "invalid username or password",
                "server code=",
                "invalid_auth",
            )
        ):
            return NinebotApiAuthError(message)
        return NinebotApiConnectionError(message)

    @staticmethod
    def _normalize_vehicle(vehicle: dict[str, Any]) -> dict[str, Any] | None:
        sn = vehicle.get("wnumber") or vehicle.get("sn")
        if not isinstance(sn, str) or not sn:
            return None
        model = vehicle.get("vehicle_name_en") or vehicle.get("vehicle_name") or sn
        if vehicle_type := vehicle.get("vehicle_type"):
            model = f"{model} ({vehicle_type})"
        image_url = vehicle.get("v6_light_img_url") or vehicle.get("img_url")
        return {
            "sn": sn,
            "name": vehicle.get("device_name") or vehicle.get("ble_name") or sn,
            "model": model,
            "image_url": image_url if isinstance(image_url, str) and image_url else None,
            "raw": vehicle,
        }

    @staticmethod
    def _normalize_status(status: dict[str, Any]) -> dict[str, Any]:
        state: dict[str, Any] = {"raw": status}

        if "dump_energy" in status:
            state["battery"] = _coerce_int(status.get("dump_energy"))
        if "precise_estimate_mileage" in status:
            state["endurance"] = _coerce_float(status.get("precise_estimate_mileage"))
        if "charging" in status:
            state["charging"] = status.get("charging")
        if "pwr" in status:
            state["power"] = status.get("pwr")

        loc = status.get("loc")
        if isinstance(loc, dict):
            locked = loc.get("lock")
            lat = _coerce_float(loc.get("lat"))
            lon = _coerce_float(loc.get("lon"))
            accuracy = _coerce_float(loc.get("acc"))
            if locked is not None:
                state["lock"] = locked
            if lat is not None and lon is not None:
                location = {"latitude": lat, "longitude": lon}
                if accuracy is not None:
                    location["accuracy"] = accuracy
                state["location"] = location
        elif "lock_status" in status:
            state["lock"] = status.get("lock_status")

        return state

    @staticmethod
    def _normalize_travel(travel: dict[str, Any]) -> dict[str, Any]:
        rides = travel.get("list")
        if not isinstance(rides, list):
            rides = []

        month_mileage = sum(
            mileage
            for ride in rides
            if isinstance(ride, dict)
            if (mileage := _coerce_float(ride.get("mileages"))) is not None
        )
        month_energy = sum(
            energy
            for ride in rides
            if isinstance(ride, dict)
            if (energy := _coerce_float(ride.get("used_electricity"))) is not None
        )
        last_ride = rides[0] if rides and isinstance(rides[0], dict) else None
        last_mileage = (
            _coerce_float(last_ride.get("mileages"))
            if last_ride is not None
            else None
        )
        last_energy = (
            _coerce_float(last_ride.get("used_electricity"))
            if last_ride is not None
            else None
        )
        return {
            "month_mileage": month_mileage,
            "last_mileage": last_mileage,
            "month_energy": month_energy,
            "last_energy": last_energy,
            "last_ride": last_ride,
        }


def _coerce_float(value: Any) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None
