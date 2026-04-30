from __future__ import annotations

from base64 import b64decode
import json
import os
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Protocol
from urllib.parse import urlparse

from temu_y2_women.errors import GenerationError
from temu_y2_women.image_generation_output import ImageProviderResult

_CURL_HTTP_CODE_MARKER = "HTTP_CODE:"
_CURL_ONLY_HOSTS = frozenset({"callxyq.xyz"})


class CurlGatewayConfig(Protocol):
    api_key: str
    base_url: str | None
    model: str
    size: str
    quality: str
    background: str
    style: str


def uses_curl_transport(base_url: str | None) -> bool:
    host = urlparse(base_url or "").hostname or ""
    return host.lower() in _CURL_ONLY_HOSTS


def render_generate_with_curl(
    *,
    config: CurlGatewayConfig,
    prompt: str,
    curl_runner: Callable[..., Any],
) -> ImageProviderResult:
    payload = _generation_payload(config, prompt)
    response = _run_curl_json_request(
        curl_runner,
        _required_base_url(config),
        config.api_key,
        "/images/generations",
        payload,
    )
    return _provider_result_from_gateway_payload(response, config, curl_runner)


def render_edit_with_curl(
    *,
    config: CurlGatewayConfig,
    prompt: str,
    reference_image_bytes: bytes,
    curl_runner: Callable[..., Any],
) -> ImageProviderResult:
    reference_path = _write_reference_image_file(reference_image_bytes)
    try:
        response = _run_curl_multipart_request(
            curl_runner,
            _required_base_url(config),
            config.api_key,
            "/images/edits",
            _edit_fields(config, prompt),
            reference_path,
        )
    finally:
        _cleanup_reference_image_file(reference_path)
    return _provider_result_from_gateway_payload(response, config, curl_runner)


def _provider_result_from_gateway_payload(
    payload: dict[str, Any],
    config: CurlGatewayConfig,
    curl_runner: Callable[..., Any],
) -> ImageProviderResult:
    data = payload.get("data", [])
    image_data = data[0] if isinstance(data, list) and data else {}
    if isinstance(image_data, dict):
        b64_json = image_data.get("b64_json", "")
        if b64_json:
            return _provider_result_from_b64_json(b64_json, config)
        url = image_data.get("url", "")
        if isinstance(url, str) and url.strip():
            return ImageProviderResult(
                image_bytes=_download_image_bytes(curl_runner, url.strip()),
                mime_type="image/png",
                provider_name="openai",
                model=config.model,
                base_url=config.base_url,
            )
    return _provider_result_from_payload(payload, config)


def _provider_result_from_payload(
    payload: dict[str, Any],
    config: CurlGatewayConfig,
) -> ImageProviderResult:
    data = payload.get("data", [])
    image_data = data[0] if isinstance(data, list) and data else {}
    b64_json = image_data.get("b64_json", "") if isinstance(image_data, dict) else ""
    return _provider_result_from_b64_json(b64_json, config)


def _provider_result_from_b64_json(
    b64_json: str,
    config: CurlGatewayConfig,
) -> ImageProviderResult:
    if not b64_json:
        raise GenerationError(
            code="IMAGE_PROVIDER_FAILED",
            message="OpenAI image provider returned no image payload",
            details={"provider": "openai"},
        )
    return ImageProviderResult(
        image_bytes=b64decode(b64_json),
        mime_type="image/png",
        provider_name="openai",
        model=config.model,
        base_url=config.base_url,
    )


def _uses_light_gateway_profile(base_url: str | None) -> bool:
    return uses_curl_transport(base_url)


def _required_base_url(config: CurlGatewayConfig) -> str:
    if config.base_url:
        return config.base_url.rstrip("/")
    raise GenerationError(
        code="INVALID_IMAGE_PROVIDER_CONFIG",
        message="OpenAI image provider requires a base_url for the current gateway transport",
        details={"provider": "openai", "field": "base_url"},
    )


def _generation_payload(config: CurlGatewayConfig, prompt: str) -> dict[str, str]:
    payload = {
        "model": config.model,
        "prompt": prompt,
        "response_format": "b64_json",
    }
    if _uses_light_gateway_profile(config.base_url):
        return payload
    payload.update(
        {
            "size": config.size,
            "quality": config.quality,
            "background": config.background,
            "style": config.style,
            "output_format": "png",
        }
    )
    return payload


def _edit_fields(config: CurlGatewayConfig, prompt: str) -> dict[str, str]:
    fields = {
        "model": config.model,
        "prompt": prompt,
        "input_fidelity": "high",
        "response_format": "b64_json",
    }
    if _uses_light_gateway_profile(config.base_url):
        return fields
    fields.update(
        {
            "size": config.size,
            "quality": config.quality,
            "background": config.background,
            "output_format": "png",
        }
    )
    return fields


def _run_curl_json_request(
    curl_runner: Callable[..., Any],
    base_url: str,
    api_key: str,
    path: str,
    payload: dict[str, str],
) -> dict[str, Any]:
    command = _curl_command(base_url, api_key, path)
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
    return _run_curl_command(
        curl_runner,
        command,
        base_url=base_url,
        path=path,
        input_text=json.dumps(payload, separators=(",", ":")),
    )


