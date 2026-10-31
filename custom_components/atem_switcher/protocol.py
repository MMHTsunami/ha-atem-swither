"""Low-level ATEM UDP packet encoding and decoding."""

from __future__ import annotations

from dataclasses import dataclass

HEADER_SIZE = 12
MAX_PACKET_LENGTH = 0x7FF

FLAG_RELIABLE = 0x01
FLAG_SYN = 0x02
FLAG_RETRANSMISSION = 0x04
FLAG_REQUEST_RETRANSMISSION = 0x08
FLAG_ACK = 0x10


@dataclass(frozen=True)
class AtemPacket:
    """Decoded ATEM packet header and payload."""

    flags: int
    session_id: int
    acknowledgement_number: int
    remote_sequence_number: int
    local_sequence_number: int
    payload: bytes


@dataclass(frozen=True)
class AtemField:
    """A decoded field or command in an ATEM packet."""

    name: str
    data: bytes


def decode_packet(data: bytes) -> AtemPacket:
    """Decode a complete ATEM packet, rejecting malformed lengths."""
    if len(data) < HEADER_SIZE:
        raise ValueError("ATEM packet is shorter than its header")

    flags_and_length = int.from_bytes(data[0:2], "big")
    packet_length = flags_and_length & MAX_PACKET_LENGTH
    if packet_length != len(data):
        raise ValueError(
            f"ATEM packet length mismatch: header={packet_length}, received={len(data)}"
        )

    return AtemPacket(
        flags=flags_and_length >> 11,
        session_id=int.from_bytes(data[2:4], "big"),
        acknowledgement_number=int.from_bytes(data[4:6], "big"),
        remote_sequence_number=int.from_bytes(data[8:10], "big"),
        local_sequence_number=int.from_bytes(data[10:12], "big"),
        payload=data[HEADER_SIZE:],
    )


def encode_packet(
    *,
    flags: int,
    session_id: int,
    acknowledgement_number: int = 0,
    remote_sequence_number: int = 0,
    local_sequence_number: int = 0,
    payload: bytes = b"",
) -> bytes:
    """Encode an ATEM packet with its 12-byte header."""
    if not 0 <= flags <= 0x1F:
        raise ValueError("ATEM flags must fit in the header's five flag bits")
    packet_length = HEADER_SIZE + len(payload)
    if packet_length > MAX_PACKET_LENGTH:
        raise ValueError("ATEM packet exceeds the protocol's 11-bit length limit")

    flags_and_length = (flags << 11) | packet_length
    return b"".join(
        (
            flags_and_length.to_bytes(2, "big"),
            session_id.to_bytes(2, "big"),
            acknowledgement_number.to_bytes(2, "big"),
            b"\x00\x00",
            remote_sequence_number.to_bytes(2, "big"),
            local_sequence_number.to_bytes(2, "big"),
            payload,
        )
    )


def encode_field(name: str, data: bytes) -> bytes:
    """Encode a single command field (length, padding, 4-char name, data)."""
    return (8 + len(data)).to_bytes(2, "big") + b"\x00\x00" + name.encode("ascii") + data


def decode_fields(payload: bytes) -> tuple[AtemField, ...]:
    """Decode concatenated length-prefixed fields and commands."""
    fields: list[AtemField] = []
    offset = 0

    while offset < len(payload):
        if len(payload) - offset < 8:
            raise ValueError("ATEM field header is incomplete")

        field_length = int.from_bytes(payload[offset : offset + 2], "big")
        if field_length < 8:
            raise ValueError(f"ATEM field has invalid length {field_length}")
        end = offset + field_length
        if end > len(payload):
            raise ValueError("ATEM field extends beyond the packet")

        try:
            name = payload[offset + 4 : offset + 8].decode("ascii")
        except UnicodeDecodeError as err:
            raise ValueError("ATEM field name is not ASCII") from err

        fields.append(AtemField(name, payload[offset + 8 : end]))
        offset = end

    return tuple(fields)
