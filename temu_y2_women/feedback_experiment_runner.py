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
from temu_y2_women.feedback_loop import prepare_dress_concept_feedback
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
