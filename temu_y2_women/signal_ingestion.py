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
_STRUCTURED_CANDIDATE_REQUIRED_FIELDS = {
    "slot",
    "value",
    "candidate_source",
    "supporting_card_ids",
    "supporting_card_count",
    "aggregation_threshold",
    "observation_model",
    "evidence_summary",
}
_MAX_DRAFT_SUMMARY_LENGTH = 140


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
    _validate_structured_candidates(path, index, signal, taxonomy)
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
    structured_candidates = _normalize_structured_candidates(signal.get("structured_candidates", []))
    if structured_candidates:
        normalized["structured_candidates"] = structured_candidates
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
    rule_tags = _build_rule_tag_lookup(rules)
    raw_candidates: list[dict[str, Any]] = []
    signal_outcomes: list[dict[str, Any]] = []
    warnings: list[str] = []
    for signal in normalized_signals:
        text_matches = _matching_rules(signal, rules)
        structured_matches = _structured_matches(signal)
        signal_outcomes.append(_build_signal_outcome(signal, text_matches, structured_matches))
        if not text_matches and not structured_matches:
            warnings.append(f"no supported draft candidates extracted for signal {signal['signal_id']}")
            continue
        raw_candidates.extend(_build_text_rule_candidate(signal, rule) for rule in text_matches)
        raw_candidates.extend(
            _build_structured_candidate(signal, candidate, rule_tags) for candidate in structured_matches
        )
    return _aggregate_draft_elements(raw_candidates), signal_outcomes, warnings


def _matching_rules(signal: dict[str, Any], rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized_text = str(signal["normalized_text"])
    matches: list[dict[str, Any]] = []
    for rule in rules:
        matched_phrases = sorted({phrase for phrase in rule["phrases"] if phrase in normalized_text})
        if matched_phrases:
            matches.append({**rule, "matched_phrases": matched_phrases})
    return matches


def _build_text_rule_candidate(signal: dict[str, Any], rule: dict[str, Any]) -> dict[str, Any]:
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
        "structured_candidate_matches": [],
        "matched_channels": {"text_rule"},
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
        "structured_candidate_matches": [],
        "matched_channels": set(),
    }


def _merge_candidate_group(group: dict[str, Any], candidate: dict[str, Any]) -> None:
    group["tags"].update(candidate["tags"])
    group["price_bands"].update(candidate["price_bands"])
    group["occasion_tags"].update(candidate["occasion_tags"])
    group["season_tags"].update(candidate["season_tags"])
    group["source_signal_ids"].update(candidate["source_signal_ids"])
    group["rule_matches"].extend(candidate["rule_matches"])
    group["structured_candidate_matches"].extend(candidate["structured_candidate_matches"])
    group["matched_channels"].update(candidate["matched_channels"])


def _build_draft_element(slot: str, value: str, group: dict[str, Any]) -> dict[str, Any]:
    signal_count = len(group["source_signal_ids"])
    evidence_count = _draft_evidence_count(group)
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
        "suggested_base_score": round(0.6 + (0.05 * evidence_count), 2),
        "evidence_summary": _build_draft_element_summary(group, signal_count),
        "source_signal_ids": sorted(group["source_signal_ids"]),
        "extraction_provenance": _build_element_provenance(group),
        "status": "draft",
    }


def _slugify(value: str) -> str:
    return value.replace(" ", "-")


def _draft_id(slot: str, value: str) -> str:
    return f"draft-{slot}-{_slugify(value)}"


def _rule_match_key(match: dict[str, Any]) -> tuple[str, str]:
    return str(match["signal_id"]), "|".join(str(item) for item in match["matched_phrases"])


def _structured_match_key(match: dict[str, Any]) -> tuple[str, str, str]:
    return str(match["signal_id"]), str(match["slot"]), str(match["value"])


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


