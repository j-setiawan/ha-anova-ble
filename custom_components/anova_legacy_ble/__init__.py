"""Anova Legacy BLE integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from .const import CONF_DEVICE_NAME, DOMAIN, PLATFORMS
from .coordinator import AnovaCoordinator
from .device import AnovaLegacyDevice


AnovaConfigEntry = ConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: AnovaConfigEntry) -> bool:
    """Set up Anova Legacy BLE from a config entry."""
    address = entry.data[CONF_ADDRESS]
    name = entry.data.get(CONF_DEVICE_NAME, "Anova Precision Cooker")

    device = AnovaLegacyDevice(hass, address, name)
    coordinator = AnovaCoordinator(hass, device)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AnovaConfigEntry) -> bool:
    """Unload an Anova config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
