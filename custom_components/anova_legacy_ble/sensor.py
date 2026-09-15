"""Sensors for Anova Legacy BLE."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
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
        [
            AnovaWaterTemperatureSensor(coordinator),
            AnovaTargetTemperatureSensor(coordinator),
            AnovaTimerSensor(coordinator),
            AnovaCookerIdSensor(coordinator),
        ]
    )


class _TemperatureSensor(AnovaEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    @property
    def native_unit_of_measurement(self) -> str:
        return (
            UnitOfTemperature.FAHRENHEIT
            if self.coordinator.data.unit == "F"
            else UnitOfTemperature.CELSIUS
        )


class AnovaWaterTemperatureSensor(_TemperatureSensor):
    _attr_name = "Water temperature"
    _attr_icon = "mdi:thermometer-water"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "water_temperature")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.current_temperature


class AnovaTargetTemperatureSensor(_TemperatureSensor):
    _attr_name = "Target temperature"
    _attr_icon = "mdi:thermometer-check"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "target_temperature_sensor")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.target_temperature


class AnovaTimerSensor(AnovaEntity, SensorEntity):
    _attr_name = "Timer"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:timer-outline"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "timer_sensor")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.timer_minutes


class AnovaCookerIdSensor(AnovaEntity, SensorEntity):
    _attr_name = "Cooker ID"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:identifier"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "cooker_id")

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data.cooker_id
