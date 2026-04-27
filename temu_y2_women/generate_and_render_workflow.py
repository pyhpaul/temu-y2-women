from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from temu_y2_women.image_generation_output import ImageProvider
from temu_y2_women.image_generation_workflow import render_dress_concept_image
from temu_y2_women.orchestrator import generate_dress_concept

_CONCEPT_RESULT_FILENAME = "concept_result.json"

ImageProviderFactory = Callable[[], ImageProvider]


def generate_and_render_dress_concept(
    request_path: Path,
    output_dir: Path,
    provider_factory: ImageProviderFactory,
) -> dict[str, Any]:
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


def _load_request_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload
    raise ValueError("generate-and-render input root must be an object")


def _write_concept_result(output_dir: Path, concept_result: dict[str, Any]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / _CONCEPT_RESULT_FILENAME
    result_path.write_text(json.dumps(concept_result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result_path
