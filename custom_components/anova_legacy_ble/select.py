"""Temperature unit selector for Anova Legacy BLE."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AnovaConfigEntry
from .entity import AnovaEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AnovaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([AnovaUnitSelect(entry.runtime_data)])


class AnovaUnitSelect(AnovaEntity, SelectEntity):
    _attr_name = "Temperature unit"
    _attr_options = ["Celsius", "Fahrenheit"]
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:temperature-celsius"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "temperature_unit")

    @property
    def current_option(self) -> str:
        return "Fahrenheit" if self.coordinator.data.unit == "F" else "Celsius"

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_write(
            lambda: self.coordinator.device.async_set_unit(option)
        )
