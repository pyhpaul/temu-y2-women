from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from pathlib import Path
from typing import Any

from temu_y2_women.errors import GenerationError

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_LEDGER_PATH = _PROJECT_ROOT / "data" / "feedback" / "dress" / "feedback_ledger.json"
_LEDGER_SCHEMA_VERSION = "feedback-ledger-v1"
_DRAFT_SCHEMA_VERSION = "draft-conflict-rules-v1"
_MIN_PAIR_PRESENCE_COUNT = 3
_WEAK_PENALTY = 0.08
_PAIR_REASON = "feedback rejects indicate this pattern/detail pair should be treated as a conflict candidate"
_SELECTED_ELEMENT_ROOTS = (
    ("feedback_target", "selected_elements"),
    ("selected_elements",),
    ("reviewed_feedback", "feedback_target", "selected_elements"),
)
_DECISIONS = {"keep", "reject"}


@dataclass(slots=True)
class PairAggregate:
    pattern_value: str
    detail_value: str
    keep_count: int = 0
    reject_count: int = 0
    source_feedback_ids: list[str] = field(default_factory=list)


def derive_conflict_rules_from_feedback_ledger(
    ledger_path: Path = _DEFAULT_LEDGER_PATH,
) -> dict[str, Any]:
    try:
        ledger = _load_ledger(ledger_path)
        aggregates, paired_record_count = _aggregate_pairs(ledger_path, ledger["records"])
        return _build_draft_payload(ledger_path, ledger["records"], aggregates, paired_record_count)
    except GenerationError as error:
        return error.to_dict()
    except OSError as error:
        return _io_error(error).to_dict()


def _load_ledger(path: Path) -> dict[str, Any]:
    payload = _load_json_object(path, "INVALID_FEEDBACK_LEDGER", "feedback ledger root must be an object")
    if payload.get("schema_version") != _LEDGER_SCHEMA_VERSION:
        raise _ledger_error(path, "schema_version", "feedback ledger schema_version is unsupported")
    if not isinstance(payload.get("records"), list):
        raise _ledger_error(path, "records", "feedback ledger must contain a records array")
    return payload


def _aggregate_pairs(
    path: Path,
    records: list[Any],
) -> tuple[dict[tuple[str, str], PairAggregate], int]:
    aggregates: dict[tuple[str, str], PairAggregate] = {}
    paired_record_count = 0
    for index, record in enumerate(records):
        observed = _extract_pair_observation(path, index, record)
        if observed is None:
            continue
        paired_record_count += 1
        key = (observed["pattern_value"], observed["detail_value"])
        aggregate = aggregates.setdefault(key, PairAggregate(*key))
        aggregate.source_feedback_ids.append(observed["feedback_id"])
        if observed["decision"] == "reject":
            aggregate.reject_count += 1
        else:
            aggregate.keep_count += 1
    return aggregates, paired_record_count


def _extract_pair_observation(path: Path, index: int, record: Any) -> dict[str, str] | None:
    if not isinstance(record, dict):
        raise _record_error(path, index, "record", "feedback ledger record must be an object")
    decision = _required_text(path, index, record, "decision").casefold()
    if decision not in _DECISIONS:
        raise _record_error(path, index, "decision", "feedback ledger decision must be keep or reject")
    feedback_id = _required_text(path, index, record, "feedback_id")
    selected = _find_selected_elements(record)
    if selected is None:
        return None
    slots = _selected_values_by_slot(path, index, selected)
    if "pattern" not in slots or "detail" not in slots:
        return None
    return {
        "feedback_id": feedback_id,
        "decision": decision,
        "pattern_value": slots["pattern"],
        "detail_value": slots["detail"],
    }


def _find_selected_elements(record: dict[str, Any]) -> Any:
    for chain in _SELECTED_ELEMENT_ROOTS:
        current: Any = record
        for part in chain:
            if not isinstance(current, dict) or part not in current:
                current = None
                break
            current = current[part]
        if current is not None:
            return current
    return None


def _selected_values_by_slot(path: Path, index: int, selected: Any) -> dict[str, str]:
    if isinstance(selected, list):
        return _selected_list_values(path, index, selected)
    if isinstance(selected, dict):
        return _selected_dict_values(path, index, selected)
    raise _record_error(path, index, "selected_elements", "selected_elements must be a list or object")


