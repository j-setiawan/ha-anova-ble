"""BLE protocol support for original Anova Precision Cookers."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import re
from typing import Any

from bleak import BleakClient
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from .const import (
    CHAR_UUID,
    CMD_CLEAR_ALARM,
    CMD_GET_ID,
    CMD_READ_TARGET_TEMP,
    CMD_READ_TEMP,
    CMD_READ_TIMER,
    CMD_READ_UNIT,
    CMD_START,
    CMD_START_TIMER,
    CMD_STATUS,
    CMD_STOP,
    CMD_STOP_TIMER,
)

_LOGGER = logging.getLogger(__name__)


class AnovaError(Exception):
    """Base exception for Anova BLE errors."""


class AnovaNotFoundError(AnovaError):
    """Raised when no connectable BLE path can reach the cooker."""


class AnovaProtocolError(AnovaError):
    """Raised when the cooker returns unusable data."""


@dataclass(slots=True)
class AnovaState:
    """Current cooker state."""

    current_temperature: float | None = None
    target_temperature: float | None = None
    timer_minutes: float | None = None
    running: bool | None = None
    unit: str = "C"
    cooker_id: str | None = None
    model: str = "Original Precision Cooker"
    is_wifi_model: bool = False


class _GattSession:
    """One connected BLE/GATT session."""

    def __init__(self, client: BleakClient) -> None:
        self.client = client
        self._response_buffer = bytearray()
        self._response_future: asyncio.Future[str] | None = None

    async def start(self) -> None:
        """Enable notifications."""
        await self.client.start_notify(CHAR_UUID, self._notification_handler)

    async def stop(self) -> None:
        """Disable notifications, if possible."""
        try:
            await self.client.stop_notify(CHAR_UUID)
        except Exception:  # noqa: BLE001 - best effort during disconnect
            pass

    def _notification_handler(self, _sender: Any, data: bytearray) -> None:
        """Accumulate the Anova's notification fragments."""
        if self._response_future is None or self._response_future.done():
            return

        self._response_buffer.extend(data)
        complete = not data or len(data) < 20 or data[-1] == 0
        if not complete:
            return

        response = self._response_buffer.decode("ascii", errors="ignore")
        response = response.rstrip("\x00\r\n ")
        self._response_buffer.clear()
        self._response_future.set_result(response)

    async def command(
        self,
        command: str,
        *,
        timeout: float = 5.0,
        response_required: bool = True,
    ) -> str | None:
        """Send an ASCII command terminated by carriage return."""
        self._response_buffer.clear()
        loop = asyncio.get_running_loop()
        self._response_future = loop.create_future()

        payload = (command + "\r").encode("ascii")
        _LOGGER.debug("Anova TX: %r", payload)
        await self.client.write_gatt_char(CHAR_UUID, payload, response=False)

        if not response_required:
            # Some firmware replies to write commands and some does not.  Do not
            # make control actions depend on receiving an acknowledgement.
            try:
                response = await asyncio.wait_for(self._response_future, 0.75)
                _LOGGER.debug("Anova RX after write: %r", response)
                return response
            except TimeoutError:
                return None
            finally:
                self._response_future = None

        try:
            response = await asyncio.wait_for(self._response_future, timeout)
            _LOGGER.debug("Anova RX: %r", response)
            return response
        except TimeoutError as err:
            raise AnovaProtocolError(f"Timeout waiting for response to {command!r}") from err
        finally:
            self._response_future = None


