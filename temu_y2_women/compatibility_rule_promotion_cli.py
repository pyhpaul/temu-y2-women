from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from temu_y2_women.errors import GenerationError
from temu_y2_women.compatibility_rule_promotion import (
    apply_reviewed_compatibility_rule_promotion,
    prepare_compatibility_rule_review,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare or apply review-gated compatibility rule promotions.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_prepare_parser(subparsers)
    _add_apply_parser(subparsers)
    args = parser.parse_args(argv)
    result = _run_command(args)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if "error" not in result else 1


def _add_prepare_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("prepare", help="Build a compatibility rule review template from staged drafts.")
    parser.add_argument("--draft-rules", required=True, help="Path to staged draft_conflict_rules.json.")
    parser.add_argument("--active-rules", required=True, help="Path to active compatibility_rules.json.")
    parser.add_argument("--elements", help="Optional path to active elements.json.")
    parser.add_argument("--taxonomy", help="Optional path to evidence_taxonomy.json.")
    parser.add_argument("--output", required=True, help="Path to write the generated review template JSON.")


def _add_apply_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("apply", help="Apply a reviewed compatibility rule promotion bundle.")
    parser.add_argument("--reviewed", required=True, help="Path to the reviewed compatibility rule decisions JSON.")
    parser.add_argument("--draft-rules", required=True, help="Path to staged draft_conflict_rules.json.")
    parser.add_argument("--active-rules", required=True, help="Path to active compatibility_rules.json.")
    parser.add_argument("--elements", help="Optional path to active elements.json.")
    parser.add_argument("--taxonomy", help="Optional path to evidence_taxonomy.json.")
    parser.add_argument("--report-output", required=True, help="Path to write the promotion report JSON.")


def _run_command(args: argparse.Namespace) -> dict[str, object]:
    if args.command == "prepare":
        return _run_prepare(args)
    if args.command == "apply":
        return _run_apply(args)
    raise GenerationError(code="INVALID_PROMOTION_INPUT", message="unsupported promotion CLI command")


def _run_prepare(args: argparse.Namespace) -> dict[str, object]:
    result = prepare_compatibility_rule_review(
        draft_rules_path=Path(args.draft_rules),
        active_rules_path=Path(args.active_rules),
        elements_path=_elements_path(args),
        taxonomy_path=_taxonomy_path(args),
    )
    if "error" in result:
        return result
    try:
        _write_json(Path(args.output), result)
    except OSError as error:
        return _write_error(error).to_dict()
    return result


def _run_apply(args: argparse.Namespace) -> dict[str, object]:
    return apply_reviewed_compatibility_rule_promotion(
        reviewed_path=Path(args.reviewed),
        draft_rules_path=Path(args.draft_rules),
        active_rules_path=Path(args.active_rules),
        report_path=Path(args.report_output),
        elements_path=_elements_path(args),
        taxonomy_path=_taxonomy_path(args),
    )


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _elements_path(args: argparse.Namespace) -> Path:
    if getattr(args, "elements", None):
        return Path(args.elements)
    return Path(__file__).resolve().parent.parent / "data/mvp/dress/elements.json"


def _taxonomy_path(args: argparse.Namespace) -> Path:
    if getattr(args, "taxonomy", None):
        return Path(args.taxonomy)
    return Path(__file__).resolve().parent.parent / "data/mvp/dress/evidence_taxonomy.json"


def _write_error(error: OSError) -> GenerationError:
    return GenerationError(code="PROMOTION_WRITE_FAILED", message="failed to write promotion cli outputs", details={"path": str(getattr(error, "filename", ""))})


if __name__ == "__main__":
    raise SystemExit(main())
