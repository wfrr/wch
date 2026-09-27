import asyncio


async def main():
    msg = input("-: ")
    reader, writer = await asyncio.open_connection("127.0.0.1", 8888)
    print(f"Sending: {msg}")
    writer.write(msg.encode())
    await writer.drain()
    data = await reader.read(128)
    print(f"Received: {data.decode()}")
    writer.close()
    await writer.wait_closed()


asyncio.run(main())
