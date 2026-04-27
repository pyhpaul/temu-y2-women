from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from temu_y2_women.feedback_loop import (
    apply_reviewed_dress_concept_feedback,
    prepare_dress_concept_feedback,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare or apply review-gated dress concept feedback.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_prepare_parser(subparsers)
    _add_apply_parser(subparsers)
    args = parser.parse_args(argv)
    result = _run_command(args)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if "error" not in result else 1


def _add_prepare_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("prepare", help="Build a concept feedback review template.")
    parser.add_argument("--result", required=True, help="Path to a successful concept result JSON.")
    parser.add_argument("--output", required=True, help="Path to write the generated review JSON.")


def _add_apply_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("apply", help="Apply reviewed concept feedback to active evidence.")
    parser.add_argument("--reviewed", required=True, help="Path to the reviewed feedback JSON.")
    parser.add_argument("--result", required=True, help="Path to the successful concept result JSON.")
    parser.add_argument("--active-elements", required=True, help="Path to active elements.json.")
    parser.add_argument("--ledger", required=True, help="Path to feedback_ledger.json.")
    parser.add_argument("--report-output", required=True, help="Path to write the feedback report JSON.")
    parser.add_argument("--taxonomy", help="Optional path to evidence_taxonomy.json.")


def _run_command(args: argparse.Namespace) -> dict[str, object]:
    if args.command == "prepare":
        return _run_prepare(args)
    return _run_apply(args)


def _run_prepare(args: argparse.Namespace) -> dict[str, object]:
    result = prepare_dress_concept_feedback(result_path=Path(args.result))
    if "error" not in result:
        try:
            _write_json(Path(args.output), result)
        except OSError as error:
            return _write_error(error)
    return result


def _run_apply(args: argparse.Namespace) -> dict[str, object]:
    kwargs = {
        "reviewed_path": Path(args.reviewed),
        "result_path": Path(args.result),
        "active_elements_path": Path(args.active_elements),
        "ledger_path": Path(args.ledger),
        "report_path": Path(args.report_output),
    }
    if getattr(args, "taxonomy", None):
        kwargs["taxonomy_path"] = Path(args.taxonomy)
    return apply_reviewed_dress_concept_feedback(**kwargs)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_error(error: OSError) -> dict[str, object]:
    return {
        "error": {
            "code": "FEEDBACK_WRITE_FAILED",
            "message": "failed to write feedback cli outputs",
            "details": {"path": str(getattr(error, "filename", ""))},
        }
    }


if __name__ == "__main__":
    raise SystemExit(main())
