import pytest
from websockets.frames import Frame, Opcode

from wch.websocket.frame import encode_frame


@pytest.mark.parametrize("fin", (1, 0))
def test_encode_fin(fin):
    reference = Frame(
        opcode=Opcode.TEXT,
        data=b"a",
        fin=bool(fin),
    ).serialize(mask=False)
    frame = encode_frame(fin, Opcode.TEXT, b"a", False)
    assert reference == frame


@pytest.mark.parametrize(
    "opcode",
    (
        Opcode.CONT,
        Opcode.TEXT,
        Opcode.BINARY,
        Opcode.CLOSE,
        Opcode.PING,
        Opcode.PONG,
    ),
)
def test_encode_opcode(opcode):
    reference = Frame(
        opcode=opcode,
        data=b"a",
        fin=True,
    ).serialize(mask=False)
    frame = encode_frame(True, opcode, b"a", False)
    assert reference == frame


@pytest.mark.parametrize(
    "payload",
    (
        b"",
        b"a",
        b"a" * 125,
        b"a" * 126,
        b"a" * 127,
        b"a" * 255,
        b"a" * 65_535,
        b"a" * 65_536,
    ),
)
def test_encode_payload(payload):
    reference = Frame(
        opcode=Opcode.TEXT,
        data=payload,
        fin=True,
    ).serialize(mask=False)
    frame = encode_frame(True, Opcode.TEXT, payload, False)
    assert reference == frame


def test_encode_masked():
    key = b"\x12\x34\x56\x78"
    payload = b"a"
    frame = encode_frame(True, Opcode.TEXT, b"a", True, masking_key=key)
    assert frame[1] >> 7 == 1
    assert frame[2:6] == key

    unmasked = bytes(byte ^ key[i % 4] for i, byte in enumerate(frame[6:]))
    assert unmasked == payload
