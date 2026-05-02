from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from temu_y2_women.style_family_visual_feedback_proposal import (
    build_visual_feedback_apply_proposal,
    write_visual_feedback_apply_proposal,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        proposal = _run_build(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(proposal, ensure_ascii=False))
    return 0 if proposal["status"] == "ready" else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a reviewable visual feedback apply proposal.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build", help="Build proposal from visual feedback dry-run report.")
    build_parser.add_argument("--dry-run", required=True, help="Path to visual feedback dry-run report JSON.")
    build_parser.add_argument("--output", required=True, help="Path to write apply proposal JSON.")
    build_parser.add_argument("--minimum-delta", type=float, default=0.04)
    build_parser.add_argument("--minimum-family-count", type=int, default=2)
    return parser


def _run_build(args: argparse.Namespace) -> dict[str, object]:
    proposal = build_visual_feedback_apply_proposal(
        dry_run_path=Path(args.dry_run),
        minimum_delta=args.minimum_delta,
        minimum_family_count=args.minimum_family_count,
    )
    write_visual_feedback_apply_proposal(proposal, Path(args.output))
    return proposal


if __name__ == "__main__":
    raise SystemExit(main())
