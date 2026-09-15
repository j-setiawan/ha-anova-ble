"""Config flow for Anova Legacy BLE."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import CONF_DEVICE_NAME, DOMAIN, SERVICE_UUID

_MANUAL = "__manual__"


def _looks_like_anova(info: BluetoothServiceInfoBleak) -> bool:
    name = (info.name or "").lower()
    service_uuids = {uuid.lower() for uuid in info.service_uuids}
    return "anova" in name or SERVICE_UUID.lower() in service_uuids


class AnovaLegacyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle Anova Legacy BLE setup."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovery_info: BluetoothServiceInfoBleak | None = None

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle automatic Bluetooth discovery."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": discovery_info.name or "Anova Precision Cooker"
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovered cooker."""
        assert self._discovery_info is not None
        if user_input is not None:
            return self.async_create_entry(
                title=self._discovery_info.name or "Anova Precision Cooker",
                data={
                    CONF_ADDRESS: self._discovery_info.address,
                    CONF_DEVICE_NAME: self._discovery_info.name or "Anova Precision Cooker",
                },
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={
                "name": self._discovery_info.name or "Anova Precision Cooker",
                "address": self._discovery_info.address,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user choose a discovered cooker or enter an address."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            if address == _MANUAL:
                return await self.async_step_manual()
            return await self._create_for_address(address)

        current_ids = self._async_current_ids(include_ignore=False)
        choices: dict[str, str] = {}
        for info in async_discovered_service_info(self.hass, True):
            if info.address in current_ids or not _looks_like_anova(info):
                continue
            choices[info.address] = f"{info.name or 'Anova'} ({info.address})"

        choices[_MANUAL] = "Enter Bluetooth address manually"
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(choices)}),
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Accept a Bluetooth address manually."""
        if user_input is not None:
            address = str(user_input[CONF_ADDRESS]).strip().upper().replace("-", ":")
            if not address:
                return self.async_show_form(
                    step_id="manual",
                    data_schema=vol.Schema({vol.Required(CONF_ADDRESS): str}),
                    errors={CONF_ADDRESS: "invalid_address"},
                )
            return await self._create_for_address(address)

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): str}),
        )

    async def _create_for_address(self, address: str) -> ConfigFlowResult:
        await self.async_set_unique_id(address, raise_on_progress=False)
        self._abort_if_unique_id_configured()

        name = "Anova Precision Cooker"
        for info in async_discovered_service_info(self.hass, True):
            if info.address == address:
                name = info.name or name
                break

        return self.async_create_entry(
            title=name,
            data={CONF_ADDRESS: address, CONF_DEVICE_NAME: name},
        )
