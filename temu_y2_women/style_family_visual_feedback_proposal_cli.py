from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from temu_y2_women.errors import GenerationError
from temu_y2_women.style_family_visual_feedback_proposal import (
    apply_visual_feedback_proposal,
    build_visual_feedback_apply_proposal,
    write_visual_feedback_apply_proposal,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        payload = _run_command(args)
    except (GenerationError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["status"] in {"ready", "applied"} else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a reviewable visual feedback apply proposal.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_build_parser(subparsers)
    _add_apply_parser(subparsers)
    return parser


def _add_build_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    build_parser = subparsers.add_parser("build", help="Build proposal from visual feedback dry-run report.")
    build_parser.add_argument("--dry-run", required=True, help="Path to visual feedback dry-run report JSON.")
    build_parser.add_argument("--output", required=True, help="Path to write apply proposal JSON.")
    build_parser.add_argument("--minimum-delta", type=float, default=0.04)
    build_parser.add_argument("--minimum-family-count", type=int, default=2)


def _add_apply_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    apply_parser = subparsers.add_parser("apply", help="Apply recommended visual feedback proposal changes.")
    apply_parser.add_argument("--proposal", required=True, help="Path to visual feedback apply proposal JSON.")
    apply_parser.add_argument("--active-elements", required=True, help="Path to active elements.json to update.")
    apply_parser.add_argument("--taxonomy", required=True, help="Path to evidence_taxonomy.json.")
    apply_parser.add_argument("--report-output", required=True, help="Path to write apply report JSON.")


def _run_command(args: argparse.Namespace) -> dict[str, object]:
    if args.command == "build":
        return _run_build(args)
    if args.command == "apply":
        return _run_apply(args)
    raise ValueError(f"Unsupported command: {args.command}")


def _run_build(args: argparse.Namespace) -> dict[str, object]:
    proposal = build_visual_feedback_apply_proposal(
        dry_run_path=Path(args.dry_run),
        minimum_delta=args.minimum_delta,
        minimum_family_count=args.minimum_family_count,
    )
    write_visual_feedback_apply_proposal(proposal, Path(args.output))
    return proposal


def _run_apply(args: argparse.Namespace) -> dict[str, object]:
    return apply_visual_feedback_proposal(
        proposal_path=Path(args.proposal),
        active_elements_path=Path(args.active_elements),
        taxonomy_path=Path(args.taxonomy),
        report_path=Path(args.report_output),
    )


if __name__ == "__main__":
    raise SystemExit(main())
