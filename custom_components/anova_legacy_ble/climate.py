"""Climate entity for Anova Legacy BLE."""

from __future__ import annotations

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AnovaConfigEntry
from .entity import AnovaEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AnovaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([AnovaClimate(entry.runtime_data)])


class AnovaClimate(AnovaEntity, ClimateEntity):
    _attr_name = "Cooker"
    _attr_icon = "mdi:pot-steam"
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_target_temperature_step = 0.1

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "climate")

    @property
    def temperature_unit(self) -> str:
        return (
            UnitOfTemperature.FAHRENHEIT
            if self.coordinator.data.unit == "F"
            else UnitOfTemperature.CELSIUS
        )

    @property
    def current_temperature(self) -> float | None:
        return self.coordinator.data.current_temperature

    @property
    def target_temperature(self) -> float | None:
        return self.coordinator.data.target_temperature

    @property
    def hvac_mode(self) -> HVACMode:
        return HVACMode.HEAT if self.coordinator.data.running else HVACMode.OFF

    @property
    def min_temp(self) -> float:
        return 32.0 if self.coordinator.data.unit == "F" else 0.0

    @property
    def max_temp(self) -> float:
        return 212.0 if self.coordinator.data.unit == "F" else 100.0

    async def async_set_temperature(self, **kwargs) -> None:
        value = kwargs.get(ATTR_TEMPERATURE)
        if value is None:
            return
        await self.coordinator.async_write(
            lambda: self.coordinator.device.async_set_temperature(float(value))
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.HEAT:
            await self.coordinator.async_write(self.coordinator.device.async_start)
        else:
            await self.coordinator.async_write(self.coordinator.device.async_stop)
