"""Number controls for Anova Legacy BLE."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AnovaConfigEntry
from .entity import AnovaEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AnovaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [AnovaTargetTemperatureNumber(coordinator), AnovaTimerNumber(coordinator)]
    )


class AnovaTargetTemperatureNumber(AnovaEntity, NumberEntity):
    _attr_name = "Target temperature setting"
    _attr_icon = "mdi:thermometer-check"
    _attr_native_step = 0.1

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "target_temperature_number")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.target_temperature

    @property
    def native_unit_of_measurement(self) -> str:
        return (
            UnitOfTemperature.FAHRENHEIT
            if self.coordinator.data.unit == "F"
            else UnitOfTemperature.CELSIUS
        )

    @property
    def native_min_value(self) -> float:
        return 32.0 if self.coordinator.data.unit == "F" else 0.0

    @property
    def native_max_value(self) -> float:
        return 212.0 if self.coordinator.data.unit == "F" else 100.0

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_write(
            lambda: self.coordinator.device.async_set_temperature(value)
        )


class AnovaTimerNumber(AnovaEntity, NumberEntity):
    _attr_name = "Timer setting"
    _attr_icon = "mdi:timer-cog-outline"
    _attr_native_min_value = 0
    _attr_native_max_value = 999
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "timer_number")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.timer_minutes

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_write(
            lambda: self.coordinator.device.async_set_timer(value)
        )
