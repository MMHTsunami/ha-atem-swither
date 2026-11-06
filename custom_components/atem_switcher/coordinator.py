"""ATEM UDP connection and Home Assistant data coordinator."""

from __future__ import annotations

import asyncio
import logging
import secrets
from collections.abc import Callable
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONNECTION_TIMEOUT,
    DEFAULT_PORT,
    DOMAIN,
    MANUFACTURER,
    UPDATE_INTERVAL,
)
from .protocol import (
    FLAG_ACK,
    FLAG_RELIABLE,
    FLAG_SYN,
    AtemField,
    AtemPacket,
    decode_fields,
    decode_packet,
    encode_field,
    encode_packet,
)

_LOGGER = logging.getLogger(__name__)
_HANDSHAKE_PAYLOAD = b"\x01\x00\x00\x00\x00\x00\x00\x00"


class AtemConnectionError(HomeAssistantError):
    """Raised when an ATEM switcher connection cannot be established."""


def _decode_text(data: bytes) -> str:
    return data.split(b"\x00", 1)[0].decode("utf-8", errors="replace").strip()


class _AtemDatagramProtocol(asyncio.DatagramProtocol):
    """Receive ATEM datagrams and complete the initial handshake."""

    def __init__(
        self,
        session_id: int,
        on_fields: Callable[[tuple[AtemField, ...]], None],
        on_disconnect: Callable[[], None],
    ) -> None:
        self.session_id = session_id
        self.on_fields = on_fields
        self.on_disconnect = on_disconnect
        self.transport: asyncio.DatagramTransport | None = None
        self.handshake: asyncio.Future[None] | None = None
        self.established = False
        self._last_sequence: int | None = None
        self._next_sequence = 1
        self._remote_session_id: int | None = None

    def send_command(self, name: str, data: bytes) -> None:
        """Send a reliable command to the switcher."""
        if self.transport is None:
            raise AtemConnectionError("ATEM UDP transport is not ready")
        self.transport.sendto(
            encode_packet(
                flags=FLAG_RELIABLE,
                session_id=self._remote_session_id or self.session_id,
                local_sequence_number=self._next_sequence,
                payload=encode_field(name, data),
            )
        )
        self._next_sequence = (self._next_sequence + 1) & 0xFFFF

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        if not isinstance(transport, asyncio.DatagramTransport):
            raise AtemConnectionError("ATEM transport is not a datagram transport")
        self.transport = transport

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        try:
            packet = decode_packet(data)
        except ValueError as err:
            _LOGGER.warning("Ignoring malformed ATEM packet from %s: %s", addr[0], err)
            return

        if packet.flags & FLAG_SYN and self.handshake is not None:
            self._complete_handshake(packet)
            return

        if not packet.payload:
            if packet.flags & FLAG_RELIABLE:
                self._send_ack(packet)
            return

        if packet.flags & FLAG_RELIABLE:
            self._remote_session_id = packet.session_id
            self._send_ack(packet)
            if packet.local_sequence_number == self._last_sequence:
                return
            self._last_sequence = packet.local_sequence_number
        try:
            fields = decode_fields(packet.payload)
        except ValueError as err:
            _LOGGER.warning("Ignoring malformed ATEM fields from %s: %s", addr[0], err)
            return
        self.on_fields(fields)

    def error_received(self, exc: Exception) -> None:
        _LOGGER.warning("ATEM UDP transport error: %s", exc)
        if self.handshake is not None and not self.handshake.done():
            self.handshake.set_exception(AtemConnectionError(str(exc)))

    def connection_lost(self, exc: Exception | None) -> None:
        if exc is not None:
            _LOGGER.warning("ATEM UDP connection lost: %s", exc)
        if self.established:
            self.established = False
            self.on_disconnect()

    def send_syn(self) -> None:
        if self.transport is None:
            raise AtemConnectionError("ATEM UDP transport is not ready")
        self.transport.sendto(
            encode_packet(
                flags=FLAG_SYN,
                session_id=self.session_id,
                payload=_HANDSHAKE_PAYLOAD,
            )
        )

    def _complete_handshake(self, packet: AtemPacket) -> None:
        if packet.session_id != self.session_id:
            return
        if not packet.payload or packet.payload[0] != 0x02:
            if self.handshake is not None and not self.handshake.done():
                self.handshake.set_exception(
                    AtemConnectionError("ATEM switcher rejected the connection")
                )
            return
        if self.transport is not None:
            self.transport.sendto(
                encode_packet(
                    flags=FLAG_ACK,
                    session_id=self.session_id,
                    acknowledgement_number=0,
                )
            )
        self.established = True
        if self.handshake is not None and not self.handshake.done():
            self.handshake.set_result(None)

    def _send_ack(self, packet: AtemPacket) -> None:
        if self.transport is not None:
            self.transport.sendto(
                encode_packet(
                    flags=FLAG_ACK,
                    session_id=packet.session_id,
                    acknowledgement_number=packet.local_sequence_number,
                )
            )

    def close(self) -> None:
        if self.transport is not None:
            self.transport.close()


