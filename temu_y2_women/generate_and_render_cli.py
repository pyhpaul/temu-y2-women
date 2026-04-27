from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable, Sequence

from temu_y2_women.generate_and_render_workflow import generate_and_render_dress_concept
from temu_y2_women.image_generation_openai import build_openai_image_provider
from temu_y2_women.image_generation_output import FakeImageProvider, ImageProvider


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a dress concept and render its image artifacts.")
    parser.add_argument("--input", required=True, help="Path to the request JSON file.")
    parser.add_argument("--output-dir", required=True, help="Directory for generated concept and render artifacts.")
    parser.add_argument("--provider", choices=("fake", "openai"), default="openai", help="Image provider to use.")
    parser.add_argument("--model", default="gpt-image-1", help="Image model name for the OpenAI provider.")
    parser.add_argument("--size", default="1024x1536", help="Image size for the OpenAI provider.")
    parser.add_argument("--quality", default="high", help="Image quality for the OpenAI provider.")
    parser.add_argument("--background", default="auto", help="Background mode for the OpenAI provider.")
    parser.add_argument("--style", default="natural", help="Image style for the OpenAI provider.")
    args = parser.parse_args(argv)
    result = generate_and_render_dress_concept(
        request_path=Path(args.input),
        output_dir=Path(args.output_dir),
        provider_factory=_provider_factory_from_args(args),
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if "error" not in result else 1


def _provider_factory_from_args(args: argparse.Namespace) -> Callable[[], ImageProvider]:
    if args.provider == "fake":
        return FakeImageProvider
    return lambda: build_openai_image_provider(
        model=args.model,
        size=args.size,
        quality=args.quality,
        background=args.background,
        style=args.style,
    )


if __name__ == "__main__":
    raise SystemExit(main())
