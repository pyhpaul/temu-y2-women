from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Sequence

from temu_y2_women.errors import GenerationError
from temu_y2_women.image_generation_output import (
    ImageProvider,
    ImageProviderResult,
    ImageRenderInput,
    ImageRenderJob,
    load_dress_image_render_input,
)

_REPORT_SCHEMA_VERSION = "image-render-report-v1"
_REPORT_FILENAME = "image_render_report.json"


def render_dress_concept_image(
    result_path: Path,
    output_dir: Path,
    provider: ImageProvider,
    prompt_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    try:
        render_input = _filtered_render_input(
            load_dress_image_render_input(result_path),
            prompt_ids,
        )
        rendered_images = _render_bundle(provider, render_input)
        report = _build_render_report(render_input, output_dir, rendered_images)
        _write_output_bundle(output_dir, rendered_images, report)
        return report
    except GenerationError as error:
        return error.to_dict()
    except OSError as error:
        return _output_error(error).to_dict()


def _render_bundle(provider: ImageProvider, render_input: ImageRenderInput) -> list[dict[str, Any]]:
    rendered_images: list[dict[str, Any]] = []
    rendered_bytes: dict[str, bytes] = {}
    for job in render_input.render_jobs:
        provider_result = _render_job(provider, render_input, job, rendered_bytes)
        rendered_bytes[job.prompt_id] = provider_result.image_bytes
        rendered_images.append(_rendered_image_item(job, provider_result))
    return rendered_images


def _filtered_render_input(
    render_input: ImageRenderInput,
    prompt_ids: Sequence[str] | None,
) -> ImageRenderInput:
    requested = _prompt_id_filter(prompt_ids)
    if not requested:
        return render_input
    jobs = tuple(job for job in render_input.render_jobs if job.prompt_id in requested)
    if not jobs:
        raise GenerationError(
            code="INVALID_IMAGE_RENDER_INPUT",
            message="image render prompt filter matched no render jobs",
            details={"prompt_ids": sorted(requested)},
        )
    first_job = jobs[0]
    return ImageRenderInput(
        source_result_path=render_input.source_result_path,
        category=render_input.category,
        mode=render_input.mode,
        prompt=first_job.prompt,
        prompt_id=first_job.prompt_id,
        group=first_job.group,
        output_name=first_job.output_name,
        render_strategy=first_job.render_strategy,
        reference_prompt_id=first_job.reference_prompt_id,
        reference_image_bytes=render_input.reference_image_bytes,
        render_notes=render_input.render_notes,
        render_jobs=jobs,
    )


def _prompt_id_filter(prompt_ids: Sequence[str] | None) -> set[str]:
    if prompt_ids is None:
        return set()
    return {str(prompt_id).strip() for prompt_id in prompt_ids if str(prompt_id).strip()}


def _render_with_provider(provider: ImageProvider, render_input: ImageRenderInput) -> ImageProviderResult:
    try:
        return provider.render(render_input)
    except GenerationError:
        raise
    except Exception as error:
        raise _provider_error(provider, error) from error


def _render_job(
    provider: ImageProvider,
    render_input: ImageRenderInput,
    job: ImageRenderJob,
    rendered_bytes: dict[str, bytes],
) -> ImageProviderResult:
    return _render_with_provider(
        provider,
        _job_render_input(
            render_input,
            job,
            _reference_image_bytes(job, rendered_bytes),
        ),
    )


def _job_render_input(
    render_input: ImageRenderInput,
    job: ImageRenderJob,
    reference_image_bytes: bytes | None,
) -> ImageRenderInput:
    return ImageRenderInput(
        source_result_path=render_input.source_result_path,
        category=render_input.category,
        mode=render_input.mode,
        prompt=job.prompt,
        prompt_id=job.prompt_id,
        group=job.group,
        output_name=job.output_name,
        render_strategy=job.render_strategy,
        reference_prompt_id=job.reference_prompt_id,
        reference_image_bytes=reference_image_bytes,
        render_notes=render_input.render_notes,
        render_jobs=(job,),
    )


def _reference_image_bytes(
    job: ImageRenderJob,
    rendered_bytes: dict[str, bytes],
) -> bytes | None:
    if job.render_strategy != "edit":
        return None
    reference_prompt_id = job.reference_prompt_id
    if reference_prompt_id and reference_prompt_id in rendered_bytes:
        return rendered_bytes[reference_prompt_id]
    raise GenerationError(
        code="IMAGE_PROVIDER_FAILED",
        message="image edit reference prompt could not be resolved",
        details={
            "field": "reference_prompt_id",
            "prompt_id": job.prompt_id,
            "reference_prompt_id": reference_prompt_id,
            "render_strategy": job.render_strategy,
        },
    )


def _rendered_image_item(
    job: ImageRenderJob,
    provider_result: ImageProviderResult,
) -> dict[str, Any]:
    return {
        "prompt_id": job.prompt_id,
        "group": job.group,
        "output_name": job.output_name,
        "render_strategy": job.render_strategy,
        "reference_prompt_id": job.reference_prompt_id,
        "prompt_fingerprint": _fingerprint(job.prompt),
        "image_bytes": provider_result.image_bytes,
        "image_path": "",
        "provider": provider_result.provider_name,
        "model": provider_result.model,
        "base_url": provider_result.base_url,
        "mime_type": provider_result.mime_type,
    }


def _build_render_report(
    render_input: ImageRenderInput,
    output_dir: Path,
    rendered_images: list[dict[str, Any]],
) -> dict[str, Any]:
    images = _report_images(output_dir, rendered_images)
    first_image = images[0]
    return {
        "schema_version": _REPORT_SCHEMA_VERSION,
        "category": render_input.category,
        "mode": render_input.mode,
        "source_result_path": str(render_input.source_result_path),
        "prompt_fingerprint": first_image["prompt_fingerprint"],
        "provider": first_image["provider"],
        "model": first_image["model"],
        "base_url": first_image["base_url"],
        "mime_type": first_image["mime_type"],
        "image_path": first_image["image_path"],
        "report_path": str(output_dir / _REPORT_FILENAME),
        "images": [
            {
                "prompt_id": item["prompt_id"],
                "group": item["group"],
                "output_name": item["output_name"],
                "render_strategy": item["render_strategy"],
                "reference_prompt_id": item["reference_prompt_id"],
                "prompt_fingerprint": item["prompt_fingerprint"],
                "image_path": item["image_path"],
            }
            for item in images
        ],
        "rendered_at": _current_timestamp(),
    }


def _report_images(output_dir: Path, rendered_images: list[dict[str, Any]]) -> list[dict[str, Any]]:
    images: list[dict[str, Any]] = []
    for item in rendered_images:
        images.append({**item, "image_path": str(output_dir / item["output_name"])})
    return images


def _write_output_bundle(output_dir: Path, rendered_images: list[dict[str, Any]], report: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / _REPORT_FILENAME
    staged_paths = _write_temp_outputs(output_dir, rendered_images, report_path, report)
    published: list[Path] = []
    try:
        for temp_path, final_path in staged_paths:
            temp_path.replace(final_path)
            published.append(final_path)
    except OSError:
        _cleanup_paths([path for path, _ in staged_paths], published)
        raise


def _write_temp_outputs(
    output_dir: Path,
    rendered_images: list[dict[str, Any]],
    report_path: Path,
    report: dict[str, Any],
) -> list[tuple[Path, Path]]:
    report_temp = report_path.with_suffix(f"{report_path.suffix}.tmp")
    staged_paths: list[tuple[Path, Path]] = []
    for item in rendered_images:
        image_path = output_dir / item["output_name"]
        image_temp = image_path.with_suffix(f"{image_path.suffix}.tmp")
        image_temp.write_bytes(item["image_bytes"])
        staged_paths.append((image_temp, image_path))
    report_temp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    staged_paths.append((report_temp, report_path))
    return staged_paths


def _cleanup_paths(temp_paths: list[Path], published_paths: list[Path]) -> None:
    for path in [*temp_paths, *published_paths]:
        if path.exists():
            path.unlink()


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _current_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _provider_error(provider: ImageProvider, error: Exception) -> GenerationError:
    return GenerationError(
        code="IMAGE_PROVIDER_FAILED",
        message="image provider failed to render the requested image",
        details={"provider": provider.__class__.__name__, "reason": str(error)},
    )


def _output_error(error: OSError) -> GenerationError:
    return GenerationError(
        code="IMAGE_RENDER_OUTPUT_FAILED",
        message="failed to write image render outputs",
        details={"path": str(getattr(error, "filename", ""))},
    )
