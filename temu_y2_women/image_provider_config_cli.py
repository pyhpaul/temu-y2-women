from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from temu_y2_women.errors import GenerationError
from temu_y2_women.image_provider_config import ProviderCliOptions, diagnose_openai_provider_config


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    payload = _run_command(args)
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if _has_default_api_key(payload) else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect OpenAI-compatible image provider configuration.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    diagnose_parser = subparsers.add_parser("diagnose", help="Print sanitized provider config diagnostics as JSON.")
    diagnose_parser.add_argument("--api-key", default=None, help="Override the default route API key.")
    diagnose_parser.add_argument("--base-url", default=None, help="Override the OpenAI-compatible API base URL.")
    diagnose_parser.add_argument("--model", default="gpt-image-2", help="Image model name.")
    diagnose_parser.add_argument("--codex-home", type=Path, default=None, help="Override CODEX_HOME for config lookup.")
    diagnose_parser.add_argument("--env-path", type=Path, default=None, help="Override the .env path for config lookup.")
    return parser


def _run_command(args: argparse.Namespace) -> dict[str, object]:
    try:
        return diagnose_openai_provider_config(
            ProviderCliOptions(
                api_key=args.api_key,
                base_url=args.base_url,
                model=args.model,
            ),
            codex_home=args.codex_home,
            env_path=args.env_path,
        )
    except GenerationError as error:
        return error.to_dict()


def _has_default_api_key(payload: dict[str, object]) -> bool:
    api_key = payload.get("api_key")
    return isinstance(api_key, dict) and api_key.get("present") is True


if __name__ == "__main__":
    raise SystemExit(main())
