from __future__ import annotations

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later

from . import NinebotConfigEntry
from .coordinator import NinebotDataUpdateCoordinator
from .entity import NinebotEntity


LOCK_DESCRIPTION = EntityDescription(key="lock")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    known_sns: set[str] = set()

    @callback
    def async_add_new_entities() -> None:
        new_entities: list[NinebotLock] = []
        devices = coordinator.data.get("devices", {})
        for sn in devices:
            if sn in known_sns:
                continue
            known_sns.add(sn)
            new_entities.append(NinebotLock(coordinator, entry, sn))

        if new_entities:
            async_add_entities(new_entities)

    async_add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(async_add_new_entities))


class NinebotLock(NinebotEntity, LockEntity):
    entity_description = LOCK_DESCRIPTION

    def __init__(
        self,
        coordinator: NinebotDataUpdateCoordinator,
        config_entry: NinebotConfigEntry,
        sn: str,
    ) -> None:
        super().__init__(coordinator, config_entry, sn)
        self._cancel_delayed_refresh = None
        self._delayed_refreshes_remaining = 0

    @property
    def is_locked(self) -> bool | None:
        value = self.device_state.get("lock")
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value == 1
        return None

    async def async_lock(self, **kwargs) -> None:
        self._cancel_delayed_status_refresh()
        await self.coordinator._client.async_lock(self._sn)
        await self.coordinator.async_request_device_status_refresh(self._sn)

    async def async_unlock(self, **kwargs) -> None:
        await self.coordinator._client.async_unlock(self._sn)
        await self.coordinator.async_request_device_status_refresh(self._sn)
        self._schedule_delayed_refresh()

    def _cancel_delayed_status_refresh(self) -> None:
        if self._cancel_delayed_refresh is not None:
            self._cancel_delayed_refresh()
            self._cancel_delayed_refresh = None
        self._delayed_refreshes_remaining = 0

    def _schedule_delayed_refresh(self) -> None:
        self._cancel_delayed_status_refresh()
        self._delayed_refreshes_remaining = 4
        self._cancel_delayed_refresh = async_call_later(
            self.hass,
            4,
            self._on_delayed_refresh,
        )

    async def _on_delayed_refresh(self, _now) -> None:
        await self.coordinator.async_request_device_status_refresh(self._sn)
        self._delayed_refreshes_remaining -= 1
        if self._delayed_refreshes_remaining > 0:
            self._cancel_delayed_refresh = async_call_later(
                self.hass,
                4,
                self._on_delayed_refresh,
            )
        else:
            self._cancel_delayed_refresh = None

    def async_will_remove_from_hass(self) -> None:
        self._cancel_delayed_status_refresh()
        super().async_will_remove_from_hass()
