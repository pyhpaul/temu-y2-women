from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from temu_y2_women.errors import GenerationError
from temu_y2_women.image_generation_output import ImageProvider
from temu_y2_women.image_generation_workflow import render_dress_concept_image
from temu_y2_women.orchestrator import generate_dress_concept

_CONCEPT_RESULT_FILENAME = "concept_result.json"
_INVALID_INPUT_CODE = "INVALID_GENERATE_AND_RENDER_INPUT"

ImageProviderFactory = Callable[[], ImageProvider]


def generate_and_render_dress_concept(
    request_path: Path,
    output_dir: Path,
    provider_factory: ImageProviderFactory,
) -> dict[str, Any]:
    try:
        payload = _load_request_payload(request_path)
        concept_result = generate_dress_concept(payload)
        if "error" in concept_result:
            return concept_result
        result_path = _write_concept_result(output_dir, concept_result)
        return render_dress_concept_image(
            result_path=result_path,
            output_dir=output_dir,
            provider=provider_factory(),
        )
    except GenerationError as error:
        return error.to_dict()
    except OSError as error:
        return _concept_result_output_error(output_dir, error).to_dict()


def _load_request_payload(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise _invalid_input_error(path, "request", "generate-and-render input could not be read") from error
    except json.JSONDecodeError as error:
        raise _invalid_input_error(path, "request", "generate-and-render input must contain valid JSON") from error
    if isinstance(payload, dict):
        return payload
    raise _invalid_input_error(path, "request", "generate-and-render input root must be an object")


def _write_concept_result(output_dir: Path, concept_result: dict[str, Any]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / _CONCEPT_RESULT_FILENAME
    temp_path = result_path.with_suffix(f"{result_path.suffix}.tmp")
    temp_path.write_text(json.dumps(concept_result, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        temp_path.replace(result_path)
    except OSError:
        _cleanup_file(temp_path)
        raise
    return result_path


def _cleanup_file(path: Path) -> None:
    if path.exists():
        path.unlink()


def _invalid_input_error(path: Path, field: str, message: str) -> GenerationError:
    return GenerationError(
        code=_INVALID_INPUT_CODE,
        message=message,
        details={"path": str(path), "field": field},
    )


def _concept_result_output_error(output_dir: Path, error: OSError) -> GenerationError:
    return GenerationError(
        code="CONCEPT_RESULT_OUTPUT_FAILED",
        message="failed to write concept result output",
        details={"path": str(output_dir / _CONCEPT_RESULT_FILENAME), "reason": str(error)},
    )
