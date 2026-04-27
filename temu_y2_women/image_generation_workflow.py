from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from temu_y2_women.errors import GenerationError
from temu_y2_women.image_generation_output import ImageProvider, ImageProviderResult, load_dress_image_render_input

_REPORT_SCHEMA_VERSION = "image-render-report-v1"
_IMAGE_FILENAME = "rendered_image.png"
_REPORT_FILENAME = "image_render_report.json"


def render_dress_concept_image(
    result_path: Path,
    output_dir: Path,
    provider: ImageProvider,
) -> dict[str, Any]:
    try:
        render_input = load_dress_image_render_input(result_path)
        provider_result = _render_with_provider(provider, render_input)
        report = _build_render_report(render_input, output_dir, provider_result)
        _write_output_bundle(output_dir, provider_result.image_bytes, report)
        return report
    except GenerationError as error:
        return error.to_dict()
    except OSError as error:
        return _output_error(error).to_dict()


def _render_with_provider(provider: ImageProvider, render_input: Any) -> ImageProviderResult:
    try:
        return provider.render(render_input)
    except GenerationError:
        raise
    except Exception as error:
        raise GenerationError(
            code="IMAGE_PROVIDER_FAILED",
            message="image provider failed to render the requested image",
            details={"provider": provider.__class__.__name__, "reason": str(error)},
        ) from error


def _build_render_report(
    render_input: Any,
    output_dir: Path,
    provider_result: ImageProviderResult,
) -> dict[str, Any]:
    return {
        "schema_version": _REPORT_SCHEMA_VERSION,
        "category": render_input.category,
        "mode": render_input.mode,
        "source_result_path": str(render_input.source_result_path),
        "prompt_fingerprint": _fingerprint(render_input.prompt),
        "provider": provider_result.provider_name,
        "model": provider_result.model,
        "mime_type": provider_result.mime_type,
        "image_path": str(output_dir / _IMAGE_FILENAME),
        "report_path": str(output_dir / _REPORT_FILENAME),
        "rendered_at": _current_timestamp(),
    }


def _write_output_bundle(output_dir: Path, image_bytes: bytes, report: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    image_path = output_dir / _IMAGE_FILENAME
    report_path = output_dir / _REPORT_FILENAME
    staged_paths = _write_temp_outputs(image_path, image_bytes, report_path, report)
    published: list[Path] = []
    try:
        for temp_path, final_path in staged_paths:
            temp_path.replace(final_path)
            published.append(final_path)
    except OSError:
        _cleanup_paths([path for path, _ in staged_paths], published)
        raise


def _write_temp_outputs(
    image_path: Path,
    image_bytes: bytes,
    report_path: Path,
    report: dict[str, Any],
) -> list[tuple[Path, Path]]:
    image_temp = image_path.with_suffix(f"{image_path.suffix}.tmp")
    report_temp = report_path.with_suffix(f"{report_path.suffix}.tmp")
    image_temp.write_bytes(image_bytes)
    report_temp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return [(image_temp, image_path), (report_temp, report_path)]


def _cleanup_paths(temp_paths: list[Path], published_paths: list[Path]) -> None:
    for path in [*temp_paths, *published_paths]:
        if path.exists():
            path.unlink()


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _current_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _output_error(error: OSError) -> GenerationError:
    return GenerationError(
        code="IMAGE_RENDER_OUTPUT_FAILED",
        message="failed to write image render outputs",
        details={"path": str(getattr(error, "filename", ""))},
    )
