import secrets
from dataclasses import dataclass


@dataclass
class Frame:
    # no RSV1..3 for now
    fin: bool
    opcode: int
    masked: bool
    payload: bytes


def mask_payload(payload: bytes, key: bytes) -> bytes:
    return bytes(chunk ^ key[i % 4] for i, chunk in enumerate(payload))


def parse_frame(frame: bytes) -> Frame:
    fin = bool(frame[0] >> 7)
    # no RSV1..3 parse for now
    opcode = frame[0] & 0x0F

    is_masked = bool(frame[1] >> 7)
    payload_length = frame[1] & 0x7F

    payload_start = 2
    payload_offset = 0
    key = b""
    if is_masked:
        payload_offset = 4
        key = frame[payload_start : payload_start + payload_offset]

    payload_start += payload_offset
    if 0 <= payload_length <= 125:
        payload = frame[payload_start : payload_start + payload_length]
    elif payload_length == 126:
        offset = 2
        actual_payload_length = int.from_bytes(
            frame[payload_start : payload_start + offset], "big"
        )
        payload_start += offset
        payload = frame[
            payload_start : payload_start + actual_payload_length + 1
        ]
    elif payload_length == 127:
        offset = 8
        actual_payload_length = int.from_bytes(
            frame[payload_start : payload_start + offset], "big"
        )
        payload_start += offset
        payload = frame[
            payload_start : payload_start + actual_payload_length + 1
        ]
    else:
        raise AssertionError("False payload length code")

    if is_masked:
        payload = mask_payload(bytes(payload), key)

    return Frame(fin, opcode, is_masked, bytes(payload))


def encode_frame(
    fin: bool,
    opcode: int,
    payload: bytes,
    is_masked: bool,
    masking_key: bytes | None = None,
) -> bytes:
    byte1 = (fin << 7) | opcode  # rsv = 000

    masked = int(is_masked) << 7
    payload_len = len(payload)
    if 0 <= payload_len <= 125:
        byte2 = masked | payload_len
        frame = byte1.to_bytes(1, "big") + byte2.to_bytes(1, "big")
    elif 126 <= payload_len < 65536:
        byte2 = masked | 126
        extended_payload_length = payload_len.to_bytes(2, byteorder="big")
        frame = (
            byte1.to_bytes(1, "big")
            + byte2.to_bytes(1, "big")
            + extended_payload_length
        )
    elif payload_len >= 65536:
        byte2 = masked | 127
        extended_payload_length = payload_len.to_bytes(8, byteorder="big")
        frame = (
            byte1.to_bytes(1, "big")
            + byte2.to_bytes(1, "big")
            + extended_payload_length
        )
    else:
        raise AssertionError("Ошибка длины сообщения")

    if is_masked:
        key = masking_key or secrets.token_bytes(4)
        payload = mask_payload(payload, key)
        frame = frame + key + payload
    else:
        frame: bytes = frame + payload

    return frame


if __name__ == "__main__":
    f = encode_frame(
        fin=True, opcode=2, payload=b"Hello, ther!" * 12, is_masked=True
    )
    print(f)
    f = parse_frame(f)
    print(f)
