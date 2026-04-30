from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
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

_REQUIRED_RUN_FILES = (
    "draft_elements.json",
    "draft_strategy_hints.json",
    "ingestion_report.json",
    "refresh_report.json",
)


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
        request_set = _load_request_set(request_set_path)
        source = source_paths or RefreshExperimentSourcePaths(EvidencePaths.defaults())
        experiment_id = _next_experiment_id()
        workspace_root = _resolve_workspace_root(experiment_root, workspace_name, experiment_id)
        workspace_paths = _workspace_paths(workspace_root)
        _copy_workspace_inputs(run_dir, source.evidence_paths, workspace_paths)
        baseline = _run_request_set(request_set_path, request_set, workspace_paths["evidence_paths"])
        baseline_path = workspace_root / "baseline_results.json"
        _write_json(baseline_path, baseline)
        review = prepare_dress_promotion_from_refresh_run(
            run_dir=workspace_paths["run_dir"],
            active_elements_path=workspace_paths["evidence_paths"].elements_path,
            active_strategies_path=workspace_paths["evidence_paths"].strategies_path,
            taxonomy_path=workspace_paths["evidence_paths"].taxonomy_path,
        )
        if "error" in review:
            return review
        manifest_path = workspace_root / "experiment_manifest.json"
        _write_json(manifest_path, _manifest_payload(experiment_id, request_set_path, workspace_root, workspace_paths, baseline_path))
        return _prepare_result(experiment_id, workspace_root, manifest_path, baseline_path, workspace_paths["run_dir"] / "promotion_review.json")
    except GenerationError as error:
        return error.to_dict()
    except OSError as error:
        return _io_error(error).to_dict()


def apply_refresh_experiment(
    manifest_path: Path,
    reviewed_path: Path | None = None,
    auto_accept_pending: bool = False,
) -> dict[str, Any]:
    try:
        manifest = _load_json_object(manifest_path)
        workspace_root = Path(manifest["workspace_root"])
        workspace_paths = _manifest_workspace_paths(manifest)
        resolved_reviewed_path = _resolve_apply_reviewed_path(
            workspace_root,
            workspace_paths["run_dir"],
            reviewed_path,
            auto_accept_pending,
        )
        apply_report = apply_reviewed_dress_promotion_from_refresh_run(
            run_dir=workspace_paths["run_dir"],
            active_elements_path=workspace_paths["evidence_paths"].elements_path,
            active_strategies_path=workspace_paths["evidence_paths"].strategies_path,
            reviewed_path=resolved_reviewed_path,
            report_path=workspace_root / "promotion_report.json",
            taxonomy_path=workspace_paths["evidence_paths"].taxonomy_path,
        )
        if "error" in apply_report:
            return apply_report
        request_set_path = Path(manifest["request_set_path"])
        request_set = _load_request_set(request_set_path)
        post_apply = _run_request_set(request_set_path, request_set, workspace_paths["evidence_paths"])
        post_apply_path = workspace_root / "post_apply_results.json"
        _write_json(post_apply_path, post_apply)
        report_path = workspace_root / "experiment_report.json"
        report = _build_experiment_report(manifest, _load_json_object(Path(manifest["baseline_results_path"])), post_apply, apply_report)
        _write_json(report_path, report)
        return _apply_result(manifest, post_apply_path, workspace_root / "promotion_report.json", report_path)
    except GenerationError as error:
        return error.to_dict()
    except OSError as error:
        return _io_error(error).to_dict()


def _resolve_apply_reviewed_path(
    workspace_root: Path,
    run_dir: Path,
    reviewed_path: Path | None,
    auto_accept_pending: bool,
) -> Path | None:
    if not auto_accept_pending:
        return reviewed_path
    source_path = reviewed_path or _default_reviewed_path(run_dir)
    if source_path is None:
        return None
    output_path = workspace_root / "auto_reviewed_decisions.json"
    _write_json(output_path, _auto_accept_review_bundle(_load_json_object(source_path)))
    return output_path


def _default_reviewed_path(run_dir: Path) -> Path | None:
    for name in ("promotion_review.json", "reviewed_decisions.json"):
        path = run_dir / name
        if path.exists():
            return path
    return None


def _auto_accept_review_bundle(review: dict[str, Any]) -> dict[str, Any]:
    return {
        **review,
        "elements": [_auto_accept_review_record(item) for item in review.get("elements", [])],
        "strategy_hints": [_auto_accept_review_record(item) for item in review.get("strategy_hints", [])],
    }


def _auto_accept_review_record(record: dict[str, Any]) -> dict[str, Any]:
    updated = dict(record)
    if updated.get("decision") == "pending":
        updated["decision"] = "accept"
    return updated


def _load_request_set(path: Path) -> dict[str, Any]:
    payload = _load_json_object(path)
    if payload.get("schema_version") != "refresh-experiment-request-set-v1":
        raise _experiment_error(path, "schema_version", "request set schema_version is unsupported")
    requests = payload.get("requests")
    if isinstance(requests, list) and requests:
        return payload
    raise _experiment_error(path, "requests", "request set must contain a non-empty requests list")


