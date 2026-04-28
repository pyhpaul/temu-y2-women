from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from temu_y2_women.errors import GenerationError
from temu_y2_women.evidence_promotion import (
    apply_reviewed_dress_promotion,
    prepare_dress_promotion_review,
)
from temu_y2_women.refresh_run_promotion import (
    apply_reviewed_dress_promotion_from_refresh_run,
    prepare_dress_promotion_from_refresh_run,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare or apply review-gated dress evidence promotions.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_prepare_parser(subparsers)
    _add_apply_parser(subparsers)
    args = parser.parse_args(argv)
    result = _run_command(args)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if "error" not in result else 1


def _add_prepare_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("prepare", help="Build a promotion review template from staged drafts.")
    parser.add_argument("--run-dir", help="Path to a refresh run directory containing staged promotion inputs.")
    parser.add_argument("--draft-elements", help="Path to staged draft_elements.json.")
    parser.add_argument("--draft-strategy-hints", help="Path to staged draft_strategy_hints.json.")
    parser.add_argument("--active-elements", required=True, help="Path to active elements.json.")
    parser.add_argument("--active-strategies", required=True, help="Path to active strategy_templates.json.")
    parser.add_argument("--taxonomy", help="Optional path to evidence_taxonomy.json.")
    parser.add_argument("--output", help="Path to write the generated review template JSON.")


def _add_apply_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("apply", help="Apply a reviewed promotion bundle to active evidence.")
    parser.add_argument("--run-dir", help="Path to a refresh run directory containing staged promotion inputs.")
    parser.add_argument("--reviewed", help="Path to the reviewed promotion decision JSON.")
    parser.add_argument("--draft-elements", help="Path to staged draft_elements.json.")
    parser.add_argument("--draft-strategy-hints", help="Path to staged draft_strategy_hints.json.")
    parser.add_argument("--active-elements", required=True, help="Path to active elements.json.")
    parser.add_argument("--active-strategies", required=True, help="Path to active strategy_templates.json.")
    parser.add_argument("--taxonomy", help="Optional path to evidence_taxonomy.json.")
    parser.add_argument("--report-output", help="Path to write the promotion report JSON.")


def _run_command(args: argparse.Namespace) -> dict[str, object]:
    if args.command == "prepare":
        return _run_prepare(args)
    if args.command == "apply":
        return _run_apply(args)
    raise GenerationError(code="INVALID_PROMOTION_INPUT", message="unsupported promotion CLI command")


def _run_prepare(args: argparse.Namespace) -> dict[str, object]:
    try:
        _validate_prepare_args(args)
    except GenerationError as error:
        return error.to_dict()
    if args.run_dir:
        return prepare_dress_promotion_from_refresh_run(
            run_dir=Path(args.run_dir),
            active_elements_path=Path(args.active_elements),
            active_strategies_path=Path(args.active_strategies),
            output_path=_optional_path(args.output),
            taxonomy_path=_taxonomy_path(args),
        )
    result = prepare_dress_promotion_review(
        draft_elements_path=Path(args.draft_elements),
        draft_strategy_hints_path=Path(args.draft_strategy_hints),
        active_elements_path=Path(args.active_elements),
        active_strategies_path=Path(args.active_strategies),
        taxonomy_path=_taxonomy_path(args),
    )
    if "error" not in result:
        try:
            _write_json(Path(args.output), result)
        except OSError as error:
            return _write_error(error).to_dict()
    return result


def _run_apply(args: argparse.Namespace) -> dict[str, object]:
    try:
        _validate_apply_args(args)
    except GenerationError as error:
        return error.to_dict()
    if args.run_dir:
        return apply_reviewed_dress_promotion_from_refresh_run(
            run_dir=Path(args.run_dir),
            active_elements_path=Path(args.active_elements),
            active_strategies_path=Path(args.active_strategies),
            reviewed_path=_optional_path(args.reviewed),
            report_path=_optional_path(args.report_output),
            taxonomy_path=_taxonomy_path(args),
        )
    return apply_reviewed_dress_promotion(
        reviewed_path=Path(args.reviewed),
        draft_elements_path=Path(args.draft_elements),
        draft_strategy_hints_path=Path(args.draft_strategy_hints),
        active_elements_path=Path(args.active_elements),
        active_strategies_path=Path(args.active_strategies),
        report_path=Path(args.report_output),
        taxonomy_path=_taxonomy_path(args),
    )


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _validate_prepare_args(args: argparse.Namespace) -> None:
    if args.run_dir and (args.draft_elements or args.draft_strategy_hints):
        raise GenerationError(
            code="INVALID_REFRESH_RUN",
            message="run-dir mode cannot be combined with explicit staged input paths",
            details={"field": "run_dir"},
        )
    if args.run_dir:
        return
    if args.draft_elements and args.draft_strategy_hints and args.output:
        return
    raise GenerationError(
        code="INVALID_PROMOTION_INPUT",
        message="prepare requires either --run-dir or explicit staged input paths plus --output",
        details={"field": "prepare"},
    )


def _validate_apply_args(args: argparse.Namespace) -> None:
    if args.run_dir and (args.draft_elements or args.draft_strategy_hints):
        raise GenerationError(
            code="INVALID_REFRESH_RUN",
            message="run-dir mode cannot be combined with explicit staged input paths",
            details={"field": "run_dir"},
        )
    if args.run_dir:
        return
    if args.reviewed and args.draft_elements and args.draft_strategy_hints and args.report_output:
        return
    raise GenerationError(
        code="INVALID_PROMOTION_INPUT",
        message="apply requires either --run-dir or explicit reviewed and staged input paths plus --report-output",
        details={"field": "apply"},
    )


def _optional_path(path_value: str | None) -> Path | None:
    if path_value is None:
        return None
    return Path(path_value)


def _taxonomy_path(args: argparse.Namespace) -> Path:
    if getattr(args, "taxonomy", None):
        return Path(args.taxonomy)
    return Path(__file__).resolve().parent.parent / "data/mvp/dress/evidence_taxonomy.json"


def _write_error(error: OSError) -> GenerationError:
    return GenerationError(
        code="PROMOTION_WRITE_FAILED",
        message="failed to write promotion cli outputs",
        details={"path": str(getattr(error, "filename", ""))},
    )


if __name__ == "__main__":
    raise SystemExit(main())
