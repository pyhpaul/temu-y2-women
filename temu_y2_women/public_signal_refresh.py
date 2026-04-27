from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen

from temu_y2_women.canonical_signal_builder import build_canonical_signals, build_signal_bundle
from temu_y2_women.errors import GenerationError
from temu_y2_women.public_source_adapter import resolve_public_source_adapter
from temu_y2_women.public_source_registry import load_public_source_registry, select_public_sources
from temu_y2_women.signal_ingestion import ingest_dress_signals


Fetcher = Callable[[str], str]
_CANONICAL_SCHEMA_VERSION = "canonical-signals-v1"


def run_public_signal_refresh(
    registry_path: Path,
    output_root: Path,
    fetched_at: str,
    fetcher: Fetcher | None = None,
    source_ids: list[str] | None = None,
) -> dict[str, Any]:
    try:
        registry_snapshot, registry = _load_registry_inputs(registry_path)
        selected_sources = select_public_sources(registry, source_ids)
        fetch = fetcher or _fetch_html
        raw_snapshots, errors = _collect_raw_snapshots(selected_sources, fetched_at, fetch)
        canonical_payload, errors = _build_canonical_payload(raw_snapshots, selected_sources, errors)
        if not canonical_payload["signals"]:
            return _refresh_error("sources", "no valid public sources produced canonical signals", errors)
        run_id = _build_run_id(fetched_at, selected_sources)
        run_dir = output_root / run_id
        bundle = build_signal_bundle(canonical_payload)
        ingestion_result = _run_signal_ingestion(run_dir, bundle)
        if "error" in ingestion_result:
            return ingestion_result
        report = _build_refresh_report(run_id, selected_sources, raw_snapshots, errors, canonical_payload, bundle, ingestion_result, fetched_at)
        _write_refresh_outputs(run_dir, registry_snapshot, raw_snapshots, canonical_payload, report)
        return report
    except GenerationError as error:
        return error.to_dict()


