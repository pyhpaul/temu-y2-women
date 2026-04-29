from __future__ import annotations

import argparse
import json
from typing import Sequence

from temu_y2_women.errors import GenerationError
from temu_y2_women.image_gateway_smoke import GatewaySmokeSettings, VALID_SMOKE_CHECK_IDS, run_gateway_smoke
from temu_y2_women.image_provider_config import ProviderCliOptions, resolve_openai_provider_configs


_DEFAULT_BASE_URL = "https://api.openai.com/v1"


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    result = _run_command(args)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if _is_success_result(result) else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run raw HTTP smoke checks against an OpenAI-compatible image gateway.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run", help="Execute the default or selected smoke checks.")
    run_parser.add_argument("--check", choices=VALID_SMOKE_CHECK_IDS, action="append", dest="checks")
    run_parser.add_argument("--model", default="gpt-image-2", help="Image model name to probe.")
    run_parser.add_argument("--base-url", default=None, help="Override the OpenAI-compatible API base URL.")
    run_parser.add_argument("--anchor-api-key", default=None, help="Override the anchor route API key.")
    run_parser.add_argument("--expansion-api-key", default=None, help="Override the expansion route API key.")
    run_parser.add_argument("--timeout-sec", type=float, default=90.0, help="Per-request timeout in seconds.")
    return parser


def _run_command(args: argparse.Namespace) -> dict[str, object]:
    try:
        return run_gateway_smoke(_smoke_settings_from_args(args), check_ids=args.checks)
    except GenerationError as error:
        return error.to_dict()


def _smoke_settings_from_args(args: argparse.Namespace) -> GatewaySmokeSettings:
    configs = resolve_openai_provider_configs(
        ProviderCliOptions(
            api_key=args.anchor_api_key,
            base_url=args.base_url,
            model=args.model,
        )
    )
    return GatewaySmokeSettings(
        base_url=configs.default_config.base_url or _DEFAULT_BASE_URL,
        model=configs.default_config.model,
        anchor_api_key=configs.default_config.api_key,
        expansion_api_key=_expansion_api_key(args.expansion_api_key, configs),
        timeout_sec=args.timeout_sec,
    )


def _expansion_api_key(override_value: str | None, configs: object) -> str:
    explicit_value = _normalized_text(override_value)
    if explicit_value:
        return explicit_value
    expansion_config = getattr(configs, "expansion_config", None)
    if expansion_config is not None:
        return getattr(expansion_config, "api_key")
    return getattr(configs, "default_config").api_key


def _normalized_text(value: str | None) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _is_success_result(result: dict[str, object]) -> bool:
    if "error" in result:
        return False
    summary = result.get("summary", {})
    if isinstance(summary, dict):
        return summary.get("failed", 1) == 0
    return False


if __name__ == "__main__":
    raise SystemExit(main())
