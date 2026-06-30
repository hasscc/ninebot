from __future__ import annotations

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NinebotConfigEntry
from .entity import NinebotEntity


TRACKER_DESCRIPTION = EntityDescription(key="location")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    known_sns: set[str] = set()

    @callback
    def async_add_new_entities() -> None:
        new_entities: list[NinebotDeviceTracker] = []
        devices = coordinator.data.get("devices", {})
        for sn in devices:
            if sn in known_sns:
                continue
            known_sns.add(sn)
            new_entities.append(NinebotDeviceTracker(coordinator, entry, sn))

        if new_entities:
            async_add_entities(new_entities)

    async_add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(async_add_new_entities))


class NinebotDeviceTracker(NinebotEntity, TrackerEntity):
    """Representation of a Ninebot GPS tracker."""

    entity_description = TRACKER_DESCRIPTION
    _attr_source_type = SourceType.GPS

    def __init__(
        self,
        coordinator,
        config_entry: NinebotConfigEntry,
        sn: str,
    ) -> None:
        super().__init__(coordinator, config_entry, sn)

    @property
    def entity_picture(self) -> str | None:
        picture = self.device_profile.get("image_url")
        return picture if isinstance(picture, str) and picture else None

    @callback
    def _on_updated(self) -> None:
        """Handle updated data."""
        self._attr_latitude = None
        self._attr_longitude = None
        self._attr_location_accuracy = None

        location = self.device_state.get("location")
        if not isinstance(location, dict):
            return

        latitude = location.get("latitude")
        longitude = location.get("longitude")
        if isinstance(latitude, int | float) and isinstance(longitude, int | float):
            self._attr_latitude = latitude
            self._attr_longitude = longitude

        accuracy = location.get("accuracy")
        if isinstance(accuracy, int | float):
            self._attr_location_accuracy = accuracy

    @property
    def available(self) -> bool:
        return super().available and self.latitude is not None and self.longitude is not None
