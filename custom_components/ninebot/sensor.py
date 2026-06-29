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
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfLength
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NinebotConfigEntry
from .entity import NinebotEntity


def _last_ride_attributes(entity: NinebotEntity) -> dict[str, Any]:
    last_ride = entity.device_state.get("last_ride")
    return last_ride if isinstance(last_ride, dict) else {}


def _month_energy_attributes(entity: NinebotEntity) -> dict[str, Any]:
    used_electricity = entity.device_state.get("month_used_electricity")
    return {"used_electricity": used_electricity} if used_electricity is not None else {}


def _last_energy_attributes(entity: NinebotEntity) -> dict[str, Any]:
    used_electricity = entity.device_state.get("last_used_electricity")
    return {"used_electricity": used_electricity} if used_electricity is not None else {}


def _address_value(entity: NinebotEntity) -> str | None:
    address = entity.device_state.get("address")
    if not isinstance(address, dict):
        return None

    formatted_address = address.get("formatted_address")
    return formatted_address if isinstance(formatted_address, str) else None


def _address_attributes(entity: NinebotEntity) -> dict[str, Any]:
    address = entity.device_state.get("address")
    if not isinstance(address, dict):
        return {}

    return {
        key: value
        for key in (
            "provider",
            "source_coordinate_system",
            "coordinate_system",
            "latitude",
            "longitude",
            "amap_latitude",
            "amap_longitude",
            "province",
            "city",
            "district",
            "township",
            "adcode",
            "error",
        )
        if (value := address.get(key)) is not None
    }


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
        value_fn=lambda entity: entity.device_state.get("battery"),
    ),
    NinebotSensorEntityDescription(
        key="endurance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda entity: entity.device_state.get("endurance"),
    ),
    NinebotSensorEntityDescription(
        key="month_mileage",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=lambda entity: entity.device_state.get("month_mileage"),
    ),
    NinebotSensorEntityDescription(
        key="last_mileage",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda entity: entity.device_state.get("last_mileage"),
        attrs_fn=_last_ride_attributes,
    ),
    NinebotSensorEntityDescription(
        key="month_energy",
        device_class=SensorDeviceClass.ENERGY,
        icon="mdi:flash",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=lambda entity: entity.device_state.get("month_energy"),
        attrs_fn=_month_energy_attributes,
    ),
    NinebotSensorEntityDescription(
        key="last_energy",
        device_class=SensorDeviceClass.ENERGY,
        icon="mdi:flash",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda entity: entity.device_state.get("last_energy"),
        attrs_fn=_last_energy_attributes,
    ),
    NinebotSensorEntityDescription(
        key="address",
        icon="mdi:map-marker",
        value_fn=_address_value,
        attrs_fn=_address_attributes,
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
