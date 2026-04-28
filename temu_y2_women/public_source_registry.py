from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from temu_y2_women.errors import GenerationError


_SUPPORTED_SOURCE_TYPES = {"public_editorial_web", "public_roundup_web"}
_SUPPORTED_MARKETS = {"US"}
_SUPPORTED_CATEGORIES = {"dress"}
_SUPPORTED_FETCH_MODES = {"html"}
_SUPPORTED_PRICE_BANDS = {"low", "mid", "high"}
_SUPPORTED_PIPELINE_MODES = {"editorial_text", "roundup_image_cards"}


def load_public_source_registry(path: Path) -> list[dict[str, Any]]:
    payload = _load_json_object(path)
    _require_schema_version(path, payload)
    sources = payload.get("sources")
    if not isinstance(sources, list):
        raise _registry_error(path, "sources", "source registry must contain a 'sources' array")
    return _validate_sources(path, sources)


def select_public_sources(
    registry: list[dict[str, Any]],
    source_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    if not source_ids:
        return list(registry)
    selected: list[dict[str, Any]] = []
    enabled_lookup = {str(source["source_id"]): source for source in registry}
    for source_id in _ordered_source_ids(source_ids):
        source = enabled_lookup.get(source_id)
        if source is None:
            raise GenerationError(
                code="INVALID_PUBLIC_SOURCE_SELECTION",
                message="source selection contains unknown source_id",
                details={"source_id": source_id},
            )
        selected.append(source)
    return selected


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload
    raise _registry_error(path, "root", "source registry root must be an object")


def _require_schema_version(path: Path, payload: dict[str, Any]) -> None:
    if payload.get("schema_version") == "public-source-registry-v1":
        return
    raise _registry_error(path, "schema_version", "unsupported source registry schema")


def _validate_sources(path: Path, sources: list[Any]) -> list[dict[str, Any]]:
    seen_ids: set[str] = set()
    validated: list[dict[str, Any]] = []
    for index, source in enumerate(sources):
        validated_source = _validate_source_record(path, index, source, seen_ids)
        if validated_source["enabled"]:
            validated.append(validated_source)
    return validated


def _validate_source_record(path: Path, index: int, source: Any, seen_ids: set[str]) -> dict[str, Any]:
    if not isinstance(source, dict):
        raise _registry_error(path, "record", "source record must be an object", index)
    required = _required_fields()
    missing = sorted(required.difference(source.keys()))
    if missing:
        raise _registry_error(path, "record", f"source record missing required fields: {missing}", index)
    source_id = _require_string(path, index, source, "source_id")
    if source_id in seen_ids:
        raise _registry_error(path, "source_id", "source_id must be unique", index)
    seen_ids.add(source_id)
    _require_url(path, index, source)
    _require_allowed(path, index, source, "source_type", _SUPPORTED_SOURCE_TYPES)
    _require_allowed(path, index, source, "target_market", _SUPPORTED_MARKETS)
    _require_allowed(path, index, source, "category", _SUPPORTED_CATEGORIES)
    _require_allowed(path, index, source, "fetch_mode", _SUPPORTED_FETCH_MODES)
    _require_allowed(path, index, source, "default_price_band", _SUPPORTED_PRICE_BANDS)
    _require_allowed(path, index, source, "pipeline_mode", _SUPPORTED_PIPELINE_MODES)
    _require_string(path, index, source, "adapter_id")
    _require_positive_int(path, index, source, "priority")
    _require_positive_number(path, index, source, "weight")
    if not isinstance(source["enabled"], bool):
        raise _registry_error(path, "enabled", "enabled must be a boolean", index)
    _require_roundup_fields(path, index, source)
    return dict(source)


def _required_fields() -> set[str]:
    return {
        "source_id",
        "source_type",
        "source_url",
        "target_market",
        "category",
        "fetch_mode",
        "adapter_id",
        "default_price_band",
        "pipeline_mode",
        "priority",
        "weight",
        "enabled",
    }


def _require_roundup_fields(path: Path, index: int, source: dict[str, Any]) -> None:
    if source["pipeline_mode"] != "roundup_image_cards":
        return
    _require_positive_int(path, index, source, "card_limit")
    _require_positive_int(path, index, source, "aggregation_threshold")
    _require_string(path, index, source, "observation_model")


def _require_string(path: Path, index: int, source: dict[str, Any], field: str) -> str:
    value = source.get(field)
    if isinstance(value, str) and value.strip():
        return value
    raise _registry_error(path, field, f"field '{field}' must be a non-empty string", index)


def _require_allowed(
    path: Path,
    index: int,
    source: dict[str, Any],
    field: str,
    allowed: set[str],
) -> None:
    value = _require_string(path, index, source, field)
    if value in allowed:
        return
    raise _registry_error(path, field, f"field '{field}' contains unsupported value", index, value)


def _require_positive_int(path: Path, index: int, source: dict[str, Any], field: str) -> None:
    value = source.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise _registry_error(path, field, f"field '{field}' must be a positive integer", index, value)


def _require_positive_number(path: Path, index: int, source: dict[str, Any], field: str) -> None:
    value = source.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise _registry_error(path, field, f"field '{field}' must be a positive number", index, value)


def _require_url(path: Path, index: int, source: dict[str, Any]) -> None:
    source_url = _require_string(path, index, source, "source_url")
    if source_url.startswith("https://"):
        return
    raise _registry_error(path, "source_url", "field 'source_url' must be an https URL", index, source_url)


def _registry_error(
    path: Path,
    field: str,
    message: str,
    index: int | None = None,
    value: Any | None = None,
) -> GenerationError:
    details: dict[str, Any] = {"path": str(path), "field": field}
    if index is not None:
        details["index"] = index
    if value is not None:
        details["value"] = value
    return GenerationError(code="INVALID_PUBLIC_SOURCE_REGISTRY", message=message, details=details)


def _ordered_source_ids(source_ids: list[str]) -> list[str]:
    ordered: list[str] = []
    for source_id in source_ids:
        if source_id not in ordered:
            ordered.append(source_id)
    return ordered
