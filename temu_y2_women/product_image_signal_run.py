from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from temu_y2_women.errors import GenerationError
from temu_y2_women.product_image_observer import observe_product_images
from temu_y2_women.product_image_observer_openai import build_openai_product_image_observer
from temu_y2_women.product_image_signal_builder import build_product_image_signal_bundle
from temu_y2_women.signal_ingestion import ingest_dress_signals


ImageObserver = Callable[[dict[str, Any]], dict[str, Any]]


def run_product_image_signal_ingestion(
    input_path: Path,
    output_root: Path,
    observed_at: str,
    observe_image: ImageObserver | None = None,
) -> dict[str, Any]:
    try:
        manifest = _read_manifest(input_path)
        observer, observation_model = _resolve_observer(observe_image)
        observations = observe_product_images(manifest, observation_model, observer)
        bundle = build_product_image_signal_bundle(manifest, observations, observed_at)
        run_id = _build_run_id(observed_at, manifest)
        run_dir = output_root / run_id
        _write_json(run_dir / "input_manifest_snapshot.json", manifest)
        _write_json(run_dir / "image_observations.json", observations)
        _write_json(run_dir / "signal_bundle.json", bundle)
        ingestion_report = ingest_dress_signals(run_dir / "signal_bundle.json", run_dir)
        if "error" in ingestion_report:
            return ingestion_report
        report = _build_run_report(run_id, manifest, observations, bundle, ingestion_report)
        _write_json(run_dir / "product_image_run_report.json", report)
        return report
    except GenerationError as error:
        return error.to_dict()


def _read_manifest(input_path: Path) -> dict[str, Any]:
    return json.loads(input_path.read_text(encoding="utf-8"))


def _resolve_observer(observe_image: ImageObserver | None) -> tuple[ImageObserver, str]:
    if observe_image is not None:
        return observe_image, _observer_label(observe_image)
    observer = build_openai_product_image_observer()
    return observer.observe_image, "gpt-4.1-mini"


def _observer_label(observer: ImageObserver) -> str:
    name = getattr(observer, "__name__", "").strip("_")
    if not name:
        return "custom-product-image-observer"
    return name.replace("_", "-")


def _build_run_id(observed_at: str, manifest: dict[str, Any]) -> str:
    product_ids = [str(product["product_id"]) for product in manifest["products"]]
    digest = hashlib.sha1("|".join(product_ids).encode("utf-8")).hexdigest()[:6]
    return f"{observed_at.replace(':', '-')}-{len(product_ids)}products-{digest}"


def _build_run_report(
    run_id: str,
    manifest: dict[str, Any],
    observations: dict[str, Any],
    bundle: dict[str, Any],
    ingestion_report: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "product-image-run-report-v1",
        "run_id": run_id,
        "input_product_count": len(manifest["products"]),
        "input_image_count": _input_image_count(manifest),
        "observed_product_count": len(observations["products"]),
        "signal_bundle_count": len(bundle["signals"]),
        "structured_candidate_count": _structured_candidate_count(bundle),
        "coverage": _coverage(ingestion_report),
        "warnings": _observation_warnings(observations),
        "errors": [],
    }


def _input_image_count(manifest: dict[str, Any]) -> int:
    return sum(len(product["images"]) for product in manifest["products"])


def _structured_candidate_count(bundle: dict[str, Any]) -> int:
    return sum(len(signal.get("structured_candidates", [])) for signal in bundle["signals"])


def _coverage(ingestion_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "matched_signals": ingestion_report["coverage"]["matched_signal_count"],
        "unmatched_signal_ids": list(ingestion_report["coverage"]["unmatched_signal_ids"]),
    }


def _observation_warnings(observations: dict[str, Any]) -> list[str]:
    ordered: list[str] = []
    for product in observations["products"]:
        for image in product["images"]:
            for warning in image.get("warnings", []):
                if warning not in ordered:
                    ordered.append(str(warning))
    return ordered


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