def _run_curl_multipart_request(
    curl_runner: Callable[..., Any],
    base_url: str,
    api_key: str,
    path: str,
    fields: dict[str, str],
    reference_path: str,
) -> dict[str, Any]:
    command = _curl_command(base_url, api_key, path)
    for key, value in fields.items():
        command.extend(["-F", f"{key}={value}"])
    command.extend(
        [
            "-F",
            f"image=@{reference_path};type=image/png;filename=reference.png",
            "-w",
            f"\n{_CURL_HTTP_CODE_MARKER}%{{http_code}}",
        ]
    )
    return _run_curl_command(curl_runner, command, base_url=base_url, path=path)


def _curl_command(base_url: str, api_key: str, path: str) -> list[str]:
    binary = "curl.exe" if os.name == "nt" else "curl"
    return [
        binary,
        "-sS",
        "-X",
        "POST",
        f"{base_url}{path}",
        "-H",
        f"Authorization: Bearer {api_key}",
    ]


def _run_curl_command(
    curl_runner: Callable[..., Any],
    command: list[str],
    *,
    base_url: str,
    path: str,
    input_text: str | None = None,
) -> dict[str, Any]:
    result = curl_runner(command, capture_output=True, text=True, input=input_text)
    body_text, http_code = _split_curl_output(str(getattr(result, "stdout", "")))
    if 200 <= http_code < 300:
        return _load_gateway_payload(body_text)
    raise _curl_gateway_error(
        body_text=body_text,
        http_code=http_code,
        stderr=str(getattr(result, "stderr", "")),
        returncode=int(getattr(result, "returncode", 0)),
        base_url=base_url,
        path=path,
    )


def _split_curl_output(stdout_text: str) -> tuple[str, int]:
    body_text, separator, http_code = stdout_text.rpartition(f"\n{_CURL_HTTP_CODE_MARKER}")
    if separator and http_code.isdigit():
        return body_text, int(http_code)
    return stdout_text, 0


def _load_gateway_payload(body_text: str) -> dict[str, Any]:
    try:
        payload = json.loads(body_text)
    except json.JSONDecodeError as error:
        raise GenerationError(
            code="IMAGE_PROVIDER_FAILED",
            message="OpenAI-compatible gateway returned invalid JSON",
            details={"provider": "openai", "reason": str(error)},
        ) from error
    if isinstance(payload, dict):
        return payload
    raise GenerationError(
        code="IMAGE_PROVIDER_FAILED",
        message="OpenAI-compatible gateway returned an invalid response payload",
        details={"provider": "openai", "field": "response"},
    )


def _curl_gateway_error(
    *,
    body_text: str,
    http_code: int,
    stderr: str,
    returncode: int,
    base_url: str,
    path: str,
) -> GenerationError:
    detail = body_text.strip() or stderr.strip() or "curl request failed"
    return GenerationError(
        code="IMAGE_PROVIDER_FAILED",
        message="OpenAI-compatible gateway request failed",
        details=_gateway_error_details(
            base_url=base_url,
            path=path,
            http_code=http_code,
            returncode=returncode,
            detail=detail,
        ),
    )


def _gateway_error_details(
    *,
    base_url: str,
    path: str,
    http_code: int,
    returncode: int,
    detail: str,
) -> dict[str, Any]:
    details: dict[str, Any] = {
        "provider": "openai",
        "gateway_host": (urlparse(base_url).hostname or "").lower(),
        "gateway_route": path,
        "http_code": http_code,
        "returncode": returncode,
        "reason_type": _gateway_reason_type(detail),
        "reason": detail[:280],
    }
    if _is_reference_image_gateway_block(base_url, path, http_code, detail):
        details["gateway_error_category"] = "gateway_reference_image_blocked"
        details["hint"] = (
            "callxyq /images/edits accepts tiny or blank probes but may block real garment reference images"
        )
    return details


def _gateway_reason_type(detail: str) -> str:
    stripped = detail.lstrip().lower()
    if stripped.startswith("<!doctype html") or stripped.startswith("<html"):
        return "html_response"
    return "text_response"


def _is_reference_image_gateway_block(
    base_url: str,
    path: str,
    http_code: int,
    detail: str,
) -> bool:
    return (
        uses_curl_transport(base_url)
        and path == "/images/edits"
        and http_code == 403
        and _gateway_reason_type(detail) == "html_response"
    )


def _download_image_bytes(curl_runner: Callable[..., Any], url: str) -> bytes:
    binary = "curl.exe" if os.name == "nt" else "curl"
    result = curl_runner([binary, "-sS", url], capture_output=True)
    output = getattr(result, "stdout", b"")
    if isinstance(output, bytes):
        return output
    return str(output).encode("utf-8")


def _write_reference_image_file(reference_image_bytes: bytes) -> str:
    with NamedTemporaryFile(delete=False, suffix=".png") as handle:
        handle.write(reference_image_bytes)
        return handle.name


def _cleanup_reference_image_file(path: str) -> None:
    if os.path.exists(path):
        os.unlink(path)
