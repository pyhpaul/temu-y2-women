from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from temu_y2_women.errors import GenerationError
from temu_y2_women.image_generation_openai import build_routed_openai_image_provider
from temu_y2_women.image_generation_output import FakeImageProvider
from temu_y2_women.image_generation_workflow import render_dress_concept_image
from temu_y2_women.image_provider_config import ProviderCliOptions, resolve_openai_provider_configs


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render an image from a saved dress concept result.")
    parser.add_argument("--result", required=True, help="Path to the successful concept result JSON.")
    parser.add_argument("--output-dir", required=True, help="Directory for rendered image artifacts.")
    parser.add_argument("--provider", choices=("fake", "openai"), default="openai", help="Image provider to use.")
    parser.add_argument("--api-key", default=None, help="Override the OpenAI-compatible API key.")
    parser.add_argument("--base-url", default=None, help="Override the OpenAI-compatible API base URL.")
    parser.add_argument("--model", default="gpt-image-2", help="Image model name for the OpenAI provider.")
    parser.add_argument("--size", default="1024x1536", help="Image size for the OpenAI provider.")
    parser.add_argument("--quality", default="high", help="Image quality for the OpenAI provider.")
    parser.add_argument("--background", default="auto", help="Background mode for the OpenAI provider.")
    parser.add_argument("--style", default="natural", help="Image style for the OpenAI provider.")
    parser.add_argument("--prompt-id", action="append", default=[], help="Render only matching prompt_id; repeatable.")
    args = parser.parse_args(argv)
    result = _run_command(args)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if "error" not in result else 1


def _run_command(args: argparse.Namespace) -> dict[str, object]:
    try:
        provider = _provider_from_args(args)
    except GenerationError as error:
        return error.to_dict()
    return render_dress_concept_image(
        result_path=Path(args.result),
        output_dir=Path(args.output_dir),
        provider=provider,
        prompt_ids=tuple(args.prompt_id),
    )


def _provider_from_args(args: argparse.Namespace) -> object:
    if args.provider == "fake":
        return FakeImageProvider()
    return build_routed_openai_image_provider(_openai_provider_configs(args))


def _openai_provider_configs(args: argparse.Namespace):
    return resolve_openai_provider_configs(
        ProviderCliOptions(
            api_key=args.api_key,
            base_url=args.base_url,
            model=args.model,
            size=args.size,
            quality=args.quality,
            background=args.background,
            style=args.style,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