def _build_signal_outcome(
    signal: dict[str, Any],
    text_matches: list[dict[str, Any]],
    structured_matches: list[dict[str, Any]],
) -> dict[str, Any]:
    matched_channels = _sorted_channels(text_matches, structured_matches)
    emitted_draft_ids = {
        _draft_id(match["slot"], match["value"]) for match in text_matches + structured_matches
    }
    outcome = {
        "signal_id": signal["signal_id"],
        "status": "matched" if emitted_draft_ids else "unmatched",
        "emitted_draft_ids": sorted(emitted_draft_ids),
        "matched_rule_keys": sorted(f"{match['slot']}:{match['value']}" for match in text_matches),
        "matched_structured_keys": sorted(f"{match['slot']}:{match['value']}" for match in structured_matches),
        "matched_channels": matched_channels,
    }
    if emitted_draft_ids:
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


def _validate_structured_candidates(path: Path, index: int, signal: dict[str, Any], taxonomy: dict[str, Any]) -> None:
    candidates = signal.get("structured_candidates")
    if candidates is None:
        return
    if not isinstance(candidates, list):
        raise _signal_error(path, index, "structured_candidates", candidates, "signal field 'structured_candidates' must be a list")
    for candidate in candidates:
        _validate_structured_candidate(path, index, candidate, taxonomy)


def _validate_structured_candidate(path: Path, index: int, candidate: Any, taxonomy: dict[str, Any]) -> None:
    if not isinstance(candidate, dict):
        raise _signal_error(path, index, "structured_candidates", candidate, "structured candidate must be an object")
    missing = sorted(_STRUCTURED_CANDIDATE_REQUIRED_FIELDS.difference(candidate.keys()))
    if missing:
        raise GenerationError(
            code="INVALID_SIGNAL_INPUT",
            message="structured candidate is missing required fields",
            details={"path": str(path), "index": index, "field": "structured_candidates", "missing": missing},
        )
    slot = _canonical_string(str(candidate["slot"]))
    value = _canonical_string(str(candidate["value"]))
    if slot not in taxonomy["allowed_slots"]:
        raise _signal_error(path, index, "structured_candidates.slot", slot, "structured candidate slot is unsupported")
    if not value:
        raise _signal_error(path, index, "structured_candidates.value", value, "structured candidate value must be non-empty")
    _require_structured_string(path, index, candidate, "candidate_source")
    _require_structured_string(path, index, candidate, "observation_model")
    _require_structured_string(path, index, candidate, "evidence_summary")
    _validate_structured_card_ids(path, index, candidate)
    _validate_positive_integer(path, index, candidate, "supporting_card_count")
    _validate_positive_integer(path, index, candidate, "aggregation_threshold")


def _require_structured_string(path: Path, index: int, candidate: dict[str, Any], field: str) -> None:
    if isinstance(candidate.get(field), str) and candidate[field].strip():
        return
    raise _signal_error(path, index, f"structured_candidates.{field}", candidate.get(field), "structured candidate field must be a non-empty string")


def _validate_structured_card_ids(path: Path, index: int, candidate: dict[str, Any]) -> None:
    card_ids = candidate.get("supporting_card_ids")
    if not isinstance(card_ids, list) or any(not isinstance(item, str) or not item.strip() for item in card_ids):
        raise _signal_error(path, index, "structured_candidates.supporting_card_ids", card_ids, "structured candidate supporting_card_ids must be a list of non-empty strings")


def _validate_positive_integer(path: Path, index: int, candidate: dict[str, Any], field: str) -> None:
    value = candidate.get(field)
    if isinstance(value, int) and value > 0:
        return
    raise _signal_error(path, index, f"structured_candidates.{field}", value, "structured candidate field must be a positive integer")


def _normalize_structured_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted((_normalize_structured_candidate(candidate) for candidate in candidates), key=_structured_candidate_sort_key)


def _normalize_structured_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "slot": _canonical_string(str(candidate["slot"])),
        "value": _canonical_string(str(candidate["value"])),
        "candidate_source": _canonical_string(str(candidate["candidate_source"])),
        "supporting_card_ids": sorted({str(item).strip() for item in candidate["supporting_card_ids"] if str(item).strip()}),
        "supporting_card_count": int(candidate["supporting_card_count"]),
        "aggregation_threshold": int(candidate["aggregation_threshold"]),
        "observation_model": _canonical_string(str(candidate["observation_model"])),
        "evidence_summary": str(candidate["evidence_summary"]).strip(),
    }


