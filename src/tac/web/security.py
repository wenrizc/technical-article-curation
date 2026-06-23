from __future__ import annotations

from secrets import token_urlsafe
from urllib.parse import urlsplit

from fastapi import Request
from fastapi.responses import JSONResponse, Response

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient", "testserver"}


class RequestBodyTooLarge(RuntimeError):
    pass


def new_csrf_token() -> str:
    return token_urlsafe(32)


def _host_name(host_header: str) -> str:
    value = host_header.strip()
    if value.startswith("[") and "]" in value:
        return value[1 : value.index("]")]
    return value.split(":", 1)[0]


def _origin_base(value: str) -> str:
    parts = urlsplit(value)
    if not parts.scheme or not parts.netloc:
        return ""
    return f"{parts.scheme}://{parts.netloc}"


def _request_base(request: Request) -> str:
    host = request.headers.get("host", "")
    return f"{request.url.scheme}://{host}"


def is_local_request(request: Request) -> bool:
    client_host = request.client.host if request.client else ""
    host_header = request.headers.get("host", "")
    return client_host in LOCAL_HOSTS and _host_name(host_header) in LOCAL_HOSTS


def same_origin_write_allowed(request: Request) -> bool:
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    expected = _request_base(request)
    if origin:
        return _origin_base(origin) == expected
    if referer:
        return _origin_base(referer) == expected
    return False


def csrf_allowed(request: Request) -> bool:
    expected = getattr(request.app.state, "csrf_token", None)
    supplied = request.headers.get("x-tac-csrf")
    return bool(expected and supplied and supplied == expected)


def _content_length(header_value: str | None) -> int | None:
    if header_value is None:
        return None
    return int(header_value)


async def _buffer_request_body(request: Request, *, max_bytes: int) -> None:
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > max_bytes:
            raise RequestBodyTooLarge
        if chunk:
            chunks.append(chunk)
    body = b"".join(chunks)
    sent = False

    async def replay_receive():
        nonlocal sent
        if sent:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    request._body = body  # type: ignore[attr-defined]
    request._receive = replay_receive  # type: ignore[attr-defined]


async def guard_request(request: Request, call_next) -> Response:
    settings = request.app.state.settings
    if not is_local_request(request):
        return JSONResponse({"detail": "local access only"}, status_code=403)
    try:
        content_length = _content_length(request.headers.get("content-length"))
    except ValueError:
        return JSONResponse({"detail": "invalid content-length"}, status_code=400)
    if content_length and content_length > settings.max_request_body_bytes:
        return JSONResponse({"detail": "request body too large"}, status_code=413)
    if request.method in WRITE_METHODS and (
        not same_origin_write_allowed(request) or not csrf_allowed(request)
    ):
        return JSONResponse({"detail": "same-origin CSRF check failed"}, status_code=403)
    semaphore = request.app.state.http_semaphore
    if getattr(semaphore, "_value", 0) <= 0:
        return JSONResponse({"detail": "too many concurrent requests"}, status_code=429)
    async with semaphore:
        try:
            if request.method in WRITE_METHODS:
                await _buffer_request_body(request, max_bytes=settings.max_request_body_bytes)
            return await call_next(request)
        except RequestBodyTooLarge:
            return JSONResponse({"detail": "request body too large"}, status_code=413)
