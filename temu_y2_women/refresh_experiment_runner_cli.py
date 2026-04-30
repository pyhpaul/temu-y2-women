from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    result = _run_command(args)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if "error" not in result else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare or apply isolated refresh experiments.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_prepare_parser(subparsers)
    _add_apply_parser(subparsers)
    return parser


def _add_prepare_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("prepare", help="Create a refresh experiment workspace.")
    parser.add_argument("--run-dir", required=True, help="Path to the refresh run directory.")
    parser.add_argument("--request-set", required=True, help="Path to the request set manifest JSON.")
    parser.add_argument("--experiment-root", required=True, help="Directory that will contain experiment workspaces.")
    parser.add_argument("--workspace-name", help="Optional fixed workspace directory name.")


def _add_apply_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("apply", help="Apply reviewed promotion decisions in a refresh workspace.")
    parser.add_argument("--manifest", required=True, help="Path to the experiment manifest JSON.")
    parser.add_argument("--reviewed", help="Optional path to the reviewed promotion JSON.")
    parser.add_argument(
        "--auto-accept-pending",
        action="store_true",
        help="Auto-convert pending review decisions to accept before apply.",
    )


def _run_command(args: argparse.Namespace) -> dict[str, object]:
    from temu_y2_women.refresh_experiment_runner import (
        apply_refresh_experiment,
        prepare_refresh_experiment,
    )

    if args.command == "prepare":
        return prepare_refresh_experiment(
            run_dir=Path(args.run_dir),
            request_set_path=Path(args.request_set),
            experiment_root=Path(args.experiment_root),
            workspace_name=args.workspace_name,
        )
    return apply_refresh_experiment(
        manifest_path=Path(args.manifest),
        reviewed_path=Path(args.reviewed) if args.reviewed else None,
        auto_accept_pending=bool(getattr(args, "auto_accept_pending", False)),
    )


if __name__ == "__main__":
    raise SystemExit(main())
