from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any
from uuid import uuid4

from temu_y2_women.errors import GenerationError
from temu_y2_women.evidence_paths import EvidencePaths
from temu_y2_women.orchestrator import generate_dress_concept
from temu_y2_women.refresh_run_promotion import (
    apply_reviewed_dress_promotion_from_refresh_run,
    prepare_dress_promotion_from_refresh_run,
)

_REQUEST_SET_SCHEMA_VERSION = "refresh-experiment-request-set-v1"
_MANIFEST_SCHEMA_VERSION = "refresh-experiment-manifest-v1"
_COMPARE_SCHEMA_VERSION = "refresh-experiment-compare-v1"
_REPORT_SCHEMA_VERSION = "refresh-experiment-report-v1"


@dataclass(frozen=True, slots=True)
class RefreshExperimentSourcePaths:
    evidence_paths: EvidencePaths


def prepare_refresh_experiment(
    run_dir: Path,
    request_set_path: Path,
    experiment_root: Path,
    workspace_name: str | None = None,
    source_paths: RefreshExperimentSourcePaths | None = None,
) -> dict[str, Any]:
    try:
        source = source_paths or RefreshExperimentSourcePaths(evidence_paths=EvidencePaths.defaults())
        request_set = _load_request_set_manifest(request_set_path)
        request_entries = _resolve_request_entries(request_set_path, request_set["requests"])
        experiment_id = _next_experiment_id()
        workspace_root = _resolve_workspace_root(experiment_root, workspace_name, experiment_id)
        workspace_paths = _workspace_paths(workspace_root)
        _copy_workspace_inputs(source.evidence_paths, workspace_paths["evidence_paths"])
        review_path = workspace_root / "promotion_review.json"
        promotion_review = prepare_dress_promotion_from_refresh_run(
            run_dir=run_dir,
            active_elements_path=workspace_paths["evidence_paths"].elements_path,
            active_strategies_path=workspace_paths["evidence_paths"].strategies_path,
            output_path=review_path,
            taxonomy_path=workspace_paths["evidence_paths"].taxonomy_path,
        )
        _raise_on_error_payload(promotion_review)
        request_records = _prepare_baseline_records(request_entries, workspace_paths["baseline_dir"], workspace_paths["evidence_paths"])
        manifest_path = workspace_root / "experiment_manifest.json"
        _write_json(
            manifest_path,
            _manifest_payload(experiment_id, run_dir, request_set, workspace_root, workspace_paths["evidence_paths"], review_path, request_records),
        )
        return _prepare_result(experiment_id, workspace_root, manifest_path, review_path, workspace_paths["baseline_dir"])
    except GenerationError as error:
        return error.to_dict()
    except OSError as error:
        return _io_error("failed to read or write refresh experiment artifacts", error).to_dict()


def apply_refresh_experiment(
    manifest_path: Path,
    reviewed_path: Path | None = None,
) -> dict[str, Any]:
    try:
        manifest_file = manifest_path.resolve()
        manifest = _load_json_object(manifest_file, "INVALID_REFRESH_EXPERIMENT_INPUT")
        context = _validated_manifest_context(manifest, manifest_file)
        workspace_root = context["workspace_root"]
        workspace_paths = context["evidence_paths"]
        resolved_reviewed_path = reviewed_path or context["promotion_review_path"]
        promotion_report_path = workspace_root / "promotion_report.json"
        apply_report = apply_reviewed_dress_promotion_from_refresh_run(
            run_dir=context["run_dir"],
            active_elements_path=workspace_paths.elements_path,
            active_strategies_path=workspace_paths.strategies_path,
            reviewed_path=resolved_reviewed_path,
            report_path=promotion_report_path,
            taxonomy_path=workspace_paths.taxonomy_path,
        )
        _raise_on_error_payload(apply_report)
        compare_records = _build_compare_records(context["requests"], workspace_paths, _accepted_evidence_summary(apply_report))
        experiment_report = _build_experiment_report(manifest, compare_records, apply_report)
        output_paths = _write_apply_outputs(workspace_root, compare_records, experiment_report)
        experiment_report_path = output_paths["experiment_report_path"]
        return _apply_result(manifest, promotion_report_path, experiment_report_path, output_paths)
    except GenerationError as error:
        return error.to_dict()
    except OSError as error:
        return _io_error("failed to read or write refresh experiment artifacts", error).to_dict()


