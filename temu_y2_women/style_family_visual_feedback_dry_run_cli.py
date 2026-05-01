from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from temu_y2_women.style_family_visual_feedback_dry_run import (
    dry_run_visual_feedback_apply,
    write_visual_feedback_dry_run_report,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        report = _run_apply(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "applied" else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dry-run apply style-family visual feedback.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    apply_parser = subparsers.add_parser("apply", help="Apply feedback reviews to a workspace copy.")
    apply_parser.add_argument("--batch", required=True, help="Path to visual_feedback_batch.json.")
    apply_parser.add_argument("--workspace-dir", required=True, help="Directory for dry-run evidence copies.")
    apply_parser.add_argument("--active-elements", required=True, help="Source active elements.json.")
    apply_parser.add_argument("--ledger", required=True, help="Source feedback_ledger.json.")
    apply_parser.add_argument("--taxonomy", required=True, help="Path to evidence_taxonomy.json.")
    apply_parser.add_argument("--output", required=True, help="Path to write dry-run report JSON.")
    return parser


def _run_apply(args: argparse.Namespace) -> dict[str, object]:
    report = dry_run_visual_feedback_apply(
        batch_path=Path(args.batch),
        workspace_dir=Path(args.workspace_dir),
        active_elements_path=Path(args.active_elements),
        ledger_path=Path(args.ledger),
        taxonomy_path=Path(args.taxonomy),
    )
    write_visual_feedback_dry_run_report(report, Path(args.output))
    return report


if __name__ == "__main__":
    raise SystemExit(main())
