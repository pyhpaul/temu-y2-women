from __future__ import annotations

from base64 import b64decode
from dataclasses import dataclass
import json
from typing import Sequence
from urllib.parse import urlparse

from temu_y2_women.image_gateway_smoke_http import GatewayHttpResult, GatewaySmokeHttpClient


_REFERENCE_IMAGE_BYTES = b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4////fwAJ+wP9KobjigAAAABJRU5ErkJggg=="
)
_GENERATION_PROMPT = "gateway smoke check image generation"
_EDIT_PROMPT = "gateway smoke check image edit"


@dataclass(frozen=True, slots=True)
class GatewaySmokeSettings:
    base_url: str
    model: str
    anchor_api_key: str
    expansion_api_key: str
    timeout_sec: float


@dataclass(frozen=True, slots=True)
class GatewaySmokeCheck:
    check_id: str
    method: str
    path: str
    credential_route: str
    request_kind: str


DEFAULT_SMOKE_CHECKS = (
    GatewaySmokeCheck("models", "GET", "/models", "anchor", "models"),
    GatewaySmokeCheck("generate-anchor", "POST", "/images/generations", "anchor", "generate"),
    GatewaySmokeCheck("generate-expansion", "POST", "/images/generations", "expansion", "generate"),
    GatewaySmokeCheck("edit-anchor", "POST", "/images/edits", "anchor", "edit"),
    GatewaySmokeCheck("edit-expansion", "POST", "/images/edits", "expansion", "edit"),
)
VALID_SMOKE_CHECK_IDS = tuple(check.check_id for check in DEFAULT_SMOKE_CHECKS)


def run_gateway_smoke(
    settings: GatewaySmokeSettings,
    *,
    check_ids: Sequence[str] | None = None,
    http_client: GatewaySmokeHttpClient | None = None,
) -> dict[str, object]:
    selected_checks = _selected_checks(check_ids)
    client = http_client or GatewaySmokeHttpClient()
    results = [_run_check(settings, check, client) for check in selected_checks]
    return {
        "schema_version": "image-gateway-smoke-report-v1",
        "model": settings.model,
        "base_url": settings.base_url.rstrip("/"),
        "timeout_sec": settings.timeout_sec,
        "requested_checks": [check.check_id for check in selected_checks],
        "checks": results,
        "summary": _summary(results),
    }


def _selected_checks(check_ids: Sequence[str] | None) -> tuple[GatewaySmokeCheck, ...]:
    if not check_ids:
        return DEFAULT_SMOKE_CHECKS
    lookup = {check.check_id: check for check in DEFAULT_SMOKE_CHECKS}
    return tuple(_required_check(check_id, lookup) for check_id in check_ids)


def _required_check(
    check_id: str,
    lookup: dict[str, GatewaySmokeCheck],
) -> GatewaySmokeCheck:
    try:
        return lookup[check_id]
    except KeyError as error:
        raise ValueError(f"unsupported smoke check: {check_id}") from error


def _run_check(
    settings: GatewaySmokeSettings,
    check: GatewaySmokeCheck,
    http_client: GatewaySmokeHttpClient,
) -> dict[str, object]:
    raw_result = _dispatch_http_check(settings, check, http_client)
    return {
        "check_id": check.check_id,
        "route": _route_label(settings.base_url, check),
        "credential_route": check.credential_route,
        "status": "success" if _is_success(raw_result) else "failed",
        "ok": _is_success(raw_result),
        "http_code": raw_result.http_code,
        "elapsed_seconds": raw_result.elapsed_seconds,
        "error_type": None if _is_success(raw_result) else _error_type(raw_result),
        "response_excerpt": "" if _is_success(raw_result) else _response_excerpt(raw_result.body_text),
    }


def _dispatch_http_check(
    settings: GatewaySmokeSettings,
    check: GatewaySmokeCheck,
    http_client: GatewaySmokeHttpClient,
) -> GatewayHttpResult:
    url = f"{settings.base_url.rstrip('/')}{check.path}"
    api_key = _api_key_for_route(settings, check.credential_route)
    if check.request_kind == "models":
        return http_client.get_json(url, api_key=api_key, timeout_sec=settings.timeout_sec)
    if check.request_kind == "generate":
        return http_client.post_json(
            url,
            api_key=api_key,
            payload=_generation_payload(settings.model),
            timeout_sec=settings.timeout_sec,
        )
    return http_client.post_multipart(
        url,
        api_key=api_key,
        fields=_edit_fields(settings.model),
        file_field="image",
        filename="reference.png",
        file_bytes=_REFERENCE_IMAGE_BYTES,
        mime_type="image/png",
        timeout_sec=settings.timeout_sec,
    )


def _api_key_for_route(settings: GatewaySmokeSettings, credential_route: str) -> str:
    if credential_route == "expansion":
        return settings.expansion_api_key
    return settings.anchor_api_key


def _generation_payload(model: str) -> dict[str, str]:
    return {
        "model": model,
        "prompt": _GENERATION_PROMPT,
        "response_format": "b64_json",
    }


def _edit_fields(model: str) -> dict[str, str]:
    return {
        "model": model,
        "prompt": _EDIT_PROMPT,
        "response_format": "b64_json",
        "input_fidelity": "high",
    }


def _route_label(base_url: str, check: GatewaySmokeCheck) -> str:
    prefix = urlparse(base_url).path.rstrip("/")
    return f"{check.method} {prefix}{check.path}" if prefix else f"{check.method} {check.path}"


def _is_success(result: GatewayHttpResult) -> bool:
    return result.http_code is not None and 200 <= result.http_code < 300


def _error_type(result: GatewayHttpResult) -> str:
    if result.timed_out:
        return "timeout"
    if result.transport_error == "network_error":
        return "network_error"
    parsed = _error_type_from_body(result.body_text)
    if parsed:
        return parsed
    return "http_error" if result.http_code is not None else "unknown_error"


def _error_type_from_body(body_text: str) -> str | None:
    try:
        payload = json.loads(body_text)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict):
        error_payload = payload.get("error")
        if isinstance(error_payload, dict):
            error_type = error_payload.get("type")
            if isinstance(error_type, str) and error_type.strip():
                return error_type.strip()
        payload_type = payload.get("type")
        if isinstance(payload_type, str) and payload_type.strip():
            return payload_type.strip()
    return None


def _response_excerpt(body_text: str) -> str:
    compact = " ".join(body_text.split())
    return compact[:280]


def _summary(results: Sequence[dict[str, object]]) -> dict[str, int]:
    passed = sum(1 for result in results if result["ok"])
    return {
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
    }
