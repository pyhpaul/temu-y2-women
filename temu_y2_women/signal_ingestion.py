from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from temu_y2_women.errors import GenerationError
from temu_y2_women.evidence_repository import load_evidence_taxonomy

_DEFAULT_TAXONOMY_PATH = Path("data/mvp/dress/evidence_taxonomy.json")
_DEFAULT_RULES_PATH = Path("data/ingestion/dress/signal_phrase_rules.json")
_SIGNAL_REQUIRED_FIELDS = {
    "signal_id",
    "source_type",
    "source_url",
    "captured_at",
    "target_market",
    "category",
    "title",
    "summary",
    "observed_price_band",
    "observed_occasion_tags",
    "observed_season_tags",
    "manual_tags",
    "status",
}


def ingest_dress_signals(
    input_path: Path,
    output_dir: Path,
    taxonomy_path: Path = _DEFAULT_TAXONOMY_PATH,
    rules_path: Path = _DEFAULT_RULES_PATH,
) -> dict[str, Any]:
    try:
        taxonomy = load_evidence_taxonomy(taxonomy_path)
        rules = _load_phrase_rules(rules_path, taxonomy)
        signals = _load_signal_bundle(input_path, taxonomy)
        normalized_signals = [_normalize_signal(signal) for signal in signals]
        draft_elements, signal_outcomes, warnings = _extract_draft_elements(normalized_signals, rules)
        draft_strategy_hints = _build_draft_strategy_hints(draft_elements)
        report = _build_ingestion_report(
            normalized_signals,
            draft_elements,
            draft_strategy_hints,
            signal_outcomes,
            warnings,
        )
        _write_staged_artifacts(output_dir, normalized_signals, draft_elements, draft_strategy_hints, report)
        return report
    except GenerationError as error:
        return error.to_dict()


def _load_signal_bundle(path: Path, taxonomy: dict[str, Any]) -> list[dict[str, Any]]:
    payload = _load_json_object(path)
    signals = payload.get("signals")
    if not isinstance(signals, list):
        raise GenerationError(
            code="INVALID_SIGNAL_INPUT",
            message="signal bundle must contain a 'signals' array",
            details={"path": str(path), "field": "signals"},
        )
    validated_signals: list[dict[str, Any]] = []
    for index, signal in enumerate(signals):
        validated_signals.append(_validate_signal_record(path, index, signal, taxonomy))
    return validated_signals


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload
    raise GenerationError(
        code="INVALID_SIGNAL_INPUT",
        message="signal bundle root must be an object",
        details={"path": str(path)},
    )


