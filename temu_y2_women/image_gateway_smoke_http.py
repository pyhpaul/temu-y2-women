from __future__ import annotations

from dataclasses import dataclass
import json
import os
import socket
import subprocess
from tempfile import NamedTemporaryFile
from time import perf_counter
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import uuid

from temu_y2_women.image_gateway_curl import uses_curl_transport


_CURL_HTTP_CODE_MARKER = "HTTP_CODE:"


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


class GatewaySmokeCurlHttpClient:
    def __init__(self, *, curl_runner: Callable[..., Any] = subprocess.run) -> None:
        self._curl_runner = curl_runner

    def get_json(self, url: str, *, api_key: str, timeout_sec: float) -> GatewayHttpResult:
        command = _curl_command("GET", url, api_key)
        command.extend(["-w", f"\n{_CURL_HTTP_CODE_MARKER}%{{http_code}}"])
        return _perform_curl_request(
            command,
            timeout_sec,
            self._curl_runner,
        )

    def post_json(
        self,
        url: str,
        *,
        api_key: str,
        payload: Mapping[str, object],
        timeout_sec: float,
    ) -> GatewayHttpResult:
        command = _curl_command("POST", url, api_key)
        command.extend(
            [
                "-H",
                "Content-Type: application/json",
                "-d",
                "@-",
                "-w",
                f"\n{_CURL_HTTP_CODE_MARKER}%{{http_code}}",
            ]
        )
        return _perform_curl_request(
            command,
            timeout_sec,
            self._curl_runner,
            input_text=json.dumps(payload, separators=(",", ":")),
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
        file_path = _write_temp_file(filename, file_bytes)
        try:
            command = _curl_command("POST", url, api_key)
            for name, value in fields.items():
                command.extend(["-F", f"{name}={value}"])
            command.extend(
                [
                    "-F",
                    f"{file_field}=@{file_path};type={mime_type};filename={filename}",
                    "-w",
                    f"\n{_CURL_HTTP_CODE_MARKER}%{{http_code}}",
                ]
            )
            return _perform_curl_request(
                command,
                timeout_sec,
                self._curl_runner,
            )
        finally:
            _cleanup_temp_file(file_path)


def build_gateway_smoke_http_client(
    base_url: str,
    *,
    curl_runner: Callable[..., Any] = subprocess.run,
) -> GatewaySmokeHttpClient | GatewaySmokeCurlHttpClient:
    if uses_curl_transport(base_url):
        return GatewaySmokeCurlHttpClient(curl_runner=curl_runner)
    return GatewaySmokeHttpClient()


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


def _perform_curl_request(
    command: list[str],
    timeout_sec: float,
    curl_runner: Callable[..., Any],
    *,
    input_text: str | None = None,
) -> GatewayHttpResult:
    start = perf_counter()
    try:
        result = curl_runner(
            command,
            capture_output=True,
            text=True,
            input=input_text,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired as error:
        return _timeout_result(str(error), start)
    except OSError as error:
        return GatewayHttpResult(
            http_code=None,
            body_text=str(error),
            elapsed_seconds=_elapsed_seconds(start),
            transport_error="network_error",
        )
    body_text, http_code = _split_curl_output(str(getattr(result, "stdout", "")))
    if http_code <= 0:
        return _curl_transport_error_result(result, body_text, start)
    return GatewayHttpResult(
        http_code=http_code,
        body_text=body_text,
        elapsed_seconds=_elapsed_seconds(start),
    )


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


def _curl_command(method: str, url: str, api_key: str) -> list[str]:
    binary = "curl.exe" if os.name == "nt" else "curl"
    return [
        binary,
        "-sS",
        "-X",
        method,
        url,
        "-H",
        "Accept: application/json",
        "-H",
        f"Authorization: Bearer {api_key}",
    ]


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


def _curl_transport_error_result(result: Any, body_text: str, start: float) -> GatewayHttpResult:
    stderr = str(getattr(result, "stderr", ""))
    returncode = int(getattr(result, "returncode", 0))
    detail = body_text.strip() or stderr.strip() or f"curl exited with status {returncode}"
    return GatewayHttpResult(
        http_code=None,
        body_text=detail,
        elapsed_seconds=_elapsed_seconds(start),
        transport_error="network_error",
    )


def _split_curl_output(stdout_text: str) -> tuple[str, int]:
    body_text, separator, http_code = stdout_text.rpartition(f"\n{_CURL_HTTP_CODE_MARKER}")
    if separator and http_code.isdigit():
        return body_text, int(http_code)
    return stdout_text, 0


def _is_timeout_reason(reason: object) -> bool:
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return True
    return "timed out" in str(reason).lower()


def _elapsed_seconds(start: float) -> float:
    return round(perf_counter() - start, 2)


def _multipart_boundary() -> str:
    return f"----temuY2Smoke{uuid.uuid4().hex}"


def _write_temp_file(filename: str, file_bytes: bytes) -> str:
    suffix = os.path.splitext(filename)[1] or ".bin"
    with NamedTemporaryFile(delete=False, suffix=suffix) as handle:
        handle.write(file_bytes)
        return handle.name


def _cleanup_temp_file(path: str) -> None:
    if os.path.exists(path):
        os.unlink(path)


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
