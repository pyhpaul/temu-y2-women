from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from temu_y2_women.style_family_visual_acceptance import (
    build_visual_acceptance_report,
    write_visual_acceptance_report,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    report = _run_build(args)
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] != "incomplete" else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a style-family visual acceptance report.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build", help="Build a report from local render artifacts.")
    build_parser.add_argument("--manifest", required=True, help="Path to style-family validation manifest JSON.")
    build_parser.add_argument("--renders-root", required=True, help="Directory containing family render folders.")
    build_parser.add_argument("--output", required=True, help="Path to write visual acceptance JSON.")
    build_parser.add_argument("--status", choices=("accepted", "rejected"), required=True)
    build_parser.add_argument("--note", action="append", default=[], help="Family note as family-id=text.")
    return parser


def _run_build(args: argparse.Namespace) -> dict[str, object]:
    report = build_visual_acceptance_report(
        manifest_path=Path(args.manifest),
        renders_root=Path(args.renders_root),
        status=args.status,
        notes=_notes_from_args(args.note),
    )
    write_visual_acceptance_report(report, Path(args.output))
    return report


def _notes_from_args(values: Sequence[str]) -> dict[str, str]:
    notes: dict[str, str] = {}
    for value in values:
        family_id, separator, note = value.partition("=")
        if separator and family_id.strip():
            notes[family_id.strip()] = note.strip()
    return notes


if __name__ == "__main__":
    raise SystemExit(main())
