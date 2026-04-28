from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from temu_y2_women.conflict_rule_feedback_deriver import derive_conflict_rules_from_feedback_ledger


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Derive staged conflict-rule candidates from reviewed feedback.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_derive_parser(subparsers)
    args = parser.parse_args(argv)
    result = _run_command(args)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if "error" not in result else 1


def _add_derive_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("derive", help="Build draft conflict rules from feedback ledger evidence.")
    parser.add_argument("--ledger", required=True, help="Path to feedback_ledger.json.")
    parser.add_argument("--output", required=True, help="Path to write draft_conflict_rules.json.")


def _run_command(args: argparse.Namespace) -> dict[str, object]:
    result = derive_conflict_rules_from_feedback_ledger(Path(args.ledger))
    if "error" in result:
        return result
    try:
        _write_json(Path(args.output), result)
    except OSError as error:
        return _write_error(error)
    summary = result["summary"]
    return {
        "draft_count": summary["draft_count"],
        "output_path": str(Path(args.output)),
        "skipped_pair_count": summary["skipped_pair_count"],
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_error(error: OSError) -> dict[str, object]:
    return {
        "error": {
            "code": "CONFLICT_RULE_WRITE_FAILED",
            "message": "failed to write conflict rule cli outputs",
            "details": {"path": str(getattr(error, "filename", ""))},
        }
    }


if __name__ == "__main__":
    raise SystemExit(main())