class AnovaLegacyDevice:
    """Local BLE client for original Anova Precision Cookers."""

    def __init__(self, hass: HomeAssistant, address: str, name: str = "Anova") -> None:
        self.hass = hass
        self.address = address
        self.name = name
        self._lock = asyncio.Lock()
        self._cooker_id: str | None = None
        self._model = "Original Precision Cooker"
        self._is_wifi_model = False

    async def _connect(self) -> BleakClient:
        """Resolve the best HA Bluetooth path and establish a connection."""
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            raise AnovaNotFoundError(
                f"No connectable Home Assistant Bluetooth adapter/proxy can currently reach {self.address}"
            )

        try:
            return await establish_connection(
                BleakClientWithServiceCache,
                ble_device,
                self.name or ble_device.name or self.address,
                max_attempts=3,
                timeout=15.0,
            )
        except Exception as err:  # noqa: BLE001 - normalize BLE backend exceptions
            raise AnovaError(f"Could not connect to Anova at {self.address}: {err}") from err

    async def _open_session(self) -> tuple[BleakClient, _GattSession]:
        client = await self._connect()
        session = _GattSession(client)
        try:
            await session.start()
        except Exception as err:  # noqa: BLE001
            try:
                await client.disconnect()
            except Exception:  # noqa: BLE001
                pass
            raise AnovaError(f"Connected, but could not enable Anova notifications: {err}") from err
        return client, session

    @staticmethod
    async def _close_session(client: BleakClient, session: _GattSession) -> None:
        await session.stop()
        try:
            await client.disconnect()
        except Exception:  # noqa: BLE001 - best effort
            pass

    async def async_read_state(self) -> AnovaState:
        """Read all useful state in one short BLE connection."""
        async with self._lock:
            client, session = await self._open_session()
            try:
                if self._cooker_id is None:
                    try:
                        cooker_id = await session.command(CMD_GET_ID, timeout=4.0)
                    except AnovaProtocolError:
                        cooker_id = None
                    if cooker_id:
                        self._cooker_id = cooker_id.strip()
                        if self._cooker_id.lower().startswith("anova f56-"):
                            self._is_wifi_model = True
                            self._model = "Original Precision Cooker 900W (BT/Wi-Fi)"
                        else:
                            self._model = "Original Precision Cooker 800W (Bluetooth)"

                async def safe(command: str) -> str | None:
                    try:
                        return await session.command(command)
                    except AnovaProtocolError as err:
                        _LOGGER.debug("Optional Anova read failed: %s", err)
                        return None

                unit_raw = await safe(CMD_READ_UNIT)
                status_raw = await safe(CMD_STATUS)
                target_raw = await safe(CMD_READ_TARGET_TEMP)
                temp_raw = await safe(CMD_READ_TEMP)
                timer_raw = await safe(CMD_READ_TIMER)

                if all(
                    value is None
                    for value in (unit_raw, status_raw, target_raw, temp_raw, timer_raw)
                ):
                    raise AnovaProtocolError(
                        "Connected to the cooker, but none of the known A2/A3 commands returned data"
                    )

                unit = self._parse_unit(unit_raw)
                return AnovaState(
                    current_temperature=self._parse_number(temp_raw),
                    target_temperature=self._parse_number(target_raw),
                    timer_minutes=self._parse_number(timer_raw),
                    running=self._parse_running(status_raw),
                    unit=unit,
                    cooker_id=self._cooker_id,
                    model=self._model,
                    is_wifi_model=self._is_wifi_model,
                )
            finally:
                await self._close_session(client, session)

    async def async_send(self, command: str) -> None:
        """Send a control command using a short-lived connection."""
        async with self._lock:
            client, session = await self._open_session()
            try:
                await session.command(command, response_required=False)
            finally:
                await self._close_session(client, session)

    async def async_set_temperature(self, value: float) -> None:
        await self.async_send(f"set temp {value:g}")

    async def async_set_timer(self, minutes: float) -> None:
        await self.async_send(f"set timer {minutes:g}")

    async def async_set_unit(self, unit: str) -> None:
        value = "f" if unit.upper().startswith("F") else "c"
        await self.async_send(f"set unit {value}")

    async def async_start(self) -> None:
        await self.async_send(CMD_START)

    async def async_stop(self) -> None:
        await self.async_send(CMD_STOP)

    async def async_start_timer(self) -> None:
        await self.async_send(CMD_START_TIMER)

    async def async_stop_timer(self) -> None:
        await self.async_send(CMD_STOP_TIMER)

    async def async_clear_alarm(self) -> None:
        await self.async_send(CMD_CLEAR_ALARM)

    @staticmethod
    def _parse_number(value: str | None) -> float | None:
        if value is None:
            return None
        match = re.search(r"[-+]?\d+(?:\.\d+)?", value)
        if not match:
            return None
        try:
            return float(match.group(0))
        except ValueError:
            return None

    @staticmethod
    def _parse_unit(value: str | None) -> str:
        if value and "f" in value.lower():
            return "F"
        return "C"

    @staticmethod
    def _parse_running(value: str | None) -> bool | None:
        if not value:
            return None
        lowered = value.lower()
        if "running" in lowered or lowered.strip() in {"run", "r"}:
            return True
        if "stopped" in lowered or "stop" in lowered or lowered.strip() in {"s", "off"}:
            return False
        return None
