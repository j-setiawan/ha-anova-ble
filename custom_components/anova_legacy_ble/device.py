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
            # Some firmware replies to write commands and some does not. Do not
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
            raise AnovaProtocolError(
                f"Timeout waiting for response to {command!r}"
            ) from err
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
        self._id_command_supported: bool | None = None
        self._model = "Original Precision Cooker"
        self._is_wifi_model = False
        self._known_unit: str | None = None
        self._last_state: AnovaState | None = None

    async def _connect(self) -> BleakClient:
        """Resolve the best HA Bluetooth path and establish a connection."""
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            raise AnovaNotFoundError(
                "No connectable Home Assistant Bluetooth adapter/proxy can currently "
                f"reach {self.address}"
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
            raise AnovaError(
                f"Could not connect to Anova at {self.address}: {err}"
            ) from err

    @staticmethod
    def _has_anova_characteristic(client: BleakClient) -> bool:
        """Return whether service discovery contains the Anova characteristic."""
        try:
            return client.services.get_characteristic(CHAR_UUID) is not None
        except Exception:  # noqa: BLE001 - backend-specific service collection errors
            return False

    @staticmethod
    def _looks_like_missing_characteristic(err: Exception) -> bool:
        message = str(err).lower()
        return "characteristic" in message and any(
            token in message for token in ("not found", "missing", "does not exist")
        )

    @staticmethod
    async def _clear_service_cache(client: BleakClient) -> None:
        """Best-effort service-cache clear before one fresh discovery attempt."""
        clear_cache = getattr(client, "clear_cache", None)
        if clear_cache is None:
            _LOGGER.debug("BLE backend does not expose clear_cache()")
            return

        try:
            cleared = await clear_cache()
            _LOGGER.warning(
                "Anova FFE1 missing; BLE service cache clear returned %s", cleared
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Could not clear BLE service cache: %s", err)

    @staticmethod
    async def _disconnect_client(client: BleakClient) -> None:
        try:
            await client.disconnect()
        except Exception:  # noqa: BLE001 - best effort
            pass

    async def _open_session(self) -> tuple[BleakClient, _GattSession]:
        """Open a session, retrying once after stale/incomplete service discovery."""
        last_error: Exception | None = None

        for attempt in range(2):
            client = await self._connect()

            if not self._has_anova_characteristic(client):
                last_error = AnovaError(
                    f"Connected to {self.address}, but GATT characteristic {CHAR_UUID} "
                    "was missing from service discovery"
                )
                if attempt == 0:
                    await self._clear_service_cache(client)
                    await self._disconnect_client(client)
                    _LOGGER.warning(
                        "Retrying Anova connection once after incomplete GATT discovery"
                    )
                    continue

                await self._disconnect_client(client)
                raise last_error

            session = _GattSession(client)
            try:
                await session.start()
                return client, session
            except Exception as err:  # noqa: BLE001
                last_error = err
                if attempt == 0 and self._looks_like_missing_characteristic(err):
                    await self._clear_service_cache(client)
                    await self._disconnect_client(client)
                    _LOGGER.warning(
                        "Retrying Anova connection once after FFE1 notification setup failed"
                    )
                    continue

                await self._disconnect_client(client)
                raise AnovaError(
                    f"Connected, but could not enable Anova notifications: {err}"
                ) from err

        raise AnovaError(f"Could not open Anova GATT session: {last_error}")

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
                if self._cooker_id is None and self._id_command_supported is not False:
                    try:
                        cooker_id = await session.command(CMD_GET_ID, timeout=4.0)
                    except AnovaProtocolError:
                        cooker_id = None

                    if cooker_id:
                        cooker_id = cooker_id.strip()
                        if self._is_unsupported_response(cooker_id):
                            self._id_command_supported = False
                            self._model = "Original Precision Cooker 800W (Bluetooth)"
                            _LOGGER.debug(
                                "Anova does not support %r; disabling cooker-ID probing",
                                CMD_GET_ID,
                            )
                        else:
                            self._id_command_supported = True
                            self._cooker_id = cooker_id
                            if cooker_id.lower().startswith("anova f56-"):
                                self._is_wifi_model = True
                                self._model = (
                                    "Original Precision Cooker 900W (BT/Wi-Fi)"
                                )
                            else:
                                self._model = (
                                    "Original Precision Cooker 800W (Bluetooth)"
                                )

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

                parsed_unit = self._parse_unit(unit_raw)
                previous_known_unit = self._known_unit
                if parsed_unit is not None:
                    self._known_unit = parsed_unit

                parsed_running = self._parse_running(status_raw)
                parsed_timer = self._parse_number(timer_raw)

                # A temperature without a trustworthy unit is dangerous: e.g.
                # 132 F must never be published as 132 C. On the first poll,
                # wait for a valid unit response before accepting temperatures.
                parsed_current = (
                    self._parse_temperature(temp_raw, self._known_unit)
                    if self._known_unit is not None
                    else None
                )
                parsed_target = (
                    self._parse_temperature(target_raw, self._known_unit)
                    if self._known_unit is not None
                    else None
                )

                valid_values = (
                    parsed_unit,
                    parsed_running,
                    parsed_current,
                    parsed_target,
                    parsed_timer,
                )
                if all(value is None for value in valid_values):
                    raise AnovaProtocolError(
                        "Connected to the cooker, but none of the known A2/A3 "
                        "commands returned valid data"
                    )

                previous = self._last_state
                effective_unit = self._known_unit or (
                    previous.unit if previous is not None else "C"
                )

                previous_current = (
                    previous.current_temperature if previous is not None else None
                )
                previous_target = (
                    previous.target_temperature if previous is not None else None
                )

                if (
                    previous is not None
                    and previous_known_unit is not None
                    and self._known_unit is not None
                    and previous_known_unit != self._known_unit
                ):
                    previous_current = self._convert_temperature(
                        previous_current, previous_known_unit, self._known_unit
                    )
                    previous_target = self._convert_temperature(
                        previous_target, previous_known_unit, self._known_unit
                    )

                state = AnovaState(
                    current_temperature=(
                        parsed_current
                        if parsed_current is not None
                        else previous_current
                    ),
                    target_temperature=(
                        parsed_target
                        if parsed_target is not None
                        else previous_target
                    ),
                    timer_minutes=(
                        parsed_timer
                        if parsed_timer is not None
                        else (previous.timer_minutes if previous is not None else None)
                    ),
                    running=(
                        parsed_running
                        if parsed_running is not None
                        else (previous.running if previous is not None else None)
                    ),
                    unit=effective_unit,
                    cooker_id=self._cooker_id,
                    model=self._model,
                    is_wifi_model=self._is_wifi_model,
                )
                self._last_state = state
                return state
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
    def _is_unsupported_response(value: str) -> bool:
        lowered = value.strip().lower()
        return lowered in {
            "invalid command",
            "unknown command",
            "unsupported command",
            "not supported",
            "error",
        } or "invalid command" in lowered

    @staticmethod
    def _parse_number(value: str | None) -> float | None:
        if value is None or AnovaLegacyDevice._is_unsupported_response(value):
            return None
        match = re.search(r"[-+]?\d+(?:\.\d+)?", value)
        if not match:
            return None
        try:
            return float(match.group(0))
        except ValueError:
            return None

    @staticmethod
    def _parse_temperature(value: str | None, unit: str) -> float | None:
        """Parse a temperature and reject readings impossible for this appliance."""
        parsed = AnovaLegacyDevice._parse_number(value)
        if parsed is None:
            return None

        # Allow a little sensor tolerance outside the normal 0-100 C cooker
        # range while still catching classic unit-mismatch artifacts (132 C).
        low, high = ((-10.0, 110.0) if unit == "C" else (14.0, 230.0))
        if not low <= parsed <= high:
            _LOGGER.warning(
                "Ignoring implausible Anova temperature %.2f %s", parsed, unit
            )
            return None
        return parsed

    @staticmethod
    def _parse_unit(value: str | None) -> str | None:
        """Parse only explicit unit responses; never guess on malformed data."""
        if value is None or AnovaLegacyDevice._is_unsupported_response(value):
            return None
        normalized = value.strip().lower()
        if normalized in {"f", "fahrenheit", "°f"}:
            return "F"
        if normalized in {"c", "celsius", "°c"}:
            return "C"
        return None

    @staticmethod
    def _parse_running(value: str | None) -> bool | None:
        if not value or AnovaLegacyDevice._is_unsupported_response(value):
            return None
        lowered = value.lower()
        if "running" in lowered or lowered.strip() in {"run", "r"}:
            return True
        if (
            "stopped" in lowered
            or "stop" in lowered
            or lowered.strip() in {"s", "off"}
        ):
            return False
        return None

    @staticmethod
    def _convert_temperature(
        value: float | None, from_unit: str, to_unit: str
    ) -> float | None:
        if value is None or from_unit == to_unit:
            return value
        if from_unit == "C" and to_unit == "F":
            return value * 9 / 5 + 32
        if from_unit == "F" and to_unit == "C":
            return (value - 32) * 5 / 9
        return value
