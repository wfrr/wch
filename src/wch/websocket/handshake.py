import asyncio
import base64
import binascii
import hashlib
import urllib.parse
from dataclasses import dataclass


class HttpRequestParsingError(Exception):
    def __init__(self, msg: str = "") -> None:
        self.msg = msg
        super().__init__(f"Invalid HTTP request: {msg}")


class BadRequestError(Exception):
    def __init__(self, msg: str = "") -> None:
        self.msg = msg
        super().__init__(f"Bad HTTP request: {msg}")


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

    def __bytes__(self) -> bytes:
        status_line = (
            f"{self.version} {self.status_code} {self.status_name}\r\n"
        )
        headers_block = ""
        for name, value in self.headers.items():
            headers_block += f"{name}: {value}\r\n"
        return (status_line + headers_block + "\r\n").encode("ascii")


async def parse_method(request_line: bytes) -> str:
    return str(request_line.split()[0], encoding="utf-8").upper()


async def parse_path(request_line: bytes) -> str:
    url = str(request_line.split()[1], encoding="utf-8")
    return urllib.parse.urlsplit(url).path


async def parse_version(request_line: bytes) -> str:
    parsed_version = str(request_line.split()[2], encoding="utf-8").upper()
    if not parsed_version.startswith("HTTP"):
        raise HttpRequestParsingError("Bad HTTP version")
    parsed_version_digits = parsed_version.removeprefix("HTTP/").split(".")
    if (
        len(parsed_version_digits) != 2
        or (not parsed_version_digits[0].isdigit())
        or (not parsed_version_digits[1].isdigit())
    ):
        raise HttpRequestParsingError("Bad HTTP version")
    return parsed_version


async def parse_headers(raw_headers: bytes) -> dict[str, str]:
    headers = raw_headers.decode("utf-8")
    request_headers = {}

    for received_header in headers.split("\r\n"):
        if not received_header:
            continue
        name, separator, value = received_header.partition(":")
        if not separator or not name:
            raise HttpRequestParsingError("Bad header")

        request_headers[name.strip().lower()] = value.strip()
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
        raise HttpRequestParsingError("Bad request line")


async def is_open_handshake_valid(request: HttpRequest) -> bool:
    # www.rfc-editor.org/info/rfc6455/#section-4.2.1
    # headers ignored: Origin, Sec-WebSocket-Protocol, Sec-WebSocket-Extensions
    # header Host just has to exist
    try:
        return bool(
            request.method == "GET"
            and request.version >= "HTTP/1.1"
            and request.headers.get("host", "")
            and request.headers.get("upgrade", "").lower() == "websocket"
            and request.headers.get("connection", "").lower() == "upgrade"
            and len(
                base64.standard_b64decode(
                    request.headers.get("sec-websocket-key", "")
                )
            )
            == 16
            and request.headers.get("sec-websocket-version", "0") == str(13)
        )
    except binascii.Error:
        return False


def calculate_accept(key: str) -> str:
    _guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    value = (key + _guid).encode("ascii")
    digest = hashlib.sha1(value).digest()
    return base64.b64encode(digest).decode("ascii")


async def open_handshake(
    request: HttpRequest, writer: asyncio.StreamWriter
) -> None:
    accept_key = calculate_accept(request.headers["sec-websocket-key"])
    headers = {
        "Upgrade": "websocket",
        "Connection": "Upgrade",
        "Sec-WebSocket-Accept": accept_key,
    }
    response = HttpResponse(
        version=request.version,
        status_code="101",
        status_name="Switching Protocols",
        headers=headers,
    )
    writer.write(bytes(response))
    await writer.drain()


async def perform_handshake(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    raw_packet = await reader.readuntil(b"\r\n\r\n")  # packet body is ignored
    http_request: HttpRequest = await parse_http_request(raw_packet)
    if not await is_open_handshake_valid(http_request):
        response = HttpResponse(
            version=http_request.version,
            status_code="400",
            status_name="Bad Request",
            headers={"Connection": "close", "Content-Length": "0"},
        )
        writer.write(bytes(response))
        await writer.drain()
        raise BadRequestError("Invalid WS upgrade request")
    await open_handshake(http_request, writer)
