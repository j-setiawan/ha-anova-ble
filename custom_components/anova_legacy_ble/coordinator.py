"""Data update coordinator for Anova Legacy BLE."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, UPDATE_INTERVAL
from .device import AnovaError, AnovaLegacyDevice, AnovaState

_LOGGER = logging.getLogger(__name__)


class AnovaCoordinator(DataUpdateCoordinator[AnovaState]):
    """Coordinate polling and writes for one Anova cooker."""

    def __init__(self, hass: HomeAssistant, device: AnovaLegacyDevice) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{device.address}",
            update_interval=UPDATE_INTERVAL,
        )
        self.device = device

    async def _async_update_data(self) -> AnovaState:
        try:
            return await self.device.async_read_state()
        except AnovaError as err:
            raise UpdateFailed(str(err)) from err

    async def async_write(self, operation) -> None:
        """Run a control operation and refresh state."""
        try:
            await operation()
        except AnovaError as err:
            raise UpdateFailed(str(err)) from err
        await self.async_request_refresh()