def _structured_candidate_sort_key(candidate: dict[str, Any]) -> tuple[str, str, str]:
    return str(candidate["slot"]), str(candidate["value"]), str(candidate["candidate_source"])


def _build_rule_tag_lookup(rules: list[dict[str, Any]]) -> dict[tuple[str, str], list[str]]:
    return {(str(rule["slot"]), str(rule["value"])): list(rule["tags"]) for rule in rules}


def _structured_matches(signal: dict[str, Any]) -> list[dict[str, Any]]:
    return list(signal.get("structured_candidates", []))


def _build_structured_candidate(
    signal: dict[str, Any],
    candidate: dict[str, Any],
    rule_tags: dict[tuple[str, str], list[str]],
) -> dict[str, Any]:
    slot = str(candidate["slot"])
    value = str(candidate["value"])
    return {
        "slot": slot,
        "value": value,
        "tags": list(rule_tags.get((slot, value), [])),
        "price_bands": [signal["observed_price_band"]],
        "occasion_tags": list(signal["observed_occasion_tags"]),
        "season_tags": list(signal["observed_season_tags"]),
        "source_signal_ids": [signal["signal_id"]],
        "rule_matches": [],
        "structured_candidate_matches": [{**candidate, "signal_id": signal["signal_id"]}],
        "matched_channels": {"structured_candidate"},
    }


def _build_draft_element_summary(group: dict[str, Any], signal_count: int) -> str:
    if group["structured_candidate_matches"]:
        return _compact_structured_summary(
            sorted(group["structured_candidate_matches"], key=_structured_summary_sort_key)[0]
        )
    return f"Derived from {signal_count} signal{'s' if signal_count != 1 else ''} for US dress demand."


def _structured_summary_sort_key(match: dict[str, Any]) -> tuple[int, str, str]:
    return -int(match["supporting_card_count"]), str(match["signal_id"]), str(match["candidate_source"])


def _compact_structured_summary(match: dict[str, Any]) -> str:
    summary = (
        f"{match['supporting_card_count']} cards agree on "
        f"{match['slot']}={match['value']}: {match['evidence_summary']}"
    )
    if len(summary) <= _MAX_DRAFT_SUMMARY_LENGTH:
        return summary
    return f"{summary[:_MAX_DRAFT_SUMMARY_LENGTH - 3].rstrip()}..."


def _draft_evidence_count(group: dict[str, Any]) -> int:
    return max(len(group["source_signal_ids"]), _max_supporting_card_count(group["structured_candidate_matches"]))


def _max_supporting_card_count(matches: list[dict[str, Any]]) -> int:
    if not matches:
        return 0
    return max(int(match["supporting_card_count"]) for match in matches)


def _build_element_provenance(group: dict[str, Any]) -> dict[str, Any]:
    channels = sorted(group["matched_channels"])
    provenance = {"kind": _provenance_kind(channels), "matched_channels": channels}
    if group["rule_matches"]:
        provenance["rule_matches"] = sorted(group["rule_matches"], key=_rule_match_key)
    if group["structured_candidate_matches"]:
        provenance["structured_candidate_matches"] = sorted(
            group["structured_candidate_matches"],
            key=_structured_match_key,
        )
    return provenance


def _provenance_kind(channels: list[str]) -> str:
    if channels == ["structured_candidate"]:
        return "structured-signal-candidate"
    if channels == ["text_rule"]:
        return "signal-rule-match"
    return "hybrid-signal-candidate"


def _sorted_channels(text_matches: list[dict[str, Any]], structured_matches: list[dict[str, Any]]) -> list[str]:
    channels: set[str] = set()
    if structured_matches:
        channels.add("structured_candidate")
    if text_matches:
        channels.add("text_rule")
    return sorted(channels)
