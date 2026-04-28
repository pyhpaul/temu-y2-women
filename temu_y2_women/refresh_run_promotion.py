from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from temu_y2_women.errors import GenerationError
from temu_y2_women.evidence_promotion import (
    apply_reviewed_dress_promotion,
    prepare_dress_promotion_review,
)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_TAXONOMY_PATH = _PROJECT_ROOT / "data/mvp/dress/evidence_taxonomy.json"
_REQUIRED_REFRESH_RUN_FILES = (
    "draft_elements.json",
    "draft_strategy_hints.json",
    "ingestion_report.json",
    "refresh_report.json",
)


def prepare_dress_promotion_from_refresh_run(
    run_dir: Path,
    active_elements_path: Path,
    active_strategies_path: Path,
    output_path: Path | None = None,
    taxonomy_path: Path | None = None,
) -> dict[str, Any]:
    try:
        paths = resolve_prepare_refresh_run_paths(run_dir, output_path)
        result = prepare_dress_promotion_review(
            draft_elements_path=paths["draft_elements_path"],
            draft_strategy_hints_path=paths["draft_strategy_hints_path"],
            active_elements_path=active_elements_path,
            active_strategies_path=active_strategies_path,
            taxonomy_path=taxonomy_path or _default_taxonomy_path(),
        )
        if "error" not in result:
            _write_json(paths["output_path"], result)
        return result
    except GenerationError as error:
        return error.to_dict()
    except OSError as error:
        return _refresh_run_io_error(error).to_dict()


def resolve_prepare_refresh_run_paths(run_dir: Path, output_path: Path | None = None) -> dict[str, Path]:
    _validate_refresh_run_dir(run_dir)
    return {
        "draft_elements_path": run_dir / "draft_elements.json",
        "draft_strategy_hints_path": run_dir / "draft_strategy_hints.json",
        "output_path": output_path or (run_dir / "promotion_review.json"),
    }


def apply_reviewed_dress_promotion_from_refresh_run(
    run_dir: Path,
    active_elements_path: Path,
    active_strategies_path: Path,
    reviewed_path: Path | None = None,
    report_path: Path | None = None,
    taxonomy_path: Path | None = None,
) -> dict[str, Any]:
    try:
        paths = resolve_apply_refresh_run_paths(run_dir, reviewed_path, report_path)
        return apply_reviewed_dress_promotion(
            reviewed_path=paths["reviewed_path"],
            draft_elements_path=paths["draft_elements_path"],
            draft_strategy_hints_path=paths["draft_strategy_hints_path"],
            active_elements_path=active_elements_path,
            active_strategies_path=active_strategies_path,
            report_path=paths["report_path"],
            taxonomy_path=taxonomy_path or _default_taxonomy_path(),
        )
    except GenerationError as error:
        return error.to_dict()
    except OSError as error:
        return _refresh_run_io_error(error).to_dict()


def resolve_apply_refresh_run_paths(
    run_dir: Path,
    reviewed_path: Path | None = None,
    report_path: Path | None = None,
) -> dict[str, Path]:
    _validate_refresh_run_dir(run_dir)
    return {
        "draft_elements_path": run_dir / "draft_elements.json",
        "draft_strategy_hints_path": run_dir / "draft_strategy_hints.json",
        "reviewed_path": _resolve_reviewed_path(run_dir, reviewed_path),
        "report_path": report_path or (run_dir / "promotion_report.json"),
    }


def _validate_refresh_run_dir(run_dir: Path) -> None:
    if not run_dir.is_dir():
        raise _refresh_run_error(run_dir, "run_dir", "refresh run directory does not exist")
    for filename in _REQUIRED_REFRESH_RUN_FILES:
        candidate = run_dir / filename
        if candidate.is_file():
            continue
        raise _refresh_run_error(run_dir, filename, "refresh run directory is missing a required artifact")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _resolve_reviewed_path(run_dir: Path, reviewed_path: Path | None) -> Path:
    if reviewed_path is not None:
        if reviewed_path.is_file():
            return reviewed_path
        raise _refresh_run_error(run_dir, "reviewed", "refresh run directory does not contain a reviewed promotion artifact")
    return _default_reviewed_path(run_dir)


def _default_reviewed_path(run_dir: Path) -> Path:
    primary = run_dir / "promotion_review.json"
    if primary.exists():
        return primary
    legacy = run_dir / "reviewed_decisions.json"
    if legacy.exists():
        return legacy
    raise _refresh_run_error(
        run_dir,
        "reviewed",
        "refresh run directory does not contain a reviewed promotion artifact",
    )


def _default_taxonomy_path() -> Path:
    return _DEFAULT_TAXONOMY_PATH


def _refresh_run_error(run_dir: Path, field: str, message: str) -> GenerationError:
    return GenerationError(
        code="INVALID_REFRESH_RUN",
        message=message,
        details={"path": str(run_dir), "field": field},
    )


def _refresh_run_io_error(error: OSError) -> GenerationError:
    return GenerationError(
        code="PROMOTION_WRITE_FAILED",
        message="failed to write promotion review output",
        details={"path": str(getattr(error, "filename", ""))},
    )

