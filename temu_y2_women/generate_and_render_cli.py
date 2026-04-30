from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable, Sequence

from temu_y2_women.evidence_paths import EvidencePaths
from temu_y2_women.generate_and_render_workflow import generate_and_render_dress_concept
from temu_y2_women.image_generation_openai import build_routed_openai_image_provider
from temu_y2_women.image_generation_output import FakeImageProvider, ImageProvider
from temu_y2_women.image_provider_config import ProviderCliOptions, resolve_openai_provider_configs


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a dress concept and render its image artifacts.")
    parser.add_argument("--input", required=True, help="Path to the request JSON file.")
    parser.add_argument("--output-dir", required=True, help="Directory for generated concept and render artifacts.")
    parser.add_argument("--provider", choices=("fake", "openai"), default="openai", help="Image provider to use.")
    parser.add_argument("--api-key", default=None, help="Override the OpenAI-compatible API key.")
    parser.add_argument("--base-url", default=None, help="Override the OpenAI-compatible API base URL.")
    parser.add_argument("--model", default="gpt-image-2", help="Image model name for the OpenAI provider.")
    parser.add_argument("--size", default="1024x1536", help="Image size for the OpenAI provider.")
    parser.add_argument("--quality", default="high", help="Image quality for the OpenAI provider.")
    parser.add_argument("--background", default="auto", help="Background mode for the OpenAI provider.")
    parser.add_argument("--style", default="natural", help="Image style for the OpenAI provider.")
    parser.add_argument("--elements-path", help="Optional path to elements.json override.")
    parser.add_argument("--strategies-path", help="Optional path to strategy_templates.json override.")
    parser.add_argument("--taxonomy-path", help="Optional path to evidence_taxonomy.json override.")
    args = parser.parse_args(argv)
    result = generate_and_render_dress_concept(
        request_path=Path(args.input),
        output_dir=Path(args.output_dir),
        provider_factory=_provider_factory_from_args(args),
        evidence_paths=_evidence_paths_from_args(args),
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if "error" not in result else 1


def _provider_factory_from_args(args: argparse.Namespace) -> Callable[[], ImageProvider]:
    if args.provider == "fake":
        return FakeImageProvider
    return lambda: build_routed_openai_image_provider(_openai_provider_configs(args))


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


def _evidence_paths_from_args(args: argparse.Namespace) -> EvidencePaths | None:
    values = (
        getattr(args, "elements_path", None),
        getattr(args, "strategies_path", None),
        getattr(args, "taxonomy_path", None),
    )
    if not any(values):
        return None
    defaults = EvidencePaths.defaults()
    return EvidencePaths(
        elements_path=Path(args.elements_path) if args.elements_path else defaults.elements_path,
        strategies_path=Path(args.strategies_path) if args.strategies_path else defaults.strategies_path,
        taxonomy_path=Path(args.taxonomy_path) if args.taxonomy_path else defaults.taxonomy_path,
    )


if __name__ == "__main__":
    raise SystemExit(main())