def _resolve_workspace_root(experiment_root: Path, workspace_name: str | None, experiment_id: str) -> Path:
    workspace_root = experiment_root / (workspace_name or experiment_id)
    workspace_root.mkdir(parents=True, exist_ok=False)
    return workspace_root


def _workspace_paths(workspace_root: Path) -> dict[str, Any]:
    evidence_root = workspace_root / "data" / "mvp" / "dress"
    return {
        "run_dir": workspace_root / "refresh_run",
        "evidence_paths": EvidencePaths(
            elements_path=evidence_root / "elements.json",
            strategies_path=evidence_root / "strategy_templates.json",
            taxonomy_path=evidence_root / "evidence_taxonomy.json",
        ),
    }


def _copy_workspace_inputs(run_dir: Path, source: EvidencePaths, workspace_paths: dict[str, Any]) -> None:
    evidence_paths = workspace_paths["evidence_paths"]
    evidence_paths.elements_path.parent.mkdir(parents=True, exist_ok=True)
    workspace_paths["run_dir"].mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source.elements_path, evidence_paths.elements_path)
    shutil.copyfile(source.strategies_path, evidence_paths.strategies_path)
    shutil.copyfile(source.taxonomy_path, evidence_paths.taxonomy_path)
    for name in _REQUIRED_RUN_FILES:
        shutil.copyfile(run_dir / name, workspace_paths["run_dir"] / name)


def _run_request_set(
    request_set_path: Path,
    request_set: dict[str, Any],
    evidence_paths: EvidencePaths,
) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for item in request_set["requests"]:
        request_id = _request_id(request_set_path, item)
        request_payload = _load_json_object(_request_path(request_set_path, item))
        results[request_id] = _result_snapshot(generate_dress_concept(request_payload, evidence_paths=evidence_paths), request_id)
    return {"schema_version": "refresh-experiment-results-v1", "results": results}


def _request_id(request_set_path: Path, item: Any) -> str:
    if isinstance(item, dict) and isinstance(item.get("request_id"), str) and item["request_id"].strip():
        return str(item["request_id"])
    raise _experiment_error(request_set_path, "request_id", "request set item is missing request_id")


def _request_path(request_set_path: Path, item: Any) -> Path:
    request_path = item.get("request_path") if isinstance(item, dict) else None
    if isinstance(request_path, str) and request_path.strip():
        candidate = Path(request_path)
        if candidate.is_absolute() or candidate.exists():
            return candidate.resolve()
        return (request_set_path.parent / request_path).resolve()
    raise _experiment_error(request_set_path, "request_path", "request set item is missing request_path")


def _result_snapshot(result: dict[str, Any], request_id: str) -> dict[str, Any]:
    if "error" in result:
        raise GenerationError(code="REFRESH_EXPERIMENT_FAILED", message="request replay failed", details={"request_id": request_id})
    return {
        "selected_strategy_ids": [item["strategy_id"] for item in result["selected_strategies"]],
        "selected_elements": result["composed_concept"]["selected_elements"],
        "concept_score": result["composed_concept"]["concept_score"],
        "retrieved_elements": result["retrieved_elements"],
    }


def _manifest_payload(
    experiment_id: str,
    request_set_path: Path,
    workspace_root: Path,
    workspace_paths: dict[str, Any],
    baseline_path: Path,
) -> dict[str, Any]:
    evidence_paths = workspace_paths["evidence_paths"]
    return {
        "schema_version": "refresh-experiment-manifest-v1",
        "experiment_id": experiment_id,
        "request_set_path": str(request_set_path.resolve()),
        "workspace_root": str(workspace_root),
        "baseline_results_path": str(baseline_path),
        "promotion_review_path": str(workspace_paths["run_dir"] / "promotion_review.json"),
        "refresh_run_dir": str(workspace_paths["run_dir"]),
        "active_elements_path": str(evidence_paths.elements_path),
        "active_strategies_path": str(evidence_paths.strategies_path),
        "taxonomy_path": str(evidence_paths.taxonomy_path),
        "created_at": _current_timestamp(),
    }


def _prepare_result(
    experiment_id: str,
    workspace_root: Path,
    manifest_path: Path,
    baseline_path: Path,
    review_path: Path,
) -> dict[str, Any]:
    return {
        "experiment_id": experiment_id,
        "workspace_root": str(workspace_root),
        "manifest_path": str(manifest_path),
        "baseline_results_path": str(baseline_path),
        "promotion_review_path": str(review_path),
    }


def _manifest_workspace_paths(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_dir": Path(manifest["refresh_run_dir"]),
        "evidence_paths": EvidencePaths(
            elements_path=Path(manifest["active_elements_path"]),
            strategies_path=Path(manifest["active_strategies_path"]),
            taxonomy_path=Path(manifest["taxonomy_path"]),
        ),
    }