def _selected_list_values(path: Path, index: int, selected: list[Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    for item in selected:
        if not isinstance(item, dict):
            raise _record_error(path, index, "selected_elements", "selected element entries must be objects")
        slot = _canonicalize_text(_required_text(path, index, item, "slot"))
        value = _required_text(path, index, item, "value")
        values[slot] = value
    return values


def _selected_dict_values(path: Path, index: int, selected: dict[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    for slot_name, item in selected.items():
        if not isinstance(item, dict):
            raise _record_error(path, index, "selected_elements", "selected element values must be objects")
        slot = _canonicalize_text(str(slot_name))
        values[slot] = _required_text(path, index, item, "value")
    return values


def _build_draft_payload(
    ledger_path: Path,
    records: list[Any],
    aggregates: dict[tuple[str, str], PairAggregate],
    paired_record_count: int,
) -> dict[str, Any]:
    candidates = [_build_candidate(item) for item in aggregates.values()]
    rules = [item for item in candidates if item is not None]
    rules.sort(key=_candidate_sort_key)
    return {
        "schema_version": _DRAFT_SCHEMA_VERSION,
        "category": "dress",
        "source_artifacts": {"feedback_ledger": ledger_path.name},
        "summary": {
            "record_count": len(records),
            "paired_record_count": paired_record_count,
            "evaluated_pair_count": len(aggregates),
            "draft_count": len(rules),
            "skipped_pair_count": len(aggregates) - len(rules),
            "minimum_pair_presence_count": _MIN_PAIR_PRESENCE_COUNT,
        },
        "rules": rules,
    }


def _build_candidate(aggregate: PairAggregate) -> dict[str, Any] | None:
    evidence = _evidence_metrics(aggregate)
    suggestion = _severity_suggestion(
        evidence["pair_presence_count"],
        evidence["review_reject_rate"],
    )
    if suggestion is None:
        return None
    draft_rule_id = _draft_rule_id(aggregate.pattern_value, aggregate.detail_value)
    return {
        "draft_rule_id": draft_rule_id,
        "category": "dress",
        "left_slot": "pattern",
        "left_value": aggregate.pattern_value,
        "right_slot": "detail",
        "right_value": aggregate.detail_value,
        "suggested_severity": suggestion["severity"],
        "suggested_penalty": suggestion["penalty"],
        "reason": _PAIR_REASON,
        "scope": {
            "category": "dress",
            "target_market": "US",
            "season_tags": [],
            "occasion_tags": [],
            "price_bands": [],
        },
        "evidence_summary": _evidence_summary(
            aggregate,
            evidence["pair_presence_count"],
        ),
        "evidence": evidence,
        "confidence": evidence["review_reject_rate"],
        "decision_source": "feedback_heuristic",
        "status": "draft",
    }


def _evidence_metrics(aggregate: PairAggregate) -> dict[str, Any]:
    pair_presence_count = aggregate.keep_count + aggregate.reject_count
    reject_rate = round(aggregate.reject_count / pair_presence_count, 4)
    return {
        "pair_presence_count": pair_presence_count,
        "keep_count": aggregate.keep_count,
        "reject_count": aggregate.reject_count,
        "review_reject_rate": reject_rate,
        "source_feedback_ids": list(aggregate.source_feedback_ids),
    }


def _severity_suggestion(pair_presence_count: int, reject_rate: float) -> dict[str, Any] | None:
    if pair_presence_count < _MIN_PAIR_PRESENCE_COUNT:
        return None
    if reject_rate >= 0.75:
        return {"severity": "strong", "penalty": 0.0}
    if reject_rate >= 0.45:
        return {"severity": "weak", "penalty": _WEAK_PENALTY}
    return None


def _evidence_summary(aggregate: PairAggregate, pair_presence_count: int) -> str:
    return (
        f"{aggregate.reject_count} rejects out of {pair_presence_count} reviewed feedback records "
        f"for {aggregate.pattern_value} + {aggregate.detail_value}."
    )


def _candidate_sort_key(candidate: dict[str, Any]) -> tuple[float, int, str]:
    evidence = candidate["evidence"]
    return (
        -float(evidence["review_reject_rate"]),
        -int(evidence["pair_presence_count"]),
        str(candidate["draft_rule_id"]),
    )


def _draft_rule_id(pattern_value: str, detail_value: str) -> str:
    return f"draft-conflict-pattern-{_slug(pattern_value)}__detail-{_slug(detail_value)}"


def _slug(value: str) -> str:
    tokens = [item for item in re.split(r"[^a-z0-9]+", value.casefold()) if item]
    return "-".join(tokens)


def _load_json_object(path: Path, code: str, root_message: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise GenerationError(
            code=code,
            message="file must contain valid JSON",
            details={"path": str(path), "line": error.lineno, "column": error.colno},
        ) from error
    if isinstance(payload, dict):
        return payload
    raise GenerationError(code=code, message=root_message, details={"path": str(path)})


def _required_text(path: Path, index: int, record: dict[str, Any], field: str) -> str:
    value = record.get(field)
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise _record_error(path, index, field, f"feedback ledger field '{field}' must be a non-empty string")


def _canonicalize_text(value: str) -> str:
    return value.strip().casefold()


def _ledger_error(path: Path, field: str, message: str) -> GenerationError:
    return GenerationError(
        code="INVALID_FEEDBACK_LEDGER",
        message=message,
        details={"path": str(path), "field": field},
    )


def _record_error(path: Path, index: int, field: str, message: str) -> GenerationError:
    return GenerationError(
        code="INVALID_FEEDBACK_LEDGER",
        message=message,
        details={"path": str(path), "index": index, "field": field},
    )


def _io_error(error: OSError) -> GenerationError:
    return GenerationError(
        code="FEEDBACK_IO_FAILED",
        message="failed to read feedback derivation input",
        details={"path": str(getattr(error, "filename", ""))},
    )
