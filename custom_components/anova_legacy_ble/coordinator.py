"""Data update coordinator for Anova Legacy BLE."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, FAILURE_GRACE_POLLS, UPDATE_INTERVAL
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
        self._consecutive_failures = 0

    async def _async_update_data(self) -> AnovaState:
        try:
            state = await self.device.async_read_state()
        except AnovaError as err:
            self._consecutive_failures += 1

            # Transient BLE connection failures are common. If we already have
            # a trustworthy state, keep it briefly rather than making every
            # entity unavailable after a single failed poll.
            if (
                self.data is not None
                and self._consecutive_failures <= FAILURE_GRACE_POLLS
            ):
                _LOGGER.warning(
                    "Anova poll failed (%d/%d grace polls); retaining last known "
                    "state: %s",
                    self._consecutive_failures,
                    FAILURE_GRACE_POLLS,
                    err,
                )
                return self.data

            raise UpdateFailed(str(err)) from err

        self._consecutive_failures = 0
        return state

    async def async_write(self, operation) -> None:
        """Run a control operation and refresh state."""
        try:
            await operation()
        except AnovaError as err:
            raise UpdateFailed(str(err)) from err
        await self.async_request_refresh()
