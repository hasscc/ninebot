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
    value_fn: Callable[[dict[str, Any]], bool | None]


BINARY_SENSOR_DESCRIPTIONS: tuple[NinebotBinarySensorEntityDescription, ...] = (
    NinebotBinarySensorEntityDescription(
        key="charging",
        translation_key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=lambda dynamic: _coerce_bool(dynamic.get("chargingState"), on_value=1),
    ),
    NinebotBinarySensorEntityDescription(
        key="power",
        translation_key="power",
        device_class=BinarySensorDeviceClass.POWER,
        value_fn=lambda dynamic: _coerce_bool(dynamic.get("powerStatus"), on_value=1),
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
        super().__init__(coordinator, config_entry, sn)
        self.entity_description = description
        self._attr_unique_id = f"{sn}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.device_dynamic_payload)

    @property
    def name(self) -> str | None:
        return self.entity_description.name

    @property
    def suggested_object_id(self) -> str:
        return f"{self.device_name}_{self.entity_description.key}"


def _coerce_bool(value: Any, *, on_value: int) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value == on_value
    return None
