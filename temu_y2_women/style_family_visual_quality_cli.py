from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from temu_y2_women.style_family_visual_quality import (
    build_visual_quality_review,
    write_visual_quality_review,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        report = _run_build(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "accepted" else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a style-family visual quality review.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build", help="Build a review from visual acceptance JSON.")
    build_parser.add_argument("--acceptance", required=True, help="Path to visual acceptance JSON.")
    build_parser.add_argument("--output", required=True, help="Path to write visual quality JSON.")
    build_parser.add_argument("--decision", action="append", default=[], help="Family decision as family-id=accepted.")
    build_parser.add_argument("--score", action="append", default=[], help="Quality score as family-id:criterion=1.")
    build_parser.add_argument("--note", action="append", default=[], help="Reviewer note as family-id=text.")
    build_parser.add_argument("--revision-reason", action="append", default=[], help="Revision reason as family-id=text.")
    return parser


def _run_build(args: argparse.Namespace) -> dict[str, object]:
    report = build_visual_quality_review(
        acceptance_path=Path(args.acceptance),
        decisions=_pairs_from_args(args.decision, "decision"),
        scores=_scores_from_args(args.score),
        notes=_pairs_from_args(args.note, "note"),
        revision_reasons=_list_pairs_from_args(args.revision_reason, "revision reason"),
    )
    write_visual_quality_review(report, Path(args.output))
    return report


def _pairs_from_args(values: Sequence[str], label: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for value in values:
        family_id, separator, text = value.partition("=")
        if not separator or not family_id.strip():
            raise ValueError(f"Invalid {label}: {value}")
        parsed[family_id.strip()] = text.strip()
    return parsed


def _list_pairs_from_args(values: Sequence[str], label: str) -> dict[str, list[str]]:
    parsed: dict[str, list[str]] = {}
    for value in values:
        family_id, separator, text = value.partition("=")
        if not separator or not family_id.strip():
            raise ValueError(f"Invalid {label}: {value}")
        parsed.setdefault(family_id.strip(), []).append(text.strip())
    return parsed


def _scores_from_args(values: Sequence[str]) -> dict[str, dict[str, int]]:
    scores: dict[str, dict[str, int]] = {}
    for value in values:
        family_criterion, separator, raw_score = value.partition("=")
        family_id, criterion = _split_family_criterion(family_criterion, value)
        if not separator:
            raise ValueError(f"Invalid score: {value}")
        scores.setdefault(family_id, {})[criterion] = _score_from_text(raw_score, value)
    return scores


def _split_family_criterion(family_criterion: str, original_value: str) -> tuple[str, str]:
    family_id, separator, criterion = family_criterion.partition(":")
    if not separator or not family_id.strip() or not criterion.strip():
        raise ValueError(f"Invalid score: {original_value}")
    return family_id.strip(), criterion.strip()


def _score_from_text(raw_score: str, original_value: str) -> int:
    try:
        return int(raw_score)
    except ValueError as exc:
        raise ValueError(f"Invalid score: {original_value}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