def _validate_signal_record(
    path: Path,
    index: int,
    signal: Any,
    taxonomy: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(signal, dict):
        raise _signal_error(path, index, "record", signal, "signal record must be an object")
    missing = sorted(_SIGNAL_REQUIRED_FIELDS.difference(signal.keys()))
    if missing:
        raise GenerationError(
            code="INVALID_SIGNAL_INPUT",
            message="signal record is missing required fields",
            details={"path": str(path), "index": index, "missing": missing},
        )
    _require_string_value(path, index, signal, "category")
    _require_string_value(path, index, signal, "target_market")
    if signal["category"] != "dress":
        raise _signal_error(path, index, "category", signal["category"], "unsupported signal category")
    if signal["target_market"] != "US":
        raise _signal_error(path, index, "target_market", signal["target_market"], "unsupported signal target_market")
    _validate_signal_lists(path, index, signal, taxonomy)
    return dict(signal)


def _require_string_value(path: Path, index: int, signal: dict[str, Any], field: str) -> None:
    if isinstance(signal.get(field), str):
        return
    raise _signal_error(path, index, field, signal.get(field), f"signal field '{field}' must be a string")


def _validate_signal_lists(
    path: Path,
    index: int,
    signal: dict[str, Any],
    taxonomy: dict[str, Any],
) -> None:
    _validate_string_list(path, index, signal, "manual_tags", taxonomy["allowed_tags"])
    _validate_string_list(path, index, signal, "observed_occasion_tags", taxonomy["allowed_occasions"])
    _validate_string_list(path, index, signal, "observed_season_tags", taxonomy["allowed_seasons"])


def _validate_string_list(
    path: Path,
    index: int,
    signal: dict[str, Any],
    field: str,
    allowed: list[str],
) -> None:
    value = signal.get(field)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise _signal_error(path, index, field, value, f"signal field '{field}' must be a list of strings")
    unknown = sorted(set(_canonical_string_list(value)).difference(allowed))
    if unknown:
        raise _signal_error(path, index, field, unknown[0], f"signal field '{field}' contains unsupported values")


def _signal_error(
    path: Path,
    index: int,
    field: str,
    value: Any,
    message: str,
) -> GenerationError:
    return GenerationError(
        code="INVALID_SIGNAL_INPUT",
        message=message,
        details={"path": str(path), "index": index, "field": field, "value": value},
    )


def _normalize_signal(signal: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        "signal_id": _canonical_string(signal["signal_id"]),
        "source_type": _canonical_string(signal["source_type"]),
        "source_url": _canonical_string(signal["source_url"]),
        "captured_at": _canonical_string(signal["captured_at"]),
        "target_market": _canonical_string(signal["target_market"]).upper(),
        "category": _canonical_string(signal["category"]),
        "title": str(signal["title"]).strip(),
        "summary": str(signal["summary"]).strip(),
        "observed_price_band": _canonical_string(signal["observed_price_band"]),
        "observed_occasion_tags": _canonical_string_list(signal["observed_occasion_tags"]),
        "observed_season_tags": _canonical_string_list(signal["observed_season_tags"]),
        "manual_tags": _canonical_string_list(signal["manual_tags"]),
        "status": _canonical_string(signal["status"]),
    }
    normalized["normalized_text"] = _build_normalized_text(normalized)
    return normalized


def _build_normalized_text(signal: dict[str, Any]) -> str:
    parts = [
        signal["title"],
        signal["summary"],
        *signal["manual_tags"],
        *signal["observed_occasion_tags"],
        *signal["observed_season_tags"],
    ]
    return " ".join(_canonical_string(part) for part in parts if str(part).strip())


def _canonical_string(value: str) -> str:
    return value.strip().casefold()


def _canonical_string_list(values: list[str]) -> list[str]:
    return sorted(set(_canonical_string(value) for value in values if value.strip()))


def _load_phrase_rules(path: Path, taxonomy: dict[str, Any]) -> list[dict[str, Any]]:
    payload = _load_json_object(path)
    rules = payload.get("slot_value_rules")
    if not isinstance(rules, list):
        raise GenerationError(
            code="INVALID_SIGNAL_INPUT",
            message="signal phrase rules must contain a 'slot_value_rules' array",
            details={"path": str(path), "field": "slot_value_rules"},
        )
    return [_validate_phrase_rule(path, rule, taxonomy) for rule in rules]


def _validate_phrase_rule(path: Path, rule: Any, taxonomy: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(rule, dict):
        raise GenerationError(
            code="INVALID_SIGNAL_INPUT",
            message="signal phrase rule must be an object",
            details={"path": str(path)},
        )
    slot = _canonical_string(str(rule.get("slot", "")))
    tags = _canonical_string_list(list(rule.get("tags", [])))
    if slot not in taxonomy["allowed_slots"] or any(tag not in taxonomy["allowed_tags"] for tag in tags):
        raise GenerationError(
            code="INVALID_SIGNAL_INPUT",
            message="signal phrase rule contains unsupported taxonomy values",
            details={"path": str(path), "slot": slot},
        )
    return {
        "slot": slot,
        "value": _canonical_string(str(rule.get("value", ""))),
        "phrases": [_canonical_string(str(phrase)) for phrase in list(rule.get("phrases", []))],
        "tags": tags,
    }


def _extract_draft_elements(
    normalized_signals: list[dict[str, Any]],
    rules: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    raw_candidates: list[dict[str, Any]] = []
    signal_outcomes: list[dict[str, Any]] = []
    warnings: list[str] = []
    for signal in normalized_signals:
        matches = _matching_rules(signal, rules)
        signal_outcomes.append(_build_signal_outcome(signal, matches))
        if not matches:
            warnings.append(f"no supported draft candidates extracted for signal {signal['signal_id']}")
            continue
        raw_candidates.extend(_build_raw_candidate(signal, rule) for rule in matches)
    return _aggregate_draft_elements(raw_candidates), signal_outcomes, warnings


def _matching_rules(signal: dict[str, Any], rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized_text = str(signal["normalized_text"])
    matches: list[dict[str, Any]] = []
    for rule in rules:
        matched_phrases = sorted({phrase for phrase in rule["phrases"] if phrase in normalized_text})
        if matched_phrases:
            matches.append({**rule, "matched_phrases": matched_phrases})
    return matches


def _build_raw_candidate(signal: dict[str, Any], rule: dict[str, Any]) -> dict[str, Any]:
    return {
        "slot": rule["slot"],
        "value": rule["value"],
        "tags": list(rule["tags"]),
        "price_bands": [signal["observed_price_band"]],
        "occasion_tags": list(signal["observed_occasion_tags"]),
        "season_tags": list(signal["observed_season_tags"]),
        "source_signal_ids": [signal["signal_id"]],
        "rule_matches": [
            {
                "signal_id": signal["signal_id"],
                "matched_phrases": list(rule["matched_phrases"]),
                "rule_slot": rule["slot"],
                "rule_value": rule["value"],
                "rule_tags": list(rule["tags"]),
            }
        ],
    }


def _aggregate_draft_elements(raw_candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for candidate in raw_candidates:
        key = (str(candidate["slot"]), str(candidate["value"]))
        grouped.setdefault(key, _empty_element_group(candidate))
        _merge_candidate_group(grouped[key], candidate)
    draft_elements = [_build_draft_element(slot, value, group) for (slot, value), group in grouped.items()]
    return sorted(draft_elements, key=lambda item: str(item["draft_id"]))


def _empty_element_group(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "tags": set(candidate["tags"]),
        "price_bands": set(candidate["price_bands"]),
        "occasion_tags": set(candidate["occasion_tags"]),
        "season_tags": set(candidate["season_tags"]),
        "source_signal_ids": set(candidate["source_signal_ids"]),
        "rule_matches": [],
    }


def _merge_candidate_group(group: dict[str, Any], candidate: dict[str, Any]) -> None:
    group["tags"].update(candidate["tags"])
    group["price_bands"].update(candidate["price_bands"])
    group["occasion_tags"].update(candidate["occasion_tags"])
    group["season_tags"].update(candidate["season_tags"])
    group["source_signal_ids"].update(candidate["source_signal_ids"])
    group["rule_matches"].extend(candidate["rule_matches"])


def _build_draft_element(slot: str, value: str, group: dict[str, Any]) -> dict[str, Any]:
    signal_count = len(group["source_signal_ids"])
    return {
        "draft_id": _draft_id(slot, value),
        "category": "dress",
        "slot": slot,
        "value": value,
        "tags": sorted(group["tags"]),
        "price_bands": sorted(group["price_bands"]),
        "occasion_tags": sorted(group["occasion_tags"]),
        "season_tags": sorted(group["season_tags"]),
        "risk_flags": [],
        "suggested_base_score": round(0.6 + (0.05 * signal_count), 2),
        "evidence_summary": f"Derived from {signal_count} signal{'s' if signal_count != 1 else ''} for US dress demand.",
        "source_signal_ids": sorted(group["source_signal_ids"]),
        "extraction_provenance": {
            "kind": "signal-rule-match",
            "rule_matches": sorted(group["rule_matches"], key=_rule_match_key),
        },
        "status": "draft",
    }


def _slugify(value: str) -> str:
    return value.replace(" ", "-")


def _draft_id(slot: str, value: str) -> str:
    return f"draft-{slot}-{_slugify(value)}"


def _rule_match_key(match: dict[str, Any]) -> tuple[str, str]:
    return str(match["signal_id"]), "|".join(str(item) for item in match["matched_phrases"])


def _build_draft_strategy_hints(draft_elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not draft_elements:
        return []
    season_tags = sorted({tag for element in draft_elements for tag in element["season_tags"]})
    occasion_tags = sorted({tag for element in draft_elements for tag in element["occasion_tags"]})
    source_signal_ids = sorted({tag for element in draft_elements for tag in element["source_signal_ids"]})
    slot_preferences = _build_slot_preferences(draft_elements)
    primary_season = season_tags[0] if season_tags else "all-season"
    return [
        {
            "hint_id": f"draft-strategy-us-{primary_season}-{'-'.join(occasion_tags)}",
            "category": "dress",
            "target_market": "US",
            "season_tags": season_tags,
            "occasion_tags": occasion_tags,
            "boost_tags": sorted({tag for element in draft_elements for tag in element["tags"]}),
            "slot_preferences": slot_preferences,
            "priority_signal": len(source_signal_ids),
            "source_signal_ids": source_signal_ids,
            "reason_summary": f"Aggregated from {len(source_signal_ids)} signals for US {primary_season} dress demand.",
            "extraction_provenance": _build_strategy_provenance(draft_elements),
            "status": "draft",
        }
    ]


def _build_slot_preferences(draft_elements: list[dict[str, Any]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for element in draft_elements:
        grouped.setdefault(str(element["slot"]), []).append(str(element["value"]))
    return {slot: sorted(values) for slot, values in sorted(grouped.items())}


def _build_ingestion_report(
    normalized_signals: list[dict[str, Any]],
    draft_elements: list[dict[str, Any]],
    draft_strategy_hints: list[dict[str, Any]],
    signal_outcomes: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": "signal-ingestion-v1",
        "summary": {
            "accepted_signal_count": len(normalized_signals),
            "draft_element_count": len(draft_elements),
            "draft_strategy_hint_count": len(draft_strategy_hints),
            "warning_count": len(warnings),
        },
        "coverage": _build_coverage(signal_outcomes),
        "accepted_signal_ids": [signal["signal_id"] for signal in normalized_signals],
        "skipped_signal_ids": [],
        "signal_outcomes": signal_outcomes,
        "warnings": warnings,
    }


def _build_strategy_provenance(draft_elements: list[dict[str, Any]]) -> dict[str, Any]:
    source_draft_ids = sorted(str(element["draft_id"]) for element in draft_elements)
    slot_value_identities = [
        {"draft_id": element["draft_id"], "slot": element["slot"], "value": element["value"]}
        for element in sorted(draft_elements, key=lambda item: str(item["draft_id"]))
    ]
    return {
        "kind": "draft-element-aggregation",
        "source_draft_ids": source_draft_ids,
        "slot_value_identities": slot_value_identities,
    }


def _build_signal_outcome(signal: dict[str, Any], matches: list[dict[str, Any]]) -> dict[str, Any]:
    outcome = {
        "signal_id": signal["signal_id"],
        "status": "matched" if matches else "unmatched",
        "emitted_draft_ids": sorted(_draft_id(match["slot"], match["value"]) for match in matches),
        "matched_rule_keys": sorted(f"{match['slot']}:{match['value']}" for match in matches),
    }
    if matches:
        return outcome
    return {**outcome, "reason": "no supported phrase rules matched normalized signal text"}


def _build_coverage(signal_outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    matched = [item["signal_id"] for item in signal_outcomes if item["status"] == "matched"]
    unmatched = [item["signal_id"] for item in signal_outcomes if item["status"] == "unmatched"]
    total = len(signal_outcomes) or 1
    return {
        "matched_signal_count": len(matched),
        "unmatched_signal_count": len(unmatched),
        "matched_signal_ids": matched,
        "unmatched_signal_ids": unmatched,
        "match_rate": round(len(matched) / total, 2),
    }


def _write_staged_artifacts(
    output_dir: Path,
    normalized_signals: list[dict[str, Any]],
    draft_elements: list[dict[str, Any]],
    draft_strategy_hints: list[dict[str, Any]],
    report: dict[str, Any],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "normalized_signals.json", {"schema_version": "signal-ingestion-v1", "signals": normalized_signals})
    _write_json(output_dir / "draft_elements.json", {"schema_version": "signal-ingestion-v1", "elements": draft_elements})
    _write_json(
        output_dir / "draft_strategy_hints.json",
        {"schema_version": "signal-ingestion-v1", "strategy_hints": draft_strategy_hints},
    )
    _write_json(output_dir / "ingestion_report.json", report)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
