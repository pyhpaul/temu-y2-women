from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from temu_y2_women.evidence_paths import EvidencePaths
from temu_y2_women.style_family_visual_drift import (
    build_style_family_visual_drift_check,
    write_style_family_visual_drift_check,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        report = _run_check(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "passed" else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check style-family concept drift after visual feedback apply.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    check_parser = subparsers.add_parser("check", help="Re-run manifest requests and compare selected family/elements.")
    check_parser.add_argument("--manifest", required=True, help="Path to style-family validation manifest JSON.")
    check_parser.add_argument("--output", required=True, help="Path to write drift check JSON.")
    check_parser.add_argument("--elements-path", help="Optional elements.json override.")
    check_parser.add_argument("--strategies-path", help="Optional strategy_templates.json override.")
    check_parser.add_argument("--taxonomy-path", help="Optional evidence_taxonomy.json override.")
    check_parser.add_argument("--style-families-path", help="Optional style_families.json override.")
    return parser


def _run_check(args: argparse.Namespace) -> dict[str, object]:
    report = build_style_family_visual_drift_check(
        manifest_path=Path(args.manifest),
        evidence_paths=_evidence_paths_from_args(args),
    )
    write_style_family_visual_drift_check(report, Path(args.output))
    return report


def _evidence_paths_from_args(args: argparse.Namespace) -> EvidencePaths | None:
    values = (
        args.elements_path,
        args.strategies_path,
        args.taxonomy_path,
        args.style_families_path,
    )
    if not any(values):
        return None
    defaults = EvidencePaths.defaults()
    return EvidencePaths(
        elements_path=Path(args.elements_path) if args.elements_path else defaults.elements_path,
        strategies_path=Path(args.strategies_path) if args.strategies_path else defaults.strategies_path,
        taxonomy_path=Path(args.taxonomy_path) if args.taxonomy_path else defaults.taxonomy_path,
        style_families_path=Path(args.style_families_path) if args.style_families_path else defaults.style_families_path,
    )


if __name__ == "__main__":
    raise SystemExit(main())
