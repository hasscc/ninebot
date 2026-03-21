from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlparse

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NinebotConfigEntry, LOGGER
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
        self._key = self.entity_description.key
        self._attr_unique_id = f"{sn}_{self._key}"
        self._attr_translation_key = self.entity_description.translation_key or self._key
        self.entity_id = self.suggested_entity_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, sn)},
            manufacturer="Ninebot",
            model=self.device_model,
            name=self.device_name,
        )
        self._attr_extra_state_attributes = {}

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._on_updated()
        if fun := getattr(self.entity_description, "attrs_fn", None):
            self._attr_extra_state_attributes = fun(self)
        LOGGER.debug("Updating state: %s %s", self._key, self.state)
        super()._handle_coordinator_update()

    @callback
    def _on_updated(self) -> None:
        """Handle updated data."""

    @property
    def available(self) -> bool:
        return super().available and self.device_payload is not None

    @property
    def device_name(self) -> str:
        info = self.device_profile
        if name := info.get("deviceName"):
            return str(name)
        return self._sn

    @property
    def device_model(self) -> str:
        info = self.device_profile
        image_url = info.get("img")
        if isinstance(image_url, str) and (parsed_model := _model_from_image_url(image_url)):
            return parsed_model
        return self._sn

    @property
    def device_payload(self) -> dict[str, Any] | None:
        devices = self.coordinator.data.get("devices", {})
        payload = devices.get(self._sn)
        return payload if isinstance(payload, dict) else None

    @property
    def device_profile(self) -> dict[str, Any]:
        payload = self.device_payload or {}
        info = payload.get("info")
        return info if isinstance(info, dict) else {}

    @property
    def device_dynamic(self) -> dict[str, Any]:
        payload = self.device_payload or {}
        dynamic = payload.get("dynamic")
        return dynamic if isinstance(dynamic, dict) else {}

    @property
    def suggested_entity_id(self) -> str:
        """Return input for object id."""
        return f"{DOMAIN}.{self._sn}_{self.entity_description.key}".lower()


def _model_from_image_url(image_url: str) -> str | None:
    parsed = urlparse(image_url)
    filename = PurePosixPath(parsed.path).stem
    if not filename:
        return None

    model = filename.replace("_", " ").strip()
    return model or None