class AtemClient:
    """Own an asynchronous UDP connection to an ATEM switcher."""

    def __init__(
        self,
        host: str,
        on_fields: Callable[[tuple[AtemField, ...]], None],
        on_disconnect: Callable[[], None],
    ) -> None:
        self.host = host
        self.on_fields = on_fields
        self.on_disconnect = on_disconnect
        self._protocol: _AtemDatagramProtocol | None = None

    async def async_connect(self) -> None:
        """Establish the ATEM UDP handshake."""
        session_id = secrets.randbelow(0xFFFF) + 1
        loop = asyncio.get_running_loop()
        try:
            protocol = _AtemDatagramProtocol(
                session_id, self.on_fields, self.on_disconnect
            )
            await loop.create_datagram_endpoint(
                lambda: protocol,
                remote_addr=(self.host, DEFAULT_PORT),
            )
            self._protocol = protocol
            handshake = loop.create_future()
            protocol.handshake = handshake
            deadline = loop.time() + CONNECTION_TIMEOUT
            while True:
                protocol.send_syn()
                try:
                    await asyncio.wait_for(asyncio.shield(handshake), timeout=1)
                    break
                except TimeoutError:
                    if loop.time() >= deadline:
                        raise
        except (OSError, TimeoutError, AtemConnectionError) as err:
            self.async_close()
            raise AtemConnectionError(
                f"Failed to connect to ATEM switcher at {self.host}: {err}"
            ) from err

    def async_close(self) -> None:
        """Close the UDP transport."""
        if self._protocol is not None:
            self._protocol.close()
            self._protocol = None

    def send_command(self, name: str, data: bytes) -> None:
        """Send a command to the switcher."""
        if self._protocol is None:
            raise AtemConnectionError("Not connected to the ATEM switcher")
        self._protocol.send_command(name, data)


class AtemCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Track connection status and the latest fields received from an ATEM."""

    def __init__(self, hass: HomeAssistant, host: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{host}",
            update_interval=UPDATE_INTERVAL,
        )
        self.host = host
        self.fields: dict[str, bytes] = {}
        self.model: str | None = None
        self.product_name: str | None = None
        self.firmware_version: str | None = None
        self.me_count = 1
        self.aux_count = 0
        self.input_names: dict[int, str] = {}
        self.output_names: dict[int, str] = {}
        self.program: dict[int, int] = {}
        self.preview: dict[int, int] = {}
        self.aux: dict[int, int] = {}
        self.initialized = False
        self.client = AtemClient(host, self._handle_fields, self._handle_disconnect)
        self.connected = False
        self._stopping = False
        self._reconnect_task: asyncio.Task[None] | None = None

    async def async_setup(self) -> None:
        """Connect to the switcher and begin receiving its state."""
        await self.client.async_connect()
        self.connected = True
        for _ in range(50):
            if self.initialized:
                break
            await asyncio.sleep(0.1)
        else:
            _LOGGER.warning(
                "ATEM switcher at %s did not finish sending its initial state",
                self.host,
            )
        self.async_set_updated_data(self._make_data())

    async def _async_update_data(self) -> dict[str, Any]:
        """Return the latest state received from the switcher."""
        if not self.connected:
            raise AtemConnectionError(f"Not connected to ATEM switcher at {self.host}")
        return self._make_data()

    async def async_shutdown(self) -> None:
        """Close the connection when the config entry is unloaded."""
        self._stopping = True
        if self._reconnect_task is not None:
            self._reconnect_task.cancel()
            self._reconnect_task = None
        self.connected = False
        self.client.async_close()

    def _handle_fields(self, fields: tuple[AtemField, ...]) -> None:
        for field in fields:
            self.fields[field.name] = field.data
            try:
                self._parse_field(field)
            except (IndexError, ValueError) as err:
                _LOGGER.debug("Could not parse ATEM field %s: %s", field.name, err)
        self.async_set_updated_data(self._make_data())

    def _parse_field(self, field: AtemField) -> None:
        name, data = field.name, field.data
        if name == "_pin":
            self.product_name = _decode_text(data[:44])
            self.model = self.product_name
        elif name == "_ver":
            self.firmware_version = (
                f"{int.from_bytes(data[0:2], 'big')}.{int.from_bytes(data[2:4], 'big')}"
            )
        elif name == "_top":
            self.me_count = data[0]
            self.aux_count = data[3] if len(data) > 3 else 0
        elif name == "InPr":
            source = int.from_bytes(data[0:2], "big")
            long_name = _decode_text(data[2:22])
            self.input_names[source] = long_name or f"Input {source}"
            port_type = data[32] if len(data) > 32 else None
            if port_type in (128, 129, 131) and long_name:
                self.output_names[source] = long_name
            else:
                self.output_names.pop(source, None)
        elif name == "PrgI":
            self.program[data[0]] = int.from_bytes(data[2:4], "big")
        elif name == "PrvI":
            self.preview[data[0]] = int.from_bytes(data[2:4], "big")
        elif name == "AuxS":
            self.aux[data[0]] = int.from_bytes(data[2:4], "big")
            self.aux_count = max(self.aux_count, data[0] + 1)
        elif name == "InCm":
            self.initialized = True

    def async_send_command(self, name: str, data: bytes) -> None:
        """Send a command to the switcher."""
        self.client.send_command(name, data)

    def set_program(self, me: int, source: int) -> None:
        """Cut the given source to program."""
        self.async_send_command("CPgI", bytes([me, 0]) + source.to_bytes(2, "big"))

    def set_preview(self, me: int, source: int) -> None:
        """Set the given source as preview."""
        self.async_send_command("CPvI", bytes([me, 0]) + source.to_bytes(2, "big"))

    def set_aux(self, aux: int, source: int) -> None:
        """Route the given source to an aux output."""
        self.async_send_command(
            "CAuS", bytes([1, aux]) + source.to_bytes(2, "big")
        )

    def _handle_disconnect(self) -> None:
        self.connected = False
        if self._stopping:
            return
        self.async_set_updated_data(self._make_data())
        if not self._stopping and self._reconnect_task is None:
            self._reconnect_task = self.hass.async_create_task(
                self._async_reconnect()
            )

    async def _async_reconnect(self) -> None:
        """Retry a lost connection with capped exponential backoff."""
        delay = 1
        try:
            while not self._stopping:
                await asyncio.sleep(delay)
                try:
                    await self.client.async_connect()
                except AtemConnectionError as err:
                    _LOGGER.warning(
                        "Failed to reconnect to ATEM switcher at %s: %s",
                        self.host,
                        err,
                    )
                    delay = min(delay * 2, 60)
                    continue

                self.connected = True
                self.async_set_updated_data(self._make_data())
                return
        except asyncio.CancelledError:
            raise
        finally:
            self._reconnect_task = None

    def device_info(self, entry_id: str) -> DeviceInfo:
        """Return device registry info including detected model and firmware."""
        return DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=self.product_name or f"ATEM Switcher ({self.host})",
            manufacturer=MANUFACTURER,
            model=self.model,
            sw_version=self.firmware_version,
        )

    def _make_data(self) -> dict[str, Any]:
        return {
            "connected": self.connected,
            "fields": dict(self.fields),
        }
