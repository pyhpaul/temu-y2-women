from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any
from uuid import uuid4

from temu_y2_women.evidence_paths import EvidencePaths
from temu_y2_women.errors import GenerationError
from temu_y2_women.feedback_loop import (
    apply_reviewed_dress_concept_feedback,
    prepare_dress_concept_feedback,
)
from temu_y2_women.orchestrator import generate_dress_concept

_DEFAULT_LEDGER_PATH = Path(__file__).resolve().parent.parent / "data" / "feedback" / "dress" / "feedback_ledger.json"


@dataclass(frozen=True, slots=True)
class ExperimentSourcePaths:
    evidence_paths: EvidencePaths
    ledger_path: Path


def prepare_feedback_experiment(
    request_path: Path,
    experiment_root: Path,
    workspace_name: str | None = None,
    source_paths: ExperimentSourcePaths | None = None,
) -> dict[str, Any]:
    try:
        source = source_paths or _default_source_paths()
        request_payload = _load_json_object(request_path)
        experiment_id = _next_experiment_id()
        workspace_root = _resolve_workspace_root(experiment_root, workspace_name, experiment_id)
        workspace_paths = _workspace_paths(workspace_root)
        _copy_workspace_inputs(source, workspace_paths)
        baseline = generate_dress_concept(request_payload, evidence_paths=workspace_paths["evidence_paths"])
        baseline_result_path = workspace_root / "baseline_result.json"
        _write_json(baseline_result_path, baseline)
        review = prepare_dress_concept_feedback(result_path=baseline_result_path)
        feedback_review_path = workspace_root / "feedback_review.json"
        _write_json(feedback_review_path, review)
        manifest_path = workspace_root / "experiment_manifest.json"
        _write_json(
            manifest_path,
            _manifest_payload(
                experiment_id,
                request_path,
                workspace_root,
                workspace_paths,
                baseline_result_path,
                feedback_review_path,
                request_payload,
            ),
        )
        return _prepare_result(experiment_id, workspace_root, manifest_path, baseline_result_path, feedback_review_path)
    except GenerationError as error:
        return error.to_dict()
    except OSError as error:
        return _io_error(error).to_dict()


def apply_feedback_experiment(reviewed_path: Path, manifest_path: Path) -> dict[str, Any]:
    try:
        manifest = _load_json_object(manifest_path)
        workspace_root = Path(manifest["workspace_root"])
        workspace_paths = _manifest_workspace_paths(manifest)
        feedback_report_path = workspace_root / "feedback_report.json"
        apply_report = apply_reviewed_dress_concept_feedback(
            reviewed_path=reviewed_path,
            result_path=Path(manifest["baseline_result_path"]),
            active_elements_path=workspace_paths["evidence_paths"].elements_path,
            ledger_path=workspace_paths["ledger_path"],
            report_path=feedback_report_path,
            taxonomy_path=workspace_paths["evidence_paths"].taxonomy_path,
        )
        rerun = generate_dress_concept(
            _load_json_object(Path(manifest["request_path"])),
            evidence_paths=workspace_paths["evidence_paths"],
        )
        rerun_path = workspace_root / "post_apply_result.json"
        _write_json(rerun_path, rerun)
        experiment_report_path = workspace_root / "experiment_report.json"
        report = _build_experiment_report(
            manifest=manifest,
            reviewed=_load_json_object(reviewed_path),
            baseline=_load_json_object(Path(manifest["baseline_result_path"])),
            rerun=rerun,
            apply_report=apply_report,
        )
        _write_json(experiment_report_path, report)
        return {
            "experiment_id": str(manifest["experiment_id"]),
            "feedback_report_path": str(feedback_report_path),
            "post_apply_result_path": str(rerun_path),
            "experiment_report_path": str(experiment_report_path),
        }
    except GenerationError as error:
        return error.to_dict()
    except OSError as error:
        return _io_error(error).to_dict()


def _default_source_paths() -> ExperimentSourcePaths:
    return ExperimentSourcePaths(
        evidence_paths=EvidencePaths.defaults(),
        ledger_path=_DEFAULT_LEDGER_PATH,
    )


def _resolve_workspace_root(experiment_root: Path, workspace_name: str | None, experiment_id: str) -> Path:
    workspace_root = experiment_root / (workspace_name or experiment_id)
    workspace_root.mkdir(parents=True, exist_ok=False)
    return workspace_root


def _workspace_paths(workspace_root: Path) -> dict[str, Any]:
    data_root = workspace_root / "data"
    evidence_root = data_root / "mvp" / "dress"
    feedback_root = data_root / "feedback" / "dress"
    return {
        "evidence_paths": EvidencePaths(
            elements_path=evidence_root / "elements.json",
            strategies_path=evidence_root / "strategy_templates.json",
            taxonomy_path=evidence_root / "evidence_taxonomy.json",
        ),
        "ledger_path": feedback_root / "feedback_ledger.json",
    }


def _manifest_workspace_paths(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_paths": EvidencePaths(
            elements_path=Path(manifest["active_elements_path"]),
            strategies_path=Path(manifest["active_strategies_path"]),
            taxonomy_path=Path(manifest["taxonomy_path"]),
        ),
        "ledger_path": Path(manifest["ledger_path"]),
    }


