import asyncio

from wch.websocket.connection import WebSocketConnection


async def main():
    reader, writer = await asyncio.open_connection("127.0.0.1", 8888)

    # upgrade connection
    writer.write(
        b"GET /chat HTTP/1.1\r\nHost: server.example.com\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Version: 13\r\n\r\n"
    )
    confirm_response = bytes(
        msg_chunk for msg_chunk in await reader.read(64 * 1024)
    )
    # TODO: validate confirm upgrade response
    print(f"Upgrade connection confirmed: {confirm_response}")

    msg = input("->: ")
    print(f"Sending: {msg}")

    ws = WebSocketConnection(reader, writer, is_client=True)
    await ws.send_text(msg)
    data = await ws.recv()
    print(f"Received: {data.decode()}")

    writer.close()
    await writer.wait_closed()


asyncio.run(main())
