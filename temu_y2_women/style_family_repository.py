from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from temu_y2_women.errors import GenerationError
from temu_y2_women.evidence_repository import (
    build_active_values_by_slot,
    load_elements,
    load_evidence_taxonomy,
)
from temu_y2_women.models import StyleFamilyProfile

_DEFAULT_STYLE_FAMILIES_PATH = Path("data/mvp/dress/style_families.json")
_REQUIRED_FIELDS = {
    "style_family_id",
    "status",
    "fallback_reason",
    "hard_slot_values",
    "soft_slot_values",
    "blocked_slot_values",
    "prompt_shell",
}
_PROMPT_SHELL_FIELDS = {
    "subject_hint",
    "scene_hint",
    "lighting_hint",
    "styling_hint",
    "constraint_hints",
}


def load_style_families(
    path: Path = _DEFAULT_STYLE_FAMILIES_PATH,
    elements_path: Path = Path("data/mvp/dress/elements.json"),
    taxonomy_path: Path = Path("data/mvp/dress/evidence_taxonomy.json"),
) -> tuple[StyleFamilyProfile, ...]:
    taxonomy = load_evidence_taxonomy(taxonomy_path)
    elements = load_elements(elements_path, taxonomy_path=taxonomy_path)
    active_values_by_slot = build_active_values_by_slot(elements)
    records = _load_style_family_records(path)
    profiles = [
        _build_profile(
            record=record,
            taxonomy=taxonomy,
            active_values_by_slot=active_values_by_slot,
            path=path,
            index=index,
        )
        for index, record in enumerate(records)
        if record.get("status") == "active"
    ]
    return tuple(profiles)


def _load_style_family_records(path: Path) -> list[dict[str, Any]]:
    payload = _load_json_object(path)
    records = payload.get("style_families")
    if not isinstance(records, list):
        raise GenerationError(
            code="INVALID_STYLE_FAMILY_CONFIG",
            message="style family store must contain a 'style_families' array",
            details={"path": str(path)},
        )
    return [*_validate_record_objects(path, records)]


def _validate_record_objects(path: Path, records: list[Any]) -> list[dict[str, Any]]:
    validated: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise GenerationError(
                code="INVALID_STYLE_FAMILY_CONFIG",
                message="style family record must be an object",
                details={"path": str(path), "index": index},
            )
        missing = sorted(_REQUIRED_FIELDS.difference(record.keys()))
        if missing:
            raise GenerationError(
                code="INVALID_STYLE_FAMILY_CONFIG",
                message="style family record is missing required fields",
                details={"path": str(path), "index": index, "missing": missing},
            )
        validated.append(record)
    return validated


def _build_profile(
    record: dict[str, Any],
    taxonomy: dict[str, Any],
    active_values_by_slot: dict[str, set[str]],
    path: Path,
    index: int,
) -> StyleFamilyProfile:
    prompt_shell = _validate_prompt_shell(path, index, record["prompt_shell"])
    return StyleFamilyProfile(
        style_family_id=str(record["style_family_id"]),
        hard_slot_values=_validate_slot_map(
            path,
            index,
            "hard_slot_values",
            record["hard_slot_values"],
            taxonomy,
            active_values_by_slot,
        ),
        soft_slot_values=_validate_slot_map(
            path,
            index,
            "soft_slot_values",
            record["soft_slot_values"],
            taxonomy,
            active_values_by_slot,
        ),
        blocked_slot_values=_validate_slot_map(
            path,
            index,
            "blocked_slot_values",
            record["blocked_slot_values"],
            taxonomy,
            active_values_by_slot,
        ),
        subject_hint=prompt_shell["subject_hint"],
        scene_hint=prompt_shell["scene_hint"],
        lighting_hint=prompt_shell["lighting_hint"],
        styling_hint=prompt_shell["styling_hint"],
        constraint_hints=tuple(prompt_shell["constraint_hints"]),
        fallback_reason=str(record["fallback_reason"]),
        status=str(record["status"]),
    )


