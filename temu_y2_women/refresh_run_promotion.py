from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from temu_y2_women.errors import GenerationError
from temu_y2_women.evidence_promotion import (
    apply_reviewed_dress_promotion,
    prepare_dress_promotion_review,
)

_DEFAULT_TAXONOMY_PATH = Path(__file__).resolve().parent.parent / "data" / "mvp" / "dress" / "evidence_taxonomy.json"
def prepare_dress_promotion_from_refresh_run(
    run_dir: Path,
    active_elements_path: Path,
    active_strategies_path: Path,
    taxonomy_path: Path = _DEFAULT_TAXONOMY_PATH,
    output_path: Path | None = None,
) -> dict[str, Any]:
    try:
        draft_elements_path, draft_strategy_hints_path = _prepare_run_inputs(run_dir)
        review = prepare_dress_promotion_review(
            draft_elements_path=draft_elements_path,
            draft_strategy_hints_path=draft_strategy_hints_path,
            active_elements_path=active_elements_path,
            active_strategies_path=active_strategies_path,
            taxonomy_path=taxonomy_path,
        )
        if "error" not in review:
            _write_json(output_path or run_dir / "promotion_review.json", review)
        return review
    except GenerationError as error:
        return error.to_dict()
    except OSError as error:
        return _io_error(error).to_dict()


def apply_reviewed_dress_promotion_from_refresh_run(
    run_dir: Path,
    active_elements_path: Path,
    active_strategies_path: Path,
    reviewed_path: Path | None = None,
    report_path: Path | None = None,
    taxonomy_path: Path = _DEFAULT_TAXONOMY_PATH,
) -> dict[str, Any]:
    try:
        draft_elements_path, draft_strategy_hints_path = _prepare_run_inputs(run_dir)
        resolved_reviewed_path = reviewed_path or _resolve_reviewed_path(run_dir)
        if resolved_reviewed_path is None or not resolved_reviewed_path.is_file():
            raise _invalid_run(run_dir, "reviewed", "refresh run is missing reviewed promotion decisions")
        return apply_reviewed_dress_promotion(
            reviewed_path=resolved_reviewed_path,
            draft_elements_path=draft_elements_path,
            draft_strategy_hints_path=draft_strategy_hints_path,
            active_elements_path=active_elements_path,
            active_strategies_path=active_strategies_path,
            report_path=report_path or run_dir / "promotion_report.json",
            taxonomy_path=taxonomy_path,
        )
    except GenerationError as error:
        return error.to_dict()
    except OSError as error:
        return _io_error(error).to_dict()


def _prepare_run_inputs(run_dir: Path) -> tuple[Path, Path]:
    _require_run_dir(run_dir)
    draft_elements_path = _require_run_file(run_dir, "draft_elements.json")
    draft_strategy_hints_path = _require_run_file(run_dir, "draft_strategy_hints.json")
    _require_run_file(run_dir, "ingestion_report.json")
    _require_run_file(run_dir, "refresh_report.json")
    return draft_elements_path, draft_strategy_hints_path


def _require_run_dir(run_dir: Path) -> None:
    if run_dir.is_dir():
        return
    raise _invalid_run(run_dir, "run_dir", "refresh run directory is missing")


def _require_run_file(run_dir: Path, name: str) -> Path:
    path = run_dir / name
    if path.is_file():
        return path
    raise _invalid_run(run_dir, name, "refresh run artifact is missing or not a file")


def _resolve_reviewed_path(run_dir: Path) -> Path | None:
    for name in ("promotion_review.json", "reviewed_decisions.json"):
        path = run_dir / name
        if path.exists():
            return path
    return None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _invalid_run(run_dir: Path, field: str, message: str) -> GenerationError:
    return GenerationError(
        code="INVALID_REFRESH_RUN",
        message=message,
        details={"path": str(run_dir), "field": field},
    )


def _io_error(error: OSError) -> GenerationError:
    return GenerationError(
        code="REFRESH_RUN_IO_FAILED",
        message="failed to read or write refresh run promotion artifacts",
        details={"path": str(getattr(error, "filename", ""))},
    )
