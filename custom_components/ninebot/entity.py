from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NinebotConfigEntry
from .const import DOMAIN
from .coordinator import NinebotDataUpdateCoordinator


class NinebotEntity(CoordinatorEntity[NinebotDataUpdateCoordinator]):
    """Base entity for Ninebot devices."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NinebotDataUpdateCoordinator,
        config_entry: NinebotConfigEntry,
        sn: str,
    ) -> None:
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._sn = sn
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, sn)},
            manufacturer="Ninebot",
            model="Vehicle",
            name=self.device_name,
        )

    @property
    def available(self) -> bool:
        return super().available and self.device_payload is not None

    @property
    def device_name(self) -> str:
        info = self.device_info_payload
        if name := info.get("deviceName"):
            return str(name)
        return self._sn

    @property
    def device_payload(self) -> dict[str, Any] | None:
        devices = self.coordinator.data.get("devices", {})
        payload = devices.get(self._sn)
        return payload if isinstance(payload, dict) else None

    @property
    def device_info_payload(self) -> dict[str, Any]:
        payload = self.device_payload or {}
        info = payload.get("info")
        return info if isinstance(info, dict) else {}

    @property
    def device_dynamic_payload(self) -> dict[str, Any]:
        payload = self.device_payload or {}
        dynamic = payload.get("dynamic")
        return dynamic if isinstance(dynamic, dict) else {}
