"""Shared entity helpers for Anova Legacy BLE."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AnovaCoordinator


class AnovaEntity(CoordinatorEntity[AnovaCoordinator]):
    """Base Anova entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AnovaCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.device.address}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        state = self.coordinator.data
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.device.address)},
            name=self.coordinator.device.name or "Anova Precision Cooker",
            manufacturer="Anova Culinary",
            model=state.model if state else "Original Precision Cooker",
        )
