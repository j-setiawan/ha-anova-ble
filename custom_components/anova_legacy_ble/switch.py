"""Running switch for Anova Legacy BLE."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AnovaConfigEntry
from .entity import AnovaEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AnovaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([AnovaRunningSwitch(entry.runtime_data)])


class AnovaRunningSwitch(AnovaEntity, SwitchEntity):
    _attr_name = "Cooking"
    _attr_icon = "mdi:pot-steam"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "running")

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.running

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_write(self.coordinator.device.async_start)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_write(self.coordinator.device.async_stop)
