from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping


_SCHEMA_VERSION = "style-family-visual-acceptance-v1"
_DEFAULT_CRITERION = "Only judge whether the four hero_front images are distinguishable at a glance."
_IMAGE_FILENAME = "hero_front.png"
_RENDER_REPORT_FILENAME = "image_render_report.json"


def build_visual_acceptance_report(
    *,
    manifest_path: Path,
    renders_root: Path,
    status: str,
    notes: Mapping[str, str] | None = None,
    criterion: str = _DEFAULT_CRITERION,
) -> dict[str, Any]:
    cases = [
        _case_report(case, renders_root, notes or {})
        for case in _manifest_cases(_read_json(manifest_path))
    ]
    summary = _summary(cases)
    return {
        "schema_version": _SCHEMA_VERSION,
        "accepted_at": _current_date(),
        "criterion": criterion,
        "status": _overall_status(status, summary),
        "summary": summary,
        "manifest_path": str(manifest_path),
        "renders_root": str(renders_root),
        "cases": cases,
    }


def write_visual_acceptance_report(report: Mapping[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def _case_report(
    manifest_case: Mapping[str, Any],
    renders_root: Path,
    notes: Mapping[str, str],
) -> dict[str, Any]:
    family_id = str(manifest_case.get("style_family_id", ""))
    family_dir = renders_root / family_id
    image_path = family_dir / _IMAGE_FILENAME
    report_path = family_dir / _RENDER_REPORT_FILENAME
    render_report = _optional_json(report_path)
    return {
        "style_family_id": family_id,
        "status": "ready" if image_path.exists() and report_path.exists() else "missing_artifacts",
        "image_path": str(image_path),
        "image_exists": image_path.exists(),
        "image_bytes": image_path.stat().st_size if image_path.exists() else 0,
        "report_path": str(report_path),
        "report_exists": report_path.exists(),
        "prompt_fingerprint": _prompt_fingerprint(render_report),
        "selected_elements": manifest_case.get("selected_elements", {}),
        "note": notes.get(family_id, ""),
    }


def _manifest_cases(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    cases = payload.get("cases", [])
    if isinstance(cases, list):
        return [case for case in cases if isinstance(case, dict)]
    return []


def _summary(cases: list[Mapping[str, Any]]) -> dict[str, int]:
    ready = sum(1 for case in cases if case.get("status") == "ready")
    return {
        "total": len(cases),
        "ready": ready,
        "missing": len(cases) - ready,
    }


def _overall_status(requested_status: str, summary: Mapping[str, int]) -> str:
    if summary.get("missing", 0) > 0:
        return "incomplete"
    return requested_status


def _prompt_fingerprint(render_report: Mapping[str, Any] | None) -> str:
    if not render_report:
        return ""
    images = render_report.get("images", [])
    if not isinstance(images, list):
        return ""
    for image in images:
        if isinstance(image, dict) and image.get("prompt_id") == "hero_front":
            value = image.get("prompt_fingerprint", "")
            return value if isinstance(value, str) else ""
    return ""


def _optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    payload = _read_json(path)
    return payload if isinstance(payload, dict) else None


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _current_date() -> str:
    return datetime.now(timezone.utc).date().isoformat()
