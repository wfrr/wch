import pytest
from websockets.frames import Frame, Opcode

from wch.websocket.frame import parse_frame


def test_parse_unmasked_text():
    # FIN=1, opcode=1 (TEXT), MASK=0, length=5, payload="Hello"
    raw = bytes.fromhex("81 05 48 65 6c 6c 6f")

    frame = parse_frame(raw)

    assert frame.fin is True
    assert frame.opcode == 1
    assert frame.masked is False
    assert frame.payload == b"Hello"


def test_parse_masked_text():
    # FIN=1, opcode=1, MASK=1, length=5
    # Masking key: 12 34 56 78
    # "Hello" XOR key = 5a 51 3a 14 7d
    raw = bytes.fromhex("81 85 12 34 56 78 5a 51 3a 14 7d")

    frame = parse_frame(raw)

    assert frame.fin is True
    assert frame.opcode == 1
    assert frame.masked is True
    assert frame.payload == b"Hello"


@pytest.mark.parametrize(
    "payload",
    (
        b"",
        b"a",
        b"a" * 125,
        b"a" * 126,
        b"a" * 127,
        b"a" * 255,
        b"a" * 65535,
        b"a" * 65536,
    ),
)
def test_parse_payload_lengths(payload):
    raw = Frame(
        opcode=Opcode.TEXT,
        data=payload,
        fin=True,
    ).serialize(mask=False)
    frame = parse_frame(raw)
    assert frame.payload == payload
