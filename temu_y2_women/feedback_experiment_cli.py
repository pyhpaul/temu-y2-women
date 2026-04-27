from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from temu_y2_women.feedback_experiment_runner import (
    apply_feedback_experiment,
    prepare_feedback_experiment,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare or apply isolated feedback experiments.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_prepare_parser(subparsers)
    _add_apply_parser(subparsers)
    args = parser.parse_args(argv)
    result = _run_command(args)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if "error" not in result else 1


def _add_prepare_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("prepare", help="Create a workspace and baseline feedback review.")
    parser.add_argument("--request", required=True, help="Path to the source request JSON.")
    parser.add_argument("--experiment-root", required=True, help="Directory that will contain experiment workspaces.")
    parser.add_argument("--workspace-name", help="Optional fixed workspace directory name.")


def _add_apply_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("apply", help="Apply reviewed feedback inside an experiment workspace.")
    parser.add_argument("--reviewed", required=True, help="Path to the reviewed feedback JSON.")
    parser.add_argument("--manifest", required=True, help="Path to the experiment manifest JSON.")


def _run_command(args: argparse.Namespace) -> dict[str, object]:
    if args.command == "prepare":
        return prepare_feedback_experiment(
            request_path=Path(args.request),
            experiment_root=Path(args.experiment_root),
            workspace_name=args.workspace_name,
        )
    return apply_feedback_experiment(
        reviewed_path=Path(args.reviewed),
        manifest_path=Path(args.manifest),
    )


if __name__ == "__main__":
    raise SystemExit(main())
