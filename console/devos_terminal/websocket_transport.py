from __future__ import annotations

import base64
import hashlib
import socket
import struct
from dataclasses import dataclass


WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
MAX_FRAME_BYTES = 1_048_576


@dataclass(frozen=True)
class WebSocketFrame:
    opcode: int
    payload: bytes


def websocket_accept(key: str) -> str:
    digest = hashlib.sha1(f"{key}{WEBSOCKET_GUID}".encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


def _receive_exact(connection: socket.socket, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = connection.recv(remaining)
        if not chunk:
            raise ConnectionError("WebSocket connection closed.")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def receive_frame(connection: socket.socket) -> WebSocketFrame:
    first, second = _receive_exact(connection, 2)
    if first & 0x70 or not first & 0x80:
        raise ValueError("Unsupported WebSocket frame.")
    opcode = first & 0x0F
    if opcode not in {0x1, 0x2, 0x8, 0x9, 0xA}:
        raise ValueError("Unsupported WebSocket opcode.")
    if not second & 0x80:
        raise ValueError("Client WebSocket frames must be masked.")

    length = second & 0x7F
    if length == 126:
        length = struct.unpack("!H", _receive_exact(connection, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", _receive_exact(connection, 8))[0]
    if length > MAX_FRAME_BYTES:
        raise ValueError("WebSocket frame is too large.")

    mask = _receive_exact(connection, 4)
    payload = _receive_exact(connection, length)
    return WebSocketFrame(
        opcode=opcode,
        payload=bytes(value ^ mask[index % 4] for index, value in enumerate(payload)),
    )


def send_frame(connection: socket.socket, payload: bytes, *, opcode: int) -> None:
    length = len(payload)
    header = bytearray([0x80 | opcode])
    if length < 126:
        header.append(length)
    elif length <= 0xFFFF:
        header.extend((126, *struct.pack("!H", length)))
    else:
        header.extend((127, *struct.pack("!Q", length)))
    connection.sendall(bytes(header) + payload)


def send_close(connection: socket.socket, code: int = 1000) -> None:
    send_frame(connection, struct.pack("!H", code), opcode=0x8)

