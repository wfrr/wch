import asyncio

from wch.websocket.connection import WebSocketConnection
from wch.websocket.handshake import (
    BadRequestError,
    HttpRequestParsingError,
    perform_handshake,
)


async def handler(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    try:
        await perform_handshake(reader, writer)
    except HttpRequestParsingError as hrpr:
        print(hrpr)
        return
    except BadRequestError as bre:
        print(bre)
        return

    ws = WebSocketConnection(reader, writer, is_client=False)
    message = await ws.recv()
    print(f"Received: {message.decode('utf-8')}")
    if not message:
        print("Not answering")
        return
    resp_msg = f"Echo: {message.decode('utf-8')}"
    await ws.send_text(resp_msg)
    print(f"Sent: {resp_msg}")


async def main():
    server = await asyncio.start_server(handler, "127.0.0.1", "8888")
    addrs = ", ".join(str(sock.getsockname()) for sock in server.sockets)
    print(f"Serving on {addrs}")

    async with server:
        await server.serve_forever()


asyncio.run(main())
