from asyncio.streams import StreamReader, StreamWriter

from wch.websocket.frame import encode_frame, parse_frame


class WebSocketConnection:
    def __init__(
        self, reader: StreamReader, writer: StreamWriter, is_client: bool
    ) -> None:
        self._reader: StreamReader = reader
        self._writer: StreamWriter = writer
        self._is_client = is_client

    async def recv(self) -> bytes:
        msg = bytes(
            msg_chunk for msg_chunk in await self._reader.read(64 * 1024)
        )
        if not msg:
            return b""
        frame = parse_frame(msg)
        return frame.payload

    async def send_text(self, message: str) -> None:
        frame = encode_frame(
            fin=True,
            opcode=1,
            payload=message.encode("ascii"),
            is_masked=self._is_client,
        )
        self._writer.write(frame)
        await self._writer.drain()
