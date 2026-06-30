from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NinebotConfigEntry
from .coordinator import NinebotDataUpdateCoordinator
from .entity import NinebotEntity


@dataclass(frozen=True, kw_only=True)
class NinebotButtonEntityDescription(ButtonEntityDescription):
    press_fn: Callable[[NinebotDataUpdateCoordinator, str], Awaitable[None]]


async def _async_press_bell(coordinator: NinebotDataUpdateCoordinator, sn: str) -> None:
    await coordinator._client.async_bell(sn)


async def _async_press_bucket(coordinator: NinebotDataUpdateCoordinator, sn: str) -> None:
    await coordinator._client.async_open_bucket(sn)


BUTTON_DESCRIPTIONS: tuple[NinebotButtonEntityDescription, ...] = (
    NinebotButtonEntityDescription(
        key="bell",
        icon="mdi:bell",
        press_fn=_async_press_bell,
    ),
    NinebotButtonEntityDescription(
        key="bucket",
        icon="mdi:car-seat",
        press_fn=_async_press_bucket,
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
        new_entities: list[NinebotButton] = []
        devices = coordinator.data.get("devices", {})
        for sn in devices:
            if sn in known_sns:
                continue
            known_sns.add(sn)
            new_entities.extend(
                NinebotButton(coordinator, entry, sn, description)
                for description in BUTTON_DESCRIPTIONS
            )

        if new_entities:
            async_add_entities(new_entities)

    async_add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(async_add_new_entities))


class NinebotButton(NinebotEntity, ButtonEntity):
    entity_description: NinebotButtonEntityDescription

    def __init__(
        self,
        coordinator: NinebotDataUpdateCoordinator,
        config_entry: NinebotConfigEntry,
        sn: str,
        description: NinebotButtonEntityDescription,
    ) -> None:
        self.entity_description = description
        super().__init__(coordinator, config_entry, sn)

    async def async_press(self) -> None:
        await self.entity_description.press_fn(self.coordinator, self._sn)
        await self.coordinator.async_request_refresh()
