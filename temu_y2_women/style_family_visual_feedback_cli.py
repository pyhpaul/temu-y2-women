from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from temu_y2_women.style_family_visual_feedback import prepare_visual_feedback_reviews


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        report = _run_prepare(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "ready" else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare feedback reviews from style-family visual quality.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare", help="Write reviewed feedback files for each style family.")
    prepare_parser.add_argument("--manifest", required=True, help="Path to style-family validation manifest JSON.")
    prepare_parser.add_argument("--quality-review", required=True, help="Path to visual quality review JSON.")
    prepare_parser.add_argument("--output-dir", required=True, help="Directory for feedback review artifacts.")
    return parser


def _run_prepare(args: argparse.Namespace) -> dict[str, object]:
    return prepare_visual_feedback_reviews(
        manifest_path=Path(args.manifest),
        quality_review_path=Path(args.quality_review),
        output_dir=Path(args.output_dir),
    )


if __name__ == "__main__":
    raise SystemExit(main())