def _load_request_set_manifest(path: Path) -> dict[str, Any]:
    payload = _load_json_object(path, "INVALID_REFRESH_EXPERIMENT_INPUT")
    if payload.get("schema_version") != _REQUEST_SET_SCHEMA_VERSION:
        raise _experiment_input_error(path, "schema_version", "unsupported request set schema version")
    if payload.get("category") != "dress":
        raise _experiment_input_error(path, "category", "refresh experiment currently supports dress only")
    requests = payload.get("requests")
    if not isinstance(requests, list) or not requests:
        raise _experiment_input_error(path, "requests", "request set must contain at least one request")
    _validate_request_entries(path, requests)
    return payload


def _validate_request_entries(path: Path, entries: list[Any]) -> None:
    seen_ids: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise _experiment_input_error(path, "requests", "each request entry must be an object")
        request_id = entry.get("request_id")
        request_path = entry.get("request_path")
        if not isinstance(request_id, str) or not request_id:
            raise _experiment_input_error(path, "request_id", "request_id must be a non-empty string")
        if request_id in seen_ids:
            raise _experiment_input_error(path, "request_id", "request_id values must be unique")
        if not isinstance(request_path, str) or not request_path:
            raise _experiment_input_error(path, "request_path", "request_path must be a non-empty string")
        seen_ids.add(request_id)


def _resolve_request_entries(request_set_path: Path, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    for entry in entries:
        request_path = Path(entry["request_path"])
        if not request_path.is_absolute():
            request_path = (request_set_path.parent / request_path).resolve()
        if not request_path.is_file():
            raise _experiment_input_error(request_set_path, "request_path", "request file does not exist")
        resolved.append({"request_id": entry["request_id"], "request_path": request_path})
    return resolved


def _resolve_workspace_root(experiment_root: Path, workspace_name: str | None, experiment_id: str) -> Path:
    base_root = experiment_root.resolve()
    workspace_root = (base_root / (workspace_name or experiment_id)).resolve()
    if not _path_is_within(workspace_root, base_root):
        raise _experiment_input_error(base_root, "workspace_name", "workspace_name must stay within experiment_root")
    workspace_root.mkdir(parents=True, exist_ok=False)
    return workspace_root


def _workspace_paths(workspace_root: Path) -> dict[str, Any]:
    evidence_root = workspace_root / "data" / "mvp" / "dress"
    return {
        "evidence_paths": EvidencePaths(
            elements_path=evidence_root / "elements.json",
            strategies_path=evidence_root / "strategy_templates.json",
            taxonomy_path=evidence_root / "evidence_taxonomy.json",
        ),
        "baseline_dir": workspace_root / "baseline",
    }


def _manifest_workspace_paths(manifest: dict[str, Any]) -> EvidencePaths:
    return EvidencePaths(
        elements_path=Path(manifest["active_elements_path"]),
        strategies_path=Path(manifest["active_strategies_path"]),
        taxonomy_path=Path(manifest["taxonomy_path"]),
    )


def _copy_workspace_inputs(source_paths: EvidencePaths, destination_paths: EvidencePaths) -> None:
    destination_paths.elements_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_paths.elements_path, destination_paths.elements_path)
    shutil.copyfile(source_paths.strategies_path, destination_paths.strategies_path)
    shutil.copyfile(source_paths.taxonomy_path, destination_paths.taxonomy_path)