def _validate_slot_map(
    path: Path,
    index: int,
    field: str,
    slot_map: Any,
    taxonomy: dict[str, Any],
    active_values_by_slot: dict[str, set[str]],
) -> dict[str, tuple[str, ...]]:
    if not isinstance(slot_map, dict):
        raise GenerationError(
            code="INVALID_STYLE_FAMILY_CONFIG",
            message=f"style family field '{field}' must be an object",
            details={"path": str(path), "index": index, "field": field},
        )
    allowed_slots = {item.casefold() for item in taxonomy["allowed_slots"]}
    validated: dict[str, tuple[str, ...]] = {}
    for slot, values in slot_map.items():
        canonical_slot = _canonicalize(str(slot))
        if canonical_slot not in allowed_slots:
            raise GenerationError(
                code="INVALID_STYLE_FAMILY_CONFIG",
                message="style family references an unknown slot",
                details={"path": str(path), "index": index, "field": field, "slot": slot},
            )
        validated[str(slot)] = _validate_slot_values(
            path=path,
            index=index,
            field=field,
            slot=str(slot),
            values=values,
            active_values=active_values_by_slot.get(str(slot), set()),
        )
    return validated


def _validate_slot_values(
    path: Path,
    index: int,
    field: str,
    slot: str,
    values: Any,
    active_values: set[str],
) -> tuple[str, ...]:
    if not isinstance(values, list) or any(not isinstance(item, str) or not item for item in values):
        raise GenerationError(
            code="INVALID_STYLE_FAMILY_CONFIG",
            message="style family slot values must be non-empty string arrays",
            details={"path": str(path), "index": index, "field": field, "slot": slot},
        )
    unknown = _unknown_values(values, active_values, allow_wildcard=field == "blocked_slot_values")
    if unknown:
        raise GenerationError(
            code="INVALID_STYLE_FAMILY_CONFIG",
            message="style family references unknown active element values",
            details={"path": str(path), "index": index, "field": field, "slot": slot, "values": unknown},
        )
    return tuple(values)


def _validate_prompt_shell(path: Path, index: int, prompt_shell: Any) -> dict[str, Any]:
    if not isinstance(prompt_shell, dict):
        raise GenerationError(
            code="INVALID_STYLE_FAMILY_CONFIG",
            message="style family prompt_shell must be an object",
            details={"path": str(path), "index": index, "field": "prompt_shell"},
        )
    missing = sorted(_PROMPT_SHELL_FIELDS.difference(prompt_shell.keys()))
    if missing:
        raise GenerationError(
            code="INVALID_STYLE_FAMILY_CONFIG",
            message="style family prompt_shell is missing required fields",
            details={"path": str(path), "index": index, "missing": missing},
        )
    constraint_hints = prompt_shell["constraint_hints"]
    if not isinstance(constraint_hints, list) or any(not isinstance(item, str) or not item for item in constraint_hints):
        raise GenerationError(
            code="INVALID_STYLE_FAMILY_CONFIG",
            message="style family constraint_hints must be a list of non-empty strings",
            details={"path": str(path), "index": index, "field": "constraint_hints"},
        )
    for field in _PROMPT_SHELL_FIELDS.difference({"constraint_hints"}):
        value = prompt_shell[field]
        if not isinstance(value, str) or not value:
            raise GenerationError(
                code="INVALID_STYLE_FAMILY_CONFIG",
                message=f"style family prompt_shell field '{field}' must be a non-empty string",
                details={"path": str(path), "index": index, "field": field},
            )
    return dict(prompt_shell)


def _unknown_values(values: list[str], active_values: set[str], allow_wildcard: bool) -> list[str]:
    canonical_active = {_canonicalize(item) for item in active_values}
    return [
        item
        for item in values
        if not (allow_wildcard and item == "*")
        and _canonicalize(item) not in canonical_active
    ]


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise GenerationError(
            code="INVALID_STYLE_FAMILY_CONFIG",
            message="style family file must contain valid JSON",
            details={"path": str(path), "line": error.lineno, "column": error.colno},
        ) from error
    if not isinstance(payload, dict):
        raise GenerationError(
            code="INVALID_STYLE_FAMILY_CONFIG",
            message="style family store root must be an object",
            details={"path": str(path)},
        )
    return payload


def _canonicalize(value: str) -> str:
    return value.strip().casefold()