def _copy_workspace_inputs(source: ExperimentSourcePaths, workspace_paths: dict[str, Any]) -> None:
    evidence_paths = workspace_paths["evidence_paths"]
    evidence_paths.elements_path.parent.mkdir(parents=True, exist_ok=True)
    workspace_paths["ledger_path"].parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source.evidence_paths.elements_path, evidence_paths.elements_path)
    shutil.copyfile(source.evidence_paths.strategies_path, evidence_paths.strategies_path)
    shutil.copyfile(source.evidence_paths.taxonomy_path, evidence_paths.taxonomy_path)
    shutil.copyfile(source.ledger_path, workspace_paths["ledger_path"])


def _manifest_payload(
    experiment_id: str,
    request_path: Path,
    workspace_root: Path,
    workspace_paths: dict[str, Any],
    baseline_result_path: Path,
    feedback_review_path: Path,
    request_payload: dict[str, Any],
) -> dict[str, Any]:
    evidence_paths = workspace_paths["evidence_paths"]
    return {
        "schema_version": "feedback-experiment-manifest-v1",
        "experiment_id": experiment_id,
        "category": str(request_payload["category"]),
        "request_path": str(request_path.resolve()),
        "request_fingerprint": _request_fingerprint(request_payload),
        "workspace_root": str(workspace_root),
        "baseline_result_path": str(baseline_result_path),
        "feedback_review_path": str(feedback_review_path),
        "active_elements_path": str(evidence_paths.elements_path),
        "active_strategies_path": str(evidence_paths.strategies_path),
        "taxonomy_path": str(evidence_paths.taxonomy_path),
        "ledger_path": str(workspace_paths["ledger_path"]),
        "created_at": _current_timestamp(),
    }


def _prepare_result(
    experiment_id: str,
    workspace_root: Path,
    manifest_path: Path,
    baseline_result_path: Path,
    feedback_review_path: Path,
) -> dict[str, Any]:
    return {
        "experiment_id": experiment_id,
        "workspace_root": str(workspace_root),
        "manifest_path": str(manifest_path),
        "baseline_result_path": str(baseline_result_path),
        "feedback_review_path": str(feedback_review_path),
    }


def _build_experiment_report(
    manifest: dict[str, Any],
    reviewed: dict[str, Any],
    baseline: dict[str, Any],
    rerun: dict[str, Any],
    apply_report: dict[str, Any],
) -> dict[str, Any]:
    selected_changes = _selected_element_changes(
        baseline["composed_concept"]["selected_elements"],
        rerun["composed_concept"]["selected_elements"],
    )
    retrieval_changes = _retrieval_rank_changes(
        baseline["retrieved_elements"],
        rerun["retrieved_elements"],
        reviewed["feedback_target"]["selected_element_ids"],
    )
    return {
        "schema_version": "feedback-experiment-report-v1",
        "experiment_id": str(manifest["experiment_id"]),
        "decision": reviewed["decision"],
        "change_type": _classify_change(selected_changes, retrieval_changes),
        "baseline_summary": _result_summary(baseline),
        "rerun_summary": _result_summary(rerun),
        "score_deltas": apply_report.get("affected_elements", []),
        "selected_element_changes": selected_changes,
        "retrieval_rank_changes": retrieval_changes,
        "warnings": apply_report.get("warnings", []),
        "recorded_at": _current_timestamp(),
    }


def _selected_element_changes(
    baseline_selected: dict[str, Any],
    rerun_selected: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    changes: dict[str, dict[str, Any]] = {}
    for slot in sorted(baseline_selected):
        if baseline_selected[slot] == rerun_selected.get(slot):
            continue
        changes[slot] = {
            "before": baseline_selected[slot],
            "after": rerun_selected.get(slot),
        }
    return changes


def _retrieval_rank_changes(
    baseline_retrieved: list[dict[str, Any]],
    rerun_retrieved: list[dict[str, Any]],
    target_ids: list[str],
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for element_id in target_ids:
        before = _retrieved_by_id(baseline_retrieved, element_id)
        after = _retrieved_by_id(rerun_retrieved, element_id)
        if before is None or after is None:
            continue
        if before["effective_score"] == after["effective_score"] and before["rank"] == after["rank"]:
            continue
        changes.append(
            {
                "element_id": element_id,
                "before_rank": before["rank"],
                "after_rank": after["rank"],
                "before_effective_score": before["effective_score"],
                "after_effective_score": after["effective_score"],
            }
        )
    return changes


def _retrieved_by_id(retrieved: list[dict[str, Any]], element_id: str) -> dict[str, Any] | None:
    for index, item in enumerate(retrieved, start=1):
        if item["element_id"] == element_id:
            return {
                "rank": index,
                "effective_score": item["effective_score"],
            }
    return None


def _classify_change(
    selected_changes: dict[str, dict[str, Any]],
    retrieval_changes: list[dict[str, Any]],
) -> str:
    if selected_changes:
        return "selection_changed"
    if retrieval_changes:
        return "retrieval_changed_only"
    return "no_observable_change"


def _result_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "concept_score": result["composed_concept"]["concept_score"],
        "selected_elements": result["composed_concept"]["selected_elements"],
    }


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise GenerationError(
            code="INVALID_EXPERIMENT_INPUT",
            message="experiment input file must contain valid JSON",
            details={"path": str(path), "line": error.lineno, "column": error.colno},
        ) from error
    if isinstance(payload, dict):
        return payload
    raise GenerationError(
        code="INVALID_EXPERIMENT_INPUT",
        message="experiment input root must be an object",
        details={"path": str(path)},
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


def _io_error(error: OSError) -> GenerationError:
    return GenerationError(
        code="EXPERIMENT_IO_FAILED",
        message="failed to read or write experiment artifacts",
        details={"path": str(getattr(error, "filename", ""))},
    )
