import asyncio
import binascii
from base64 import standard_b64decode
from dataclasses import dataclass
from hashlib import sha1
from urllib.parse import urlsplit


class HttpRequestParsingError(Exception):
    def __init__(self, msg="Invalid HTTP request") -> None: ...


@dataclass
class HttpRequest:
    method: str
    path: str
    version: str
    headers: dict[str, str]

    def __ge__(self, other: str):
        return float(self.version.removeprefix("HTTP/")) >= float(
            other.removeprefix("HTTP/")
        )


@dataclass
class HttpResponse:
    version: str
    status_code: str
    status_name: str
    headers: dict[str, str]

    def bytes(self) -> bytes:
        headers_block = ""
        for name, value in self.headers.items():
            headers_block += f"{name}: {value}\r\n"
        status_line = (
            f"{self.version} {self.status_code} {self.status_name}\r\n"
        )
        return (status_line + headers_block + "\r\n\r\n").encode("utf-8")


async def parse_method(request_line: bytes) -> str:
    return str(request_line.split()[0], encoding="utf-8").upper()


async def parse_path(request_line: bytes) -> str:
    url = str(request_line.split()[1], encoding="utf-8")
    return urlsplit(url).path


async def parse_version(request_line: bytes) -> str:
    parsed_version = str(request_line.split()[2], encoding="utf-8").upper()
    if not parsed_version.startswith("HTTP"):
        raise HttpRequestParsingError()
    parsed_version_digits = parsed_version.removeprefix("HTTP/").split(".")
    if (
        len(parsed_version_digits) != 2
        or (not parsed_version_digits[0].isdigit())
        or (not parsed_version_digits[1].isdigit())
    ):
        raise HttpRequestParsingError()
    return parsed_version


async def parse_headers(raw_headers: bytes) -> dict[str, str]:
    headers = str(raw_headers, encoding="utf-8")
    request_headers = {}
    for received_header in headers.split("\r\n"):
        if len(rh := received_header.split(": ")) == 2:
            request_headers[rh[0].lower()] = rh[1].lower()
        else:
            raise HttpRequestParsingError()
    return request_headers


async def parse_http_request(raw_packet: bytes) -> HttpRequest:
    request_line = raw_packet.split(b"\r\n")[0]
    if len(request_line.split()) == 3:
        raw_leftover = raw_packet.removeprefix(request_line + b"\r\n")
        raw_headers = raw_leftover.removesuffix(b"\r\n\r\n")
        return HttpRequest(
            method=await parse_method(request_line),
            path=await parse_path(request_line),
            version=await parse_version(request_line),
            headers=await parse_headers(raw_headers),
        )
    else:
        raise HttpRequestParsingError()


async def is_open_handshake_valid(request: HttpRequest) -> bool:
    # www.rfc-editor.org/info/rfc6455/#section-4.2.1
    # headers ignored: Origin, Sec-WebSocket-Protocol, Sec-WebSocket-Extensions
    # header Host just has to exist
    try:
        return bool(
            request.method == "GET"
            and request.version >= "HTTP/1.1"
            and request.headers.get("host", "")
            and request.headers.get("upgrade", "") == "websocket"
            and request.headers.get("connection", "") == "upgrade"
            and len(
                standard_b64decode(request.headers.get("sec-websocket-key", ""))
            )
            == 16
            and request.headers.get("sec-websocket-version", "0") == str(13)
        )
    except binascii.Error:
        return False


async def open_handshake(
    request: HttpRequest, writer: asyncio.StreamWriter
) -> None:
    headers = {
        "Upgrade": "websocket",
        "Connection": "Upgrade",
        "Sec-WebSocket-Accept": sha1(
            request.headers["sec-websocket-key"].encode("utf-8")
        ).hexdigest(),
    }
    response = HttpResponse(
        version=request.version,
        status_code="101",
        status_name="Switching Protocols",
        headers=headers,
    )
    writer.write(response.bytes())
    await writer.drain()


async def perform_handshake(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    raw_packet = await reader.readuntil(b"\r\n\r\n")  # packet body is ignored
    http_request: HttpRequest = await parse_http_request(raw_packet)
    print(f"Received: {http_request}")
    if not await is_open_handshake_valid(http_request):
        print("Invalid open handshake")
        return
    print("Validated open handshake")
    await open_handshake(http_request, writer)
    print("Opened handshake")


async def handler(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    await perform_handshake(reader, writer)
    while True:
        msg = await reader.read(128)
        if reader.at_eof():
            print("eof")
            break
        print(f"Received: {msg.decode()}")


async def main():
    server = await asyncio.start_server(handler, "127.0.0.1", "8888")
    addrs = ", ".join(str(sock.getsockname()) for sock in server.sockets)
    print(f"Serving on {addrs}")

    async with server:
        await server.serve_forever()


asyncio.run(main())