def _build_experiment_report(
    manifest: dict[str, Any],
    baseline: dict[str, Any],
    post_apply: dict[str, Any],
    apply_report: dict[str, Any],
) -> dict[str, Any]:
    request_ids = sorted(baseline["results"])
    requests = {request_id: _request_compare(baseline["results"][request_id], post_apply["results"][request_id]) for request_id in request_ids}
    return {
        "schema_version": "refresh-experiment-report-v1",
        "experiment_id": str(manifest["experiment_id"]),
        "request_count": len(request_ids),
        "summary": _report_summary(requests),
        "promotion_summary": apply_report.get("summary", {}),
        "requests": requests,
        "recorded_at": _current_timestamp(),
    }


def _request_compare(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    strategy_changes = _selected_strategy_changes(before["selected_strategy_ids"], after["selected_strategy_ids"])
    selected_changes = _selected_element_changes(before["selected_elements"], after["selected_elements"])
    retrieval_changes = _retrieval_changes(before["retrieved_elements"], after["retrieved_elements"])
    return {
        "change_type": _classify_change(strategy_changes, selected_changes, retrieval_changes),
        "selected_strategy_ids": strategy_changes,
        "concept_score_before": before["concept_score"],
        "concept_score_after": after["concept_score"],
        "concept_score_delta": round(after["concept_score"] - before["concept_score"], 4),
        "selected_element_changes": selected_changes,
        "retrieval_changes": retrieval_changes,
    }


def _selected_strategy_changes(before: list[str], after: list[str]) -> dict[str, list[str]]:
    return {"before": list(before), "after": list(after)}


def _selected_element_changes(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    changes: dict[str, Any] = {}
    for slot in sorted(before):
        if before[slot] != after.get(slot):
            changes[slot] = {"before": before[slot], "after": after.get(slot)}
    return changes


def _retrieval_changes(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> list[dict[str, Any]]:
    before_by_id = _retrieved_by_id(before)
    after_by_id = _retrieved_by_id(after)
    changes: list[dict[str, Any]] = []
    for element_id in sorted(set(before_by_id) | set(after_by_id)):
        left = before_by_id.get(element_id, {"rank": None, "effective_score": None})
        right = after_by_id.get(element_id, {"rank": None, "effective_score": None})
        if left == right:
            continue
        changes.append({"element_id": element_id, "before": left, "after": right})
    return changes


def _retrieved_by_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        item["element_id"]: {"rank": index, "effective_score": item["effective_score"]}
        for index, item in enumerate(items, start=1)
    }


def _classify_change(
    strategy_changes: dict[str, list[str]],
    selected_changes: dict[str, Any],
    retrieval_changes: list[dict[str, Any]],
) -> str:
    if selected_changes:
        return "selection_changed"
    if strategy_changes["before"] != strategy_changes["after"]:
        return "strategy_changed_only"
    if retrieval_changes:
        return "retrieval_changed_only"
    return "no_observable_change"


def _report_summary(requests: dict[str, dict[str, Any]]) -> dict[str, int]:
    return {
        "selection_changed": sum(1 for item in requests.values() if item["change_type"] == "selection_changed"),
        "strategy_changed_only": sum(1 for item in requests.values() if item["change_type"] == "strategy_changed_only"),
        "retrieval_changed_only": sum(1 for item in requests.values() if item["change_type"] == "retrieval_changed_only"),
        "no_observable_change": sum(1 for item in requests.values() if item["change_type"] == "no_observable_change"),
    }


def _apply_result(
    manifest: dict[str, Any],
    post_apply_path: Path,
    promotion_report_path: Path,
    experiment_report_path: Path,
) -> dict[str, Any]:
    return {
        "experiment_id": str(manifest["experiment_id"]),
        "post_apply_results_path": str(post_apply_path),
        "promotion_report_path": str(promotion_report_path),
        "experiment_report_path": str(experiment_report_path),
    }


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise GenerationError(
            code="INVALID_REFRESH_EXPERIMENT_INPUT",
            message="experiment input file must contain valid JSON",
            details={"path": str(path), "line": error.lineno, "column": error.colno},
        ) from error
    if isinstance(payload, dict):
        return payload
    raise _experiment_error(path, "root", "experiment input root must be an object")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _experiment_error(path: Path, field: str, message: str) -> GenerationError:
    return GenerationError(
        code="INVALID_REFRESH_EXPERIMENT_INPUT",
        message=message,
        details={"path": str(path), "field": field},
    )


def _current_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _next_experiment_id() -> str:
    return f"exp-{uuid4().hex[:12]}"


def _io_error(error: OSError) -> GenerationError:
    return GenerationError(
        code="REFRESH_EXPERIMENT_IO_FAILED",
        message="failed to read or write refresh experiment artifacts",
        details={"path": str(getattr(error, "filename", ""))},
    )
