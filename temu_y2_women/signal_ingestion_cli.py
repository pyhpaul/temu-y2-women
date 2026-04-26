from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from temu_y2_women.signal_ingestion import ingest_dress_signals


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest dress signal bundles into staged draft artifacts.")
    parser.add_argument("--input", required=True, help="Path to the raw signal JSON file.")
    parser.add_argument("--output-dir", required=True, help="Directory for staged output artifacts.")
    args = parser.parse_args(argv)

    result = ingest_dress_signals(
        input_path=Path(args.input),
        output_dir=Path(args.output_dir),
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if "error" not in result else 1
