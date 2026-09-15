"""Timer/alarm buttons for Anova Legacy BLE."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
    entities = [
        AnovaCommandButton(coordinator, "start_timer", "Start timer", "mdi:timer-play-outline", coordinator.device.async_start_timer),
        AnovaCommandButton(coordinator, "stop_timer", "Stop timer", "mdi:timer-stop-outline", coordinator.device.async_stop_timer),
    ]
    if coordinator.data.is_wifi_model:
        entities.append(
            AnovaCommandButton(coordinator, "clear_alarm", "Clear alarm", "mdi:alarm-light-off-outline", coordinator.device.async_clear_alarm)
        )
    async_add_entities(entities)


class AnovaCommandButton(AnovaEntity, ButtonEntity):
    def __init__(self, coordinator, key: str, name: str, icon: str, action) -> None:
        super().__init__(coordinator, key)
        self._attr_name = name
        self._attr_icon = icon
        self._action = action

    async def async_press(self) -> None:
        await self.coordinator.async_write(self._action)
