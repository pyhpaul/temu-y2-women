from __future__ import annotations

from dataclasses import dataclass
import json
import socket
from time import perf_counter
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import uuid


@dataclass(frozen=True, slots=True)
class GatewayHttpResult:
    http_code: int | None
    body_text: str
    elapsed_seconds: float
    timed_out: bool = False
    transport_error: str | None = None


class GatewaySmokeHttpClient:
    def __init__(self, *, transport: Callable[..., Any] = urlopen) -> None:
        self._transport = transport

    def get_json(self, url: str, *, api_key: str, timeout_sec: float) -> GatewayHttpResult:
        return _perform_request(
            _build_request(url, api_key=api_key, method="GET"),
            timeout_sec,
            self._transport,
        )

    def post_json(
        self,
        url: str,
        *,
        api_key: str,
        payload: Mapping[str, object],
        timeout_sec: float,
    ) -> GatewayHttpResult:
        return _perform_request(
            _build_request(
                url,
                api_key=api_key,
                method="POST",
                data=json.dumps(payload).encode("utf-8"),
                content_type="application/json",
            ),
            timeout_sec,
            self._transport,
        )

    def post_multipart(
        self,
        url: str,
        *,
        api_key: str,
        fields: Mapping[str, str],
        file_field: str,
        filename: str,
        file_bytes: bytes,
        mime_type: str,
        timeout_sec: float,
    ) -> GatewayHttpResult:
        boundary = _multipart_boundary()
        return _perform_request(
            _build_request(
                url,
                api_key=api_key,
                method="POST",
                data=_build_multipart_payload(
                    boundary,
                    fields,
                    file_field,
                    filename,
                    file_bytes,
                    mime_type,
                ),
                content_type=f"multipart/form-data; boundary={boundary}",
            ),
            timeout_sec,
            self._transport,
        )


def _perform_request(
    request: Request,
    timeout_sec: float,
    transport: Callable[..., Any],
) -> GatewayHttpResult:
    start = perf_counter()
    try:
        with transport(request, timeout=timeout_sec) as response:
            return GatewayHttpResult(
                http_code=response.getcode(),
                body_text=_read_text(response),
                elapsed_seconds=_elapsed_seconds(start),
            )
    except HTTPError as error:
        return GatewayHttpResult(
            http_code=error.code,
            body_text=_read_text(error),
            elapsed_seconds=_elapsed_seconds(start),
        )
    except URLError as error:
        return _url_error_result(error, start)
    except (TimeoutError, socket.timeout) as error:
        return _timeout_result(str(error), start)


def _build_request(
    url: str,
    *,
    api_key: str,
    method: str,
    data: bytes | None = None,
    content_type: str | None = None,
) -> Request:
    return Request(
        url=url,
        data=data,
        headers=_request_headers(api_key, content_type),
        method=method,
    )


def _request_headers(api_key: str, content_type: str | None) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def _read_text(response: Any) -> str:
    payload = response.read()
    if isinstance(payload, bytes):
        return payload.decode("utf-8", errors="replace")
    return str(payload)


def _url_error_result(error: URLError, start: float) -> GatewayHttpResult:
    reason = error.reason
    if _is_timeout_reason(reason):
        return _timeout_result(str(reason), start)
    return GatewayHttpResult(
        http_code=None,
        body_text=str(reason),
        elapsed_seconds=_elapsed_seconds(start),
        transport_error="network_error",
    )


def _timeout_result(message: str, start: float) -> GatewayHttpResult:
    return GatewayHttpResult(
        http_code=None,
        body_text=message or "timed out",
        elapsed_seconds=_elapsed_seconds(start),
        timed_out=True,
        transport_error="timeout",
    )


def _is_timeout_reason(reason: object) -> bool:
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return True
    return "timed out" in str(reason).lower()


def _elapsed_seconds(start: float) -> float:
    return round(perf_counter() - start, 2)


def _multipart_boundary() -> str:
    return f"----temuY2Smoke{uuid.uuid4().hex}"


def _build_multipart_payload(
    boundary: str,
    fields: Mapping[str, str],
    file_field: str,
    filename: str,
    file_bytes: bytes,
    mime_type: str,
) -> bytes:
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend(_text_part(boundary, name, value))
    chunks.extend(_file_part(boundary, file_field, filename, file_bytes, mime_type))
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks)


def _text_part(boundary: str, name: str, value: str) -> list[bytes]:
    return [
        f"--{boundary}\r\n".encode("utf-8"),
        f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"),
        value.encode("utf-8"),
        b"\r\n",
    ]


def _file_part(
    boundary: str,
    field_name: str,
    filename: str,
    file_bytes: bytes,
    mime_type: str,
) -> list[bytes]:
    return [
        f"--{boundary}\r\n".encode("utf-8"),
        (
            f'Content-Disposition: form-data; name="{field_name}"; '
            f'filename="{filename}"\r\n'
        ).encode("utf-8"),
        f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"),
        file_bytes,
        b"\r\n",
    ]
