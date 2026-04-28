from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from temu_y2_women.product_image_signal_run import run_product_image_signal_ingestion


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage structured dress evidence from local product images.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Observe local product images and write staged ingestion artifacts.")
    run_parser.add_argument("--input", required=True, help="Path to product image manifest JSON.")
    run_parser.add_argument("--output-root", required=True, help="Directory for staged run outputs.")
    run_parser.add_argument("--observed-at", required=True, help="ISO timestamp for this observation run.")

    args = parser.parse_args(argv)
    result = run_product_image_signal_ingestion(
        input_path=Path(args.input),
        output_root=Path(args.output_root),
        observed_at=str(args.observed_at),
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if "error" not in result else 1


if __name__ == "__main__":
    raise SystemExit(main())
