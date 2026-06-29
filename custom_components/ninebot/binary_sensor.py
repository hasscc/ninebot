from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NinebotConfigEntry
from .entity import NinebotEntity


@dataclass(frozen=True, kw_only=True)
class NinebotBinarySensorEntityDescription(BinarySensorEntityDescription):
    value_fn: Callable


BINARY_SENSOR_DESCRIPTIONS: tuple[NinebotBinarySensorEntityDescription, ...] = (
    NinebotBinarySensorEntityDescription(
        key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda entity: _coerce_bool(entity.device_state.get("charging"), on_value=1),
    ),
    NinebotBinarySensorEntityDescription(
        key="power",
        device_class=BinarySensorDeviceClass.POWER,
        value_fn=lambda entity: _coerce_bool(entity.device_state.get("power"), on_value=1),
    ),
    NinebotBinarySensorEntityDescription(
        key="lock",
        device_class=BinarySensorDeviceClass.LOCK,
        value_fn=lambda entity: _coerce_bool(entity.device_state.get("lock"), on_value=0),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    known_sns: set[str] = set()

    @callback
    def async_add_new_entities() -> None:
        new_entities: list[NinebotBinarySensor] = []
        devices = coordinator.data.get("devices", {})
        for sn in devices:
            if sn in known_sns:
                continue
            known_sns.add(sn)
            new_entities.extend(
                NinebotBinarySensor(coordinator, entry, sn, description)
                for description in BINARY_SENSOR_DESCRIPTIONS
            )

        if new_entities:
            async_add_entities(new_entities)

    async_add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(async_add_new_entities))


class NinebotBinarySensor(NinebotEntity, BinarySensorEntity):
    """Representation of a Ninebot binary sensor."""

    entity_description: NinebotBinarySensorEntityDescription

    def __init__(
        self,
        coordinator,
        config_entry,
        sn: str,
        description: NinebotBinarySensorEntityDescription,
    ) -> None:
        self.entity_description = description
        super().__init__(coordinator, config_entry, sn)

    @callback
    def _on_updated(self) -> None:
        """Handle updated data."""
        self._attr_is_on = self.entity_description.value_fn(self)


def _coerce_bool(value: Any, *, on_value: int) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value == on_value
    return None