def _load_registry_inputs(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise GenerationError(
            code="INVALID_PUBLIC_SOURCE_REGISTRY",
            message="source registry root must be an object",
            details={"path": str(path), "field": "root"},
        )
    return payload, load_public_source_registry(path)


def _fetch_html(url: str) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 public-signal-refresh/1.0"})
    with urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def _build_run_id(fetched_at: str, selected_sources: list[dict[str, Any]]) -> str:
    suffix = _selected_source_suffix(selected_sources)
    return f"{fetched_at.replace(':', '-')}-{suffix}"


def _collect_raw_snapshots(
    registry: list[dict[str, Any]],
    fetched_at: str,
    fetcher: Fetcher,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    snapshots: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for source in registry:
        html = _fetch_source_html(source, fetcher, errors)
        if html is None:
            continue
        snapshot = _parse_source_snapshot(source, html, fetched_at, errors)
        if snapshot is not None:
            snapshots.append(snapshot)
    return snapshots, errors


def _fetch_source_html(
    source: dict[str, Any],
    fetcher: Fetcher,
    errors: list[dict[str, Any]],
) -> str | None:
    try:
        return fetcher(str(source["source_url"]))
    except Exception as error:
        errors.append(_source_error(source["source_id"], "fetch", error, "PUBLIC_SOURCE_FETCH_FAILED"))
        return None


def _parse_source_snapshot(
    source: dict[str, Any],
    html: str,
    fetched_at: str,
    errors: list[dict[str, Any]],
) -> dict[str, Any] | None:
    try:
        adapter = resolve_public_source_adapter(str(source["adapter_id"]))
        return adapter(source, html, fetched_at)
    except Exception as error:
        errors.append(_source_error(source["source_id"], "parse", error, "PUBLIC_SOURCE_PARSE_FAILED"))
        return None


def _build_canonical_payload(
    raw_snapshots: list[dict[str, Any]],
    selected_sources: list[dict[str, Any]],
    errors: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    signals: list[dict[str, Any]] = []
    source_defaults = {source["source_id"]: source["default_price_band"] for source in selected_sources}
    for snapshot in raw_snapshots:
        source_id = str(snapshot["source_id"])
        try:
            payload = build_canonical_signals(snapshot, source_defaults[source_id])
        except Exception as error:
            errors.append(_source_error(source_id, "canonicalize", error, "PUBLIC_SOURCE_CANONICALIZE_FAILED"))
            continue
        signals.extend(list(payload["signals"]))
    return {"schema_version": _CANONICAL_SCHEMA_VERSION, "signals": signals}, errors


def _run_signal_ingestion(run_dir: Path, bundle: dict[str, Any]) -> dict[str, Any]:
    run_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = run_dir / "signal_bundle.json"
    _write_json(bundle_path, bundle)
    return ingest_dress_signals(input_path=bundle_path, output_dir=run_dir)


def _build_refresh_report(
    run_id: str,
    registry: list[dict[str, Any]],
    raw_snapshots: list[dict[str, Any]],
    errors: list[dict[str, Any]],
    canonical_payload: dict[str, Any],
    bundle: dict[str, Any],
    ingestion_result: dict[str, Any],
    fetched_at: str,
) -> dict[str, Any]:
    warnings = _build_refresh_warnings(raw_snapshots, ingestion_result)
    successful_sources = _successful_source_ids(raw_snapshots, errors)
    selected_source_ids = [str(source["source_id"]) for source in registry]
    return {
        "schema_version": "public-refresh-report-v1",
        "run_id": run_id,
        "started_at": fetched_at,
        "completed_at": fetched_at,
        "selected_source_ids": selected_source_ids,
        "source_summary": _source_summary(registry, successful_sources),
        "source_details": _build_source_details(registry, raw_snapshots, errors, canonical_payload, ingestion_result),
        "canonical_signal_count": len(canonical_payload["signals"]),
        "signal_bundle_count": len(bundle["signals"]),
        "fallback_price_band_count": _fallback_price_band_count(canonical_payload),
        "coverage": {
            "matched_signals": ingestion_result["coverage"]["matched_signal_count"],
            "unmatched_signal_ids": list(ingestion_result["coverage"]["unmatched_signal_ids"]),
        },
        "warnings": warnings,
        "errors": errors,
    }


def _build_refresh_warnings(
    raw_snapshots: list[dict[str, Any]],
    ingestion_result: dict[str, Any],
) -> list[str]:
    warnings = list(ingestion_result.get("warnings", []))
    for snapshot in raw_snapshots:
        warnings.extend(str(item) for item in list(snapshot.get("warnings", [])))
    return warnings


def _source_summary(registry: list[dict[str, Any]], successful_sources: set[str]) -> dict[str, int]:
    succeeded = len(successful_sources)
    return {"total": len(registry), "succeeded": succeeded, "failed": len(registry) - succeeded}


def _fallback_price_band_count(canonical_payload: dict[str, Any]) -> int:
    return sum(1 for signal in canonical_payload["signals"] if signal["price_band_resolution"] == "source_default")


def _successful_source_ids(raw_snapshots: list[dict[str, Any]], errors: list[dict[str, Any]]) -> set[str]:
    failed_ids = {str(item["source_id"]) for item in errors if item["stage"] == "canonicalize"}
    return {str(snapshot["source_id"]) for snapshot in raw_snapshots if str(snapshot["source_id"]) not in failed_ids}


def _selected_source_suffix(selected_sources: list[dict[str, Any]]) -> str:
    source_ids = [str(source["source_id"]) for source in selected_sources]
    joined = "|".join(source_ids).encode("utf-8")
    return f"{len(source_ids)}sources-{hashlib.sha1(joined).hexdigest()[:6]}"


def _build_source_details(
    selected_sources: list[dict[str, Any]],
    raw_snapshots: list[dict[str, Any]],
    errors: list[dict[str, Any]],
    canonical_payload: dict[str, Any],
    ingestion_result: dict[str, Any],
) -> list[dict[str, Any]]:
    snapshot_lookup = {str(snapshot["source_id"]): snapshot for snapshot in raw_snapshots}
    errors_lookup = _group_source_errors(errors)
    signal_lookup = _signal_ids_by_source(canonical_payload)
    outcomes = _signal_outcomes_by_id(ingestion_result)
    return [
        _build_source_detail(source, snapshot_lookup, errors_lookup, signal_lookup, outcomes)
        for source in selected_sources
    ]


def _build_source_detail(
    source: dict[str, Any],
    snapshot_lookup: dict[str, dict[str, Any]],
    errors_lookup: dict[str, list[dict[str, Any]]],
    signal_lookup: dict[str, list[dict[str, Any]]],
    outcomes: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    source_id = str(source["source_id"])
    signals = signal_lookup.get(source_id, [])
    source_outcomes = [outcomes[signal["canonical_signal_id"]] for signal in signals if signal["canonical_signal_id"] in outcomes]
    return {
        "source_id": source_id,
        "adapter_id": source["adapter_id"],
        "priority": source["priority"],
        "weight": source["weight"],
        "status": "failed" if errors_lookup.get(source_id) else "succeeded",
        "signal_count": len(signals),
        "matched_signal_count": sum(1 for item in source_outcomes if item["status"] == "matched"),
        "unmatched_signal_count": sum(1 for item in source_outcomes if item["status"] == "unmatched"),
        "fallback_price_band_count": sum(1 for signal in signals if signal["price_band_resolution"] == "source_default"),
        "warnings": list(snapshot_lookup.get(source_id, {}).get("warnings", [])),
        "errors": list(errors_lookup.get(source_id, [])),
    }


def _group_source_errors(errors: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in errors:
        grouped.setdefault(str(item["source_id"]), []).append(item)
    return grouped


def _signal_ids_by_source(canonical_payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for signal in canonical_payload["signals"]:
        grouped.setdefault(str(signal["source_id"]), []).append(signal)
    return grouped


def _signal_outcomes_by_id(ingestion_result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    outcomes = ingestion_result.get("signal_outcomes", [])
    return {str(item["signal_id"]): item for item in outcomes}


def _write_refresh_outputs(
    run_dir: Path,
    registry_snapshot: dict[str, Any],
    raw_snapshots: list[dict[str, Any]],
    canonical_payload: dict[str, Any],
    report: dict[str, Any],
) -> None:
    _write_json(run_dir / "source_registry_snapshot.json", registry_snapshot)
    _write_raw_snapshots(run_dir / "raw_sources", raw_snapshots)
    _write_json(run_dir / "canonical_signals.json", canonical_payload)
    _write_json(run_dir / "refresh_report.json", report)


def _write_raw_snapshots(raw_dir: Path, raw_snapshots: list[dict[str, Any]]) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    for snapshot in raw_snapshots:
        _write_json(raw_dir / f"{snapshot['source_id']}.json", snapshot)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _source_error(source_id: str, stage: str, error: Exception, fallback_code: str) -> dict[str, Any]:
    if isinstance(error, GenerationError):
        error_code = error.code
    else:
        error_code = fallback_code
    return {"source_id": source_id, "stage": stage, "error_code": error_code, "message": str(error)}


def _refresh_error(field: str, message: str, errors: list[dict[str, Any]]) -> dict[str, Any]:
    return GenerationError(
        code="INVALID_PUBLIC_SIGNAL_REFRESH",
        message=message,
        details={"field": field, "errors": errors},
    ).to_dict()
