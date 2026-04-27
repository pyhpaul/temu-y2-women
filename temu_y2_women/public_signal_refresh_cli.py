from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from temu_y2_women.public_signal_refresh import run_public_signal_refresh


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run public seasonal source refresh for dress evidence.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Fetch enabled public sources and write staged refresh artifacts.")
    run_parser.add_argument("--registry", default="data/refresh/dress/source_registry.json")
    run_parser.add_argument("--output-root", default="data/refresh/dress")
    run_parser.add_argument("--fetched-at", required=True)
    run_parser.add_argument("--source-id", action="append", dest="source_ids")

    args = parser.parse_args(argv)
    result = run_public_signal_refresh(
        registry_path=Path(args.registry),
        output_root=Path(args.output_root),
        fetched_at=str(args.fetched_at),
        source_ids=args.source_ids,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if "error" not in result else 1
