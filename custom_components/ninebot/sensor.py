from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfLength
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NinebotConfigEntry
from .entity import NinebotEntity


def _location_description(entity: NinebotEntity) -> str | None:
    location_info = entity.device_dynamic.get("locationInfo")
    if not isinstance(location_info, dict):
        return None

    location_desc = location_info.get("locationDesc")
    return str(location_desc) if location_desc is not None else None


@dataclass(frozen=True, kw_only=True)
class NinebotSensorEntityDescription(SensorEntityDescription):
    value_fn: Callable
    attrs_fn: Callable | None = None


SENSOR_DESCRIPTIONS: tuple[NinebotSensorEntityDescription, ...] = (
    NinebotSensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda entity: entity.device_dynamic.get("dumpEnergy"),
    ),
    NinebotSensorEntityDescription(
        key="endurance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda entity: entity.device_dynamic.get("estimateMileage"),
    ),
    NinebotSensorEntityDescription(
        key="location",
        icon="mdi:map-marker",
        value_fn=_location_description,
        attrs_fn=lambda entity: {
            "entity_picture": img,
        } if (img := entity.device_profile.get("img")) else {},
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
        new_entities: list[NinebotSensor] = []
        devices = coordinator.data.get("devices", {})
        for sn in devices:
            if sn in known_sns:
                continue
            known_sns.add(sn)
            new_entities.extend(
                NinebotSensor(coordinator, entry, sn, description)
                for description in SENSOR_DESCRIPTIONS
            )

        if new_entities:
            async_add_entities(new_entities)

    async_add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(async_add_new_entities))


class NinebotSensor(NinebotEntity, SensorEntity):
    """Representation of a Ninebot sensor."""

    entity_description: NinebotSensorEntityDescription

    def __init__(
        self,
        coordinator,
        config_entry: NinebotConfigEntry,
        sn: str,
        description: NinebotSensorEntityDescription,
    ) -> None:
        self.entity_description = description
        super().__init__(coordinator, config_entry, sn)

    @callback
    def _on_updated(self) -> None:
        """Handle updated data."""
        self._attr_native_value = self.entity_description.value_fn(self)