def _prepare_baseline_records(
    request_entries: list[dict[str, Any]],
    baseline_dir: Path,
    evidence_paths: EvidencePaths,
) -> list[dict[str, Any]]:
    baseline_dir.mkdir(parents=True, exist_ok=False)
    records: list[dict[str, Any]] = []
    for entry in request_entries:
        request_payload = _load_json_object(entry["request_path"], "INVALID_REFRESH_EXPERIMENT_INPUT")
        result = generate_dress_concept(request_payload, evidence_paths=evidence_paths)
        _raise_on_generation_error(result, entry["request_id"], "baseline")
        baseline_path = baseline_dir / f"{entry['request_id']}.json"
        _write_json(baseline_path, result)
        records.append(_request_record(entry["request_id"], entry["request_path"], baseline_path, request_payload))
    return records


def _request_record(
    request_id: str,
    request_path: Path,
    baseline_result_path: Path,
    request_payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "request_path": str(request_path.resolve()),
        "request_fingerprint": _request_fingerprint(request_payload),
        "baseline_result_path": str(baseline_result_path.resolve()),
    }


def _manifest_payload(
    experiment_id: str,
    run_dir: Path,
    request_set: dict[str, Any],
    workspace_root: Path,
    evidence_paths: EvidencePaths,
    review_path: Path,
    request_records: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": _MANIFEST_SCHEMA_VERSION,
        "experiment_id": experiment_id,
        "category": request_set["category"],
        "request_set_schema_version": request_set["schema_version"],
        "request_count": len(request_records),
        "run_dir": str(run_dir.resolve()),
        "workspace_root": str(workspace_root.resolve()),
        "promotion_review_path": str(review_path.resolve()),
        "active_elements_path": str(evidence_paths.elements_path.resolve()),
        "active_strategies_path": str(evidence_paths.strategies_path.resolve()),
        "taxonomy_path": str(evidence_paths.taxonomy_path.resolve()),
        "requests": request_records,
        "created_at": _current_timestamp(),
    }


def _prepare_result(
    experiment_id: str,
    workspace_root: Path,
    manifest_path: Path,
    review_path: Path,
    baseline_dir: Path,
) -> dict[str, Any]:
    return {
        "experiment_id": experiment_id,
        "workspace_root": str(workspace_root.resolve()),
        "manifest_path": str(manifest_path.resolve()),
        "promotion_review_path": str(review_path.resolve()),
        "baseline_dir": str(baseline_dir.resolve()),
    }


def _build_compare_records(
    requests: list[dict[str, Any]],
    evidence_paths: EvidencePaths,
    accepted_evidence: dict[str, Any],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for entry in requests:
        baseline = _load_json_object(Path(entry["baseline_result_path"]), "INVALID_REFRESH_EXPERIMENT_INPUT")
        request_payload = _load_json_object(Path(entry["request_path"]), "INVALID_REFRESH_EXPERIMENT_INPUT")
        _validate_request_fingerprint(entry, request_payload)
        rerun = generate_dress_concept(request_payload, evidence_paths=evidence_paths)
        _raise_on_generation_error(rerun, entry["request_id"], "post_apply")
        records.append(
            {
                "request_id": entry["request_id"],
                "rerun": rerun,
                "compare": _compare_payload(entry["request_id"], baseline, rerun, accepted_evidence),
            }
        )
    return records


def _compare_payload(
    request_id: str,
    baseline: dict[str, Any],
    rerun: dict[str, Any],
    accepted_evidence: dict[str, Any],
) -> dict[str, Any]:
    selected_changes = _selected_element_changes(baseline["composed_concept"]["selected_elements"], rerun["composed_concept"]["selected_elements"])
    retrieval_changes = _retrieval_rank_changes(baseline["retrieved_elements"], rerun["retrieved_elements"], accepted_evidence["element_ids"])
    score_delta = round(rerun["composed_concept"]["concept_score"] - baseline["composed_concept"]["concept_score"], 4)
    factory_spec_changes = _factory_spec_changes(baseline["factory_spec"], rerun["factory_spec"])
    return {
        "schema_version": _COMPARE_SCHEMA_VERSION,
        "request_id": request_id,
        "change_type": _classify_change(selected_changes, retrieval_changes, score_delta, factory_spec_changes),
        "baseline_summary": _result_summary(baseline),
        "post_apply_summary": _result_summary(rerun),
        "diff": {
            "selected_element_changes": selected_changes,
            "retrieval_rank_changes": retrieval_changes,
            "concept_score_delta": score_delta,
            "factory_spec_changes": factory_spec_changes,
        },
        "accepted_evidence": accepted_evidence,
    }


def _write_apply_outputs(
    workspace_root: Path,
    compare_records: list[dict[str, Any]],
    experiment_report: dict[str, Any],
) -> dict[str, Path]:
    staging = _staging_apply_paths(workspace_root)
    final_paths = _final_apply_paths(workspace_root)
    try:
        staging["post_apply_dir"].mkdir(parents=True, exist_ok=False)
        staging["compare_dir"].mkdir(parents=True, exist_ok=False)
        for record in compare_records:
            request_id = record["request_id"]
            _write_json(staging["post_apply_dir"] / f"{request_id}.json", record["rerun"])
            _write_json(staging["compare_dir"] / f"{request_id}.json", record["compare"])
        _write_json(staging["experiment_report_path"], experiment_report)
        _replace_path(final_paths["post_apply_dir"], staging["post_apply_dir"])
        _replace_path(final_paths["compare_dir"], staging["compare_dir"])
        _replace_path(final_paths["experiment_report_path"], staging["experiment_report_path"])
        return final_paths
    except OSError:
        _cleanup_path(final_paths["post_apply_dir"])
        _cleanup_path(final_paths["compare_dir"])
        _cleanup_path(final_paths["experiment_report_path"])
        _cleanup_path(staging["post_apply_dir"])
        _cleanup_path(staging["compare_dir"])
        _cleanup_path(staging["experiment_report_path"])
        raise


def _build_experiment_report(
    manifest: dict[str, Any],
    compare_records: list[dict[str, Any]],
    apply_report: dict[str, Any],
) -> dict[str, Any]:
    compare_payloads = [record["compare"] for record in compare_records]
    return {
        "schema_version": _REPORT_SCHEMA_VERSION,
        "experiment_id": manifest["experiment_id"],
        "request_count": len(compare_payloads),
        "change_summary": _change_summary(compare_payloads),
        "score_summary": _score_summary(compare_payloads),
        "slot_change_summary": _slot_change_summary(compare_payloads),
        "accepted_evidence_summary": _accepted_evidence_summary(apply_report),
        "request_reports": _request_reports(compare_payloads, Path(manifest["workspace_root"]) / "compare"),
    }


def _apply_result(
    manifest: dict[str, Any],
    promotion_report_path: Path,
    experiment_report_path: Path,
    output_paths: dict[str, Path],
) -> dict[str, Any]:
    return {
        "experiment_id": manifest["experiment_id"],
        "workspace_root": manifest["workspace_root"],
        "promotion_report_path": str(promotion_report_path),
        "post_apply_dir": str(output_paths["post_apply_dir"]),
        "compare_dir": str(output_paths["compare_dir"]),
        "experiment_report_path": str(experiment_report_path),
    }


def _accepted_evidence_summary(apply_report: dict[str, Any]) -> dict[str, Any]:
    element_ids = sorted({item["element_id"] for item in apply_report.get("elements", []) if item.get("decision") == "accept"})
    strategy_ids = sorted({item["strategy_id"] for item in apply_report.get("strategy_hints", []) if item.get("decision") == "accept"})
    source_signal_ids = sorted(
        {
            signal_id
            for section in ("elements", "strategy_hints")
            for item in apply_report.get(section, [])
            if item.get("decision") == "accept"
            for signal_id in item.get("source_signal_ids", [])
        }
    )
    return {"element_ids": element_ids, "strategy_ids": strategy_ids, "source_signal_ids": source_signal_ids}


def _selected_element_changes(
    baseline_selected: dict[str, Any],
    rerun_selected: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    changes: dict[str, dict[str, Any]] = {}
    for slot in sorted(set(baseline_selected) | set(rerun_selected)):
        before = baseline_selected.get(slot)
        after = rerun_selected.get(slot)
        if before == after:
            continue
        changes[slot] = {"before": before, "after": after}
    return changes


def _retrieval_rank_changes(
    baseline_retrieved: list[dict[str, Any]],
    rerun_retrieved: list[dict[str, Any]],
    accepted_element_ids: list[str],
) -> list[dict[str, Any]]:
    baseline_index = _retrieval_index(baseline_retrieved)
    rerun_index = _retrieval_index(rerun_retrieved)
    tracked_ids = sorted(set(accepted_element_ids) | set(baseline_index) | set(rerun_index))
    changes: list[dict[str, Any]] = []
    for element_id in tracked_ids:
        before = baseline_index.get(element_id)
        after = rerun_index.get(element_id)
        if before == after:
            continue
        changes.append({"element_id": element_id, "before": before, "after": after})
    return changes


def _retrieval_index(retrieved: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        item["element_id"]: {"rank": index, "effective_score": item["effective_score"]}
        for index, item in enumerate(retrieved, start=1)
    }


def _factory_spec_changes(
    baseline_factory_spec: dict[str, Any],
    rerun_factory_spec: dict[str, Any],
) -> dict[str, Any]:
    baseline_known = baseline_factory_spec["known"]
    rerun_known = rerun_factory_spec["known"]
    changed_fields = sorted(field for field in set(baseline_known) | set(rerun_known) if baseline_known.get(field) != rerun_known.get(field))
    slot_changes = sorted(
        slot
        for slot in set(baseline_known["selected_elements"]) | set(rerun_known["selected_elements"])
        if baseline_known["selected_elements"].get(slot) != rerun_known["selected_elements"].get(slot)
    )
    return {
        "changed": bool(changed_fields or baseline_factory_spec["unresolved"] != rerun_factory_spec["unresolved"]),
        "known_field_changes": changed_fields,
        "selected_element_slots_changed": slot_changes,
        "unresolved_count_before": len(baseline_factory_spec["unresolved"]),
        "unresolved_count_after": len(rerun_factory_spec["unresolved"]),
    }


def _classify_change(
    selected_changes: dict[str, Any],
    retrieval_changes: list[dict[str, Any]],
    score_delta: float,
    factory_spec_changes: dict[str, Any],
) -> str:
    if selected_changes:
        return "selection_changed"
    if retrieval_changes:
        return "retrieval_changed_only"
    if score_delta != 0:
        return "score_changed_only"
    if factory_spec_changes["changed"]:
        return "factory_spec_changed_only"
    return "no_observable_change"


def _result_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "concept_score": result["composed_concept"]["concept_score"],
        "selected_elements": result["composed_concept"]["selected_elements"],
        "factory_spec": _factory_spec_summary(result["factory_spec"]),
    }


def _factory_spec_summary(factory_spec: dict[str, Any]) -> dict[str, Any]:
    known = factory_spec["known"]
    return {
        "selected_strategy_ids": known["selected_strategy_ids"],
        "selected_elements": known["selected_elements"],
        "unresolved_count": len(factory_spec["unresolved"]),
    }


def _change_summary(compare_payloads: list[dict[str, Any]]) -> dict[str, int]:
    summary = {
        "selection_changed": 0,
        "retrieval_changed_only": 0,
        "score_changed_only": 0,
        "factory_spec_changed_only": 0,
        "no_observable_change": 0,
    }
    for payload in compare_payloads:
        summary[payload["change_type"]] += 1
    return summary


def _score_summary(compare_payloads: list[dict[str, Any]]) -> dict[str, Any]:
    deltas = [payload["diff"]["concept_score_delta"] for payload in compare_payloads]
    changed = [delta for delta in deltas if delta != 0]
    return {
        "changed_request_count": len(changed),
        "average_delta": round(sum(deltas) / len(deltas), 4) if deltas else 0.0,
        "max_delta": max(deltas, default=0.0),
        "min_delta": min(deltas, default=0.0),
    }


def _slot_change_summary(compare_payloads: list[dict[str, Any]]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for payload in compare_payloads:
        for slot in payload["diff"]["selected_element_changes"]:
            summary[slot] = summary.get(slot, 0) + 1
    return summary


def _request_reports(compare_payloads: list[dict[str, Any]], compare_dir: Path) -> list[dict[str, Any]]:
    return [
        {
            "request_id": payload["request_id"],
            "change_type": payload["change_type"],
            "compare_path": str(compare_dir / f"{payload['request_id']}.json"),
        }
        for payload in compare_payloads
    ]


def _load_json_object(path: Path, error_code: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise GenerationError(
            code=error_code,
            message="input file must contain valid JSON",
            details={"path": str(path), "line": error.lineno, "column": error.colno},
        ) from error
    if isinstance(payload, dict):
        return payload
    raise GenerationError(
        code=error_code,
        message="input root must be an object",
        details={"path": str(path)},
    )


def _validated_manifest_context(manifest: dict[str, Any], manifest_path: Path) -> dict[str, Any]:
    if manifest.get("schema_version") != _MANIFEST_SCHEMA_VERSION:
        raise _experiment_input_error(manifest_path, "schema_version", "unsupported refresh experiment manifest schema version")
    workspace_root = _absolute_manifest_path(manifest, manifest_path, "workspace_root")
    context = {
        "workspace_root": workspace_root,
        "run_dir": _absolute_manifest_path(manifest, manifest_path, "run_dir"),
        "promotion_review_path": _workspace_manifest_path(manifest, manifest_path, workspace_root, "promotion_review_path"),
        "evidence_paths": EvidencePaths(
            elements_path=_workspace_manifest_path(manifest, manifest_path, workspace_root, "active_elements_path"),
            strategies_path=_workspace_manifest_path(manifest, manifest_path, workspace_root, "active_strategies_path"),
            taxonomy_path=_workspace_manifest_path(manifest, manifest_path, workspace_root, "taxonomy_path"),
        ),
    }
    context["requests"] = _validated_manifest_requests(manifest, manifest_path, workspace_root)
    return context


def _validated_manifest_requests(
    manifest: dict[str, Any],
    manifest_path: Path,
    workspace_root: Path,
) -> list[dict[str, Any]]:
    requests = manifest.get("requests")
    if not isinstance(requests, list) or not requests:
        raise _experiment_input_error(manifest_path, "requests", "manifest must contain at least one request record")
    records: list[dict[str, Any]] = []
    for record in requests:
        if not isinstance(record, dict):
            raise _experiment_input_error(manifest_path, "requests", "manifest request record must be an object")
        request_id = record.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            raise _experiment_input_error(manifest_path, "request_id", "manifest request_id must be a non-empty string")
        records.append(
            {
                "request_id": request_id,
                "request_path": _absolute_record_path(record, manifest_path, "request_path"),
                "baseline_result_path": _workspace_record_path(record, manifest_path, workspace_root, "baseline_result_path"),
                "request_fingerprint": _request_fingerprint_value(record, manifest_path),
            }
        )
    return records


def _absolute_manifest_path(manifest: dict[str, Any], manifest_path: Path, field: str) -> Path:
    value = manifest.get(field)
    if not isinstance(value, str) or not value:
        raise _experiment_input_error(manifest_path, field, "manifest field must be a non-empty path string")
    path = Path(value)
    if not path.is_absolute():
        raise _experiment_input_error(manifest_path, field, "manifest path must be absolute")
    return path


def _workspace_manifest_path(manifest: dict[str, Any], manifest_path: Path, workspace_root: Path, field: str) -> Path:
    path = _absolute_manifest_path(manifest, manifest_path, field)
    if _path_is_within(path, workspace_root):
        return path
    raise _experiment_input_error(manifest_path, field, "manifest path must stay within workspace_root")


def _absolute_record_path(record: dict[str, Any], manifest_path: Path, field: str) -> Path:
    value = record.get(field)
    if not isinstance(value, str) or not value:
        raise _experiment_input_error(manifest_path, field, "manifest request field must be a non-empty path string")
    path = Path(value)
    if path.is_absolute():
        return path
    raise _experiment_input_error(manifest_path, field, "manifest request path must be absolute")


def _workspace_record_path(record: dict[str, Any], manifest_path: Path, workspace_root: Path, field: str) -> Path:
    path = _absolute_record_path(record, manifest_path, field)
    if _path_is_within(path, workspace_root):
        return path
    raise _experiment_input_error(manifest_path, field, "manifest request path must stay within workspace_root")


def _request_fingerprint_value(record: dict[str, Any], manifest_path: Path) -> str:
    value = record.get("request_fingerprint")
    if isinstance(value, str) and value:
        return value
    raise _experiment_input_error(manifest_path, "request_fingerprint", "manifest request fingerprint must be a non-empty string")


def _validate_request_fingerprint(entry: dict[str, Any], request_payload: dict[str, Any]) -> None:
    current = _request_fingerprint(request_payload)
    if current == entry["request_fingerprint"]:
        return
    raise _experiment_input_error(Path(entry["request_path"]), "request_fingerprint", "request payload changed since prepare")


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _staging_apply_paths(workspace_root: Path) -> dict[str, Path]:
    return {
        "post_apply_dir": workspace_root / ".post_apply.staging",
        "compare_dir": workspace_root / ".compare.staging",
        "experiment_report_path": workspace_root / ".experiment_report.staging.json",
    }


def _final_apply_paths(workspace_root: Path) -> dict[str, Path]:
    return {
        "post_apply_dir": workspace_root / "post_apply",
        "compare_dir": workspace_root / "compare",
        "experiment_report_path": workspace_root / "experiment_report.json",
    }


def _replace_path(destination: Path, source: Path) -> None:
    _cleanup_path(destination)
    source.replace(destination)


def _cleanup_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
        return
    if path.exists():
        path.unlink()


def _raise_on_error_payload(payload: dict[str, Any]) -> None:
    error = payload.get("error")
    if error is None:
        return
    raise GenerationError(
        code=error["code"],
        message=error["message"],
        details=error.get("details", {}),
    )


def _raise_on_generation_error(result: dict[str, Any], request_id: str, stage: str) -> None:
    error = result.get("error")
    if error is None:
        return
    raise GenerationError(
        code="REFRESH_EXPERIMENT_FAILED",
        message=f"{stage} generation failed for refresh experiment request",
        details={"request_id": request_id, "stage": stage, "source_code": error["code"]},
    )


def _experiment_input_error(path: Path, field: str, message: str) -> GenerationError:
    return GenerationError(
        code="INVALID_REFRESH_EXPERIMENT_INPUT",
        message=message,
        details={"path": str(path), "field": field},
    )


def _io_error(message: str, error: OSError) -> GenerationError:
    return GenerationError(
        code="REFRESH_EXPERIMENT_FAILED",
        message=message,
        details={"path": str(getattr(error, "filename", ""))},
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _request_fingerprint(payload: dict[str, Any]) -> str:
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _current_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _next_experiment_id() -> str:
    return f"exp-{uuid4().hex[:12]}"
